"""Batch-applies a directory of Practice ROM memory-dump text files (see
dumpimport.py) onto a Practice ROM, without launching the Temporal Redux GUI.

Usage (from anywhere):
    python apply_dumps.py <rom_path> <dump_dir> [options]

Or, from sourcefiles/:
    python -m practice.apply_dumps <rom_path> <dump_dir> [options]

Each dump file's location id (parsed from its filename, see
dumpimport.parse_dump_filename) is matched against the rom's own
practice-hack save states (see scanner.scan_backend_for_save_states).
A save state is only ever written when a dump is paired to it; a dump file
with no matching save state, or a save state with no matching dump file, is
reported and left alone rather than guessed at.

A location can hold more than one save state -- one per entry point, each
gated on a different value of the practice flag (see scanner.py) -- and
correspondingly can have more than one dump file, distinguished by a
"-<variant>" filename suffix (e.g. "070.txt" and "070-MIDROOM.txt": the
same room captured once through its normal door and once via a debug
mid-room warp).

Which dump belongs to which save state is decided by the filename variant
alone (see _GUARD_VALUE_BY_VARIANT): the unsuffixed file is the room's
normal entrance, guard value 1, and "-MIDROOM" is its mid-room warp, guard
value 2. Deliberately not inferred from the bytes already in a slot --
every byte a dump covers is overwritten anyway, and a slot's current
contents can be a leftover from an earlier build of the ROM rather than
evidence of what belongs there.

By default nothing is overwritten in place: the patched rom is written to a
new file alongside the input (see _PATCHED_OUTPUT_SUFFIX below). Pass
--in-place to overwrite the input rom instead, or --dry-run to print the
report without writing any file at all.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

# gamebackend.py imports itself  via "sourcefiles.jetsoftime.x" rather
# than "jetsoftime.x"
# The rest of practice/ and editorui/ instead import gamebackend.py and jetsoftime/
# unqualified, as if sourcefiles/ itself were a path root. Both styles
# coexist in the app today (see TemporalRedux.spec's comment on it) and are
# normally resolved for free by an IDE's source-root configuration. This
# script is meant to run standalone, outside any IDE, so it sets both roots
# up itself rather than silently depending on that.
# I really want to fix the inconsistency, but not today.
_SOURCEFILES_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT_DIR = _SOURCEFILES_DIR.parent
for _extra_sys_path_entry in (str(_REPO_ROOT_DIR), str(_SOURCEFILES_DIR)):
    if _extra_sys_path_entry not in sys.path:
        sys.path.insert(0, _extra_sys_path_entry)

from gamebackend import SnesBackend  # noqa: E402 -- must follow the sys.path setup above
from jetsoftime.freespace import FreeSpaceError  # noqa: E402
from sourcefiles.jetsoftime.freespace import FreeSpaceError as _AliasedFreeSpaceError  # noqa: E402
from practice.dumpapply import ApplyResult, apply_location_dump  # noqa: E402
from practice.dumpimport import LocationDump, load_dump_directory  # noqa: E402
from practice.scanner import PracticeSaveState, scan_backend_for_save_states  # noqa: E402

_PATCHED_OUTPUT_SUFFIX = ".patched"

# gamebackend.py reaches the freespace module via the "sourcefiles.jetsoftime.*"
# import path, while practice/ reaches it via "jetsoftime.*" (see the sys.path
# note above). Python loads those as two unrelated modules, each defining its
# own FreeSpaceError class, so an `except` naming only one silently fails to
# catch the other (which is exactly what a write-space failure raises here)
# The two names collapse to one class if only a single path was ever imported,
# so listing both is safe either way.
_FREE_SPACE_ERRORS = (FreeSpaceError, _AliasedFreeSpaceError)

# Which save-state slot (practice-flag guard value) each dump filename
# variant belongs to. The unsuffixed file is the room's normal entrance,
# guard value 1; "-MIDROOM" is its debug mid-room warp, guard value 2.
# Add a row here to teach the tool a new variant suffix.
_GUARD_VALUE_BY_VARIANT: dict[str | None, int] = {
    None: 1,
    'MIDROOM': 2,
}


@dataclass
class DumpAssignment:
    """One dump paired to the save state slot its filename variant names."""
    save_state: PracticeSaveState
    dump: LocationDump


@dataclass
class BatchResult:
    results: list[ApplyResult] = field(default_factory=list)
    unmatched_dumps: list[LocationDump] = field(default_factory=list)      # no save state to pair with
    unpaired_save_states: list[PracticeSaveState] = field(default_factory=list)  # no dump to pair with
    write_failures: list[tuple[int, str]] = field(default_factory=list)    # (location id, why)


def guard_value_for_variant(variant: str | None) -> int | None:
    """The practice-flag value whose save state a dump file's filename
    variant names, or None if the variant isn't one this tool knows how to
    place.

    This is a fixed convention rather than anything derived from the ROM:
    the practice hack's own entry-point numbering decides which slot is
    which, and a dump's *existing* bytes say nothing about where it belongs
    (every byte a dump covers is overwritten anyway, and a slot's current
    contents can be a leftover from an earlier build).
    """
    return _GUARD_VALUE_BY_VARIANT.get(variant)


def group_dumps_by_location(dumps: list[LocationDump]) -> dict[int, list[LocationDump]]:
    """All dumps for each location id, base file (no variant) first."""
    grouped: dict[int, list[LocationDump]] = {}
    for dump in dumps:
        grouped.setdefault(dump.location_id, []).append(dump)
    for location_dumps in grouped.values():
        location_dumps.sort(key=lambda dump: (dump.variant is not None, dump.variant or ''))
    return grouped


def pair_dumps_to_save_states(
        dumps: list[LocationDump],
        save_states: list[PracticeSaveState],
) -> tuple[list[DumpAssignment], list[LocationDump], list[PracticeSaveState]]:
    """Pair each dump with the save state whose guard value its filename
    variant designates (see guard_value_for_variant).

    A dump naming a slot this location doesn't have -- and a slot no dump
    names -- is reported back rather than force-fitted onto whatever is
    left over, so a missing or misnamed file surfaces instead of silently
    writing a state into the wrong entry point.

    Returns (assignments, dumps left over, save states left over).
    """
    states_by_guard_value = {save_state.guard_value: save_state for save_state in save_states}

    assignments: list[DumpAssignment] = []
    leftover_dumps: list[LocationDump] = []
    claimed_guard_values: set[int] = set()

    for dump in dumps:
        guard_value = guard_value_for_variant(dump.variant)
        save_state = states_by_guard_value.get(guard_value) if guard_value is not None else None
        if save_state is None or guard_value in claimed_guard_values:
            leftover_dumps.append(dump)
            continue
        claimed_guard_values.add(guard_value)
        assignments.append(DumpAssignment(save_state=save_state, dump=dump))

    assignments.sort(key=lambda assignment: assignment.save_state.guard_value)
    leftover_states = [
        save_state for save_state in save_states
        if save_state.guard_value not in claimed_guard_values
    ]
    return assignments, leftover_dumps, leftover_states


def apply_all(backend: SnesBackend, dumps: list[LocationDump]) -> BatchResult:
    """Pair and apply every dump, writing each touched location back into
    the backend's rom (in memory -- callers still need to call
    backend.save_to_file())."""
    save_states = scan_backend_for_save_states(backend)

    states_by_location: dict[int, list[PracticeSaveState]] = {}
    for save_state in save_states.values():
        states_by_location.setdefault(save_state.location_id, []).append(save_state)
    for location_states in states_by_location.values():
        location_states.sort(key=lambda state: state.guard_value)

    dumps_by_location = group_dumps_by_location(dumps)

    batch = BatchResult()
    changed_location_ids: list[int] = []
    for location_id in sorted(set(dumps_by_location) | set(states_by_location)):
        location_dumps = dumps_by_location.get(location_id, [])
        location_states = states_by_location.get(location_id, [])
        assignments, leftover_dumps, leftover_states = pair_dumps_to_save_states(
            location_dumps, location_states)

        batch.unmatched_dumps.extend(leftover_dumps)
        batch.unpaired_save_states.extend(leftover_states)
        if not assignments:
            continue

        # Every save state in a location shares one Event, so all of that
        # location's assignments are applied together.
        event = backend.get_script(location_id)
        changed = False
        for assignment in assignments:
            result = apply_location_dump(event, assignment.save_state, assignment.dump)
            batch.results.append(result)
            changed = changed or result.changed

        if changed:
            changed_location_ids.append(location_id)

    # Written as one batch rather than per location: the rom's free space is
    # scarce enough that recompiling locations one at a time lets earlier,
    # smaller scripts consume the only blocks large enough for a later,
    # larger one -- even when the run as a whole needs less space than it
    # frees. See ScriptManager.write_scripts_to_rom().
    try:
        unplaced = backend.write_scripts(changed_location_ids)
    except _FREE_SPACE_ERRORS as error:
        batch.write_failures.extend(
            (location_id, str(error)) for location_id in changed_location_ids
        )
    else:
        batch.write_failures.extend(
            (location_id, 'no free space large enough for the recompiled script')
            for location_id in unplaced
        )

    return batch


def _print_report(batch: BatchResult) -> None:
    changed_results = [result for result in batch.results if result.changed]

    print(f"{len(batch.results)} save state(s) paired with a dump file:")
    for result in batch.results:
        status = f"{result.changed_byte_count} byte(s) changed" if result.changed else "no change"
        coverage = f"{result.matched_byte_count}/{result.mem_copy_byte_count} byte(s) covered"
        guard_note = "  [guard flag in range, left untouched]" if result.guard_flag_in_range else ""
        print(
            f"  0x{result.location_id:03X} slot {result.guard_value}  <- {result.dump_path.name:<20} "
            f"{status:<18} {coverage}{guard_note}"
        )

    if batch.unmatched_dumps:
        print(f"\n{len(batch.unmatched_dumps)} dump file(s) had no save state to pair with:")
        for dump in batch.unmatched_dumps:
            print(f"  0x{dump.location_id:03X}  {dump.source_path.name}  ({dump.header})")

    if batch.unpaired_save_states:
        print(f"\n{len(batch.unpaired_save_states)} save state(s) had no dump file to pair with:")
        for save_state in batch.unpaired_save_states:
            print(f"  0x{save_state.location_id:03X} slot {save_state.guard_value}  {save_state.location_name}")

    if batch.write_failures:
        print(f"\n{len(batch.write_failures)} location(s) could NOT be written back:")
        for location_id, message in batch.write_failures:
            print(f"  0x{location_id:03X}: {message}")

    failed_location_ids = {location_id for location_id, _message in batch.write_failures}
    changed_location_ids = {result.location_id for result in changed_results}
    written_count = len(changed_location_ids - failed_location_ids)
    print(f"\n{len(changed_results)} save state(s) updated across {written_count} location(s), "
          f"{len(batch.results) - len(changed_results)} unchanged.")


def run(rom_path: Path, dump_dir: Path, output_path: Path, dry_run: bool) -> int:
    backend = SnesBackend.from_path(rom_path)

    load_result = load_dump_directory(dump_dir)
    for _path, message in load_result.errors:
        print(f"SKIP  {message}")
    if load_result.ignored:
        ignored_names = ", ".join(path.name for path in load_result.ignored)
        print(f"Ignored {len(load_result.ignored)} non-dump file(s): {ignored_names}")

    batch = apply_all(backend, load_result.dumps)
    _print_report(batch)

    changed_count = sum(1 for result in batch.results if result.changed)
    if batch.write_failures:
        # All or nothing: a rom missing some of the locations it was asked to
        # update is worse than no rom at all, since the gap is invisible once
        # this report has scrolled away.
        print(f"\n{len(batch.write_failures)} location(s) could not be placed; no rom written.")
        return 1
    if dry_run:
        print(f"\nDry run: {changed_count} save state(s) would be updated. No file written.")
        return 0
    if changed_count == 0:
        print("\nNo changes to apply; rom not written.")
        return 0

    backend.save_to_file(output_path)
    print(f"\nWrote {changed_count} updated save state(s) to {output_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("rom", type=Path, help="Path to the Practice ROM (.smc) to update")
    parser.add_argument("dump_dir", type=Path, help="Directory of <hex location id>[-variant].txt dump files")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help=f"Output rom path (default: <rom stem>{_PATCHED_OUTPUT_SUFFIX}<rom suffix>, next to the input)",
    )
    parser.add_argument(
        "--in-place", action="store_true",
        help="Overwrite the input rom instead of writing a new file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the report without writing any rom file",
    )
    args = parser.parse_args(argv)

    if args.in_place and args.output is not None:
        parser.error("--in-place and --output are mutually exclusive")
    if not args.rom.is_file():
        parser.error(f"rom not found: {args.rom}")
    if not args.dump_dir.is_dir():
        parser.error(f"dump directory not found: {args.dump_dir}")

    if args.in_place:
        output_path = args.rom
    elif args.output is not None:
        output_path = args.output
    else:
        output_path = args.rom.with_name(args.rom.stem + _PATCHED_OUTPUT_SUFFIX + args.rom.suffix)

    return run(args.rom, args.dump_dir, output_path, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
