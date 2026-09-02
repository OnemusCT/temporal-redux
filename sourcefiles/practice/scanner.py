"""Detects Chrono Trigger Practice ROM save-state blocks in event scripts.

The practice hack gates room-startup state setup behind a check of flag byte
0x7F0021 (unused treasure-flag space in vanilla Chrono Trigger) against a
nonzero value.  That flag is set by the *previous* location's event code
before the room transition, never by the destination room itself, so the
guard is the only thing the destination room's own script needs to contain.

The value compared against selects *which* of that room's save states to
restore.

Because a conditional's forward jump distance is capped at 0xFF bytes, a
save state whose setup does not fit in one block splits it across several
consecutive `if (0x7F0021 == N) { ... }` blocks.  Each such block is a
"segment"; one save state is the union of every segment sharing its guard
value, in execution order.

Segments are not confined to Object 0's Startup function.  A second save
state in particular can live in an unrelated object and function (for
example, the Load Stats state for Masamune), so every object's every
function is searched.
"""
from __future__ import annotations

from dataclasses import dataclass

from gamebackend import GameBackend
from jetsoftime.ctevent import Event
from jetsoftime.eventcommand import EventCommand, Operation, get_command

PRACTICE_FLAG_ADDRESS = 0x7F0021
MEM_COPY_COMMAND = 0x4E

# A location's save states are keyed by (location id, guard value)
SaveStateKey = tuple[int, int]

_GUARD_COMMAND = 0x16
# The guard command encodes its flag as a byte offset from 0x7F0000, with
# offsets past 0x7F00FF setting the high bit of the operator byte instead of
# widening the offset. 0x7F0021 is below that, so the operator is a plain
# EQUALS.
_FLAG_OFFSET = PRACTICE_FLAG_ADDRESS - 0x7F0000
_EXPECTED_OPERATOR = int(Operation.EQUALS)

# Location name that decodes to bad event data and loops indefinitely rather
# than raise, so it must be skipped rather than caught.
_UNSCANNABLE_LOCATION_NAME_MARKER = "(Bad Event Data Packet)"


@dataclass
class PracticeSegment:
    """One practice-flag-guarded block whose body writes state.

    `mem_copies` pairs each Mem Copy command with its absolute byte offset
    in the owning Event's `data`, so edited values can be written back.
    `guard_value` is the flag value this block is gated on, i.e. which of
    the location's save states it belongs to.
    """
    guard_offset: int
    mem_copies: list[tuple[int, EventCommand]]
    guard_value: int


@dataclass
class PracticeSaveState:
    """One location's practice-hack setup for a single guard value."""
    location_id: int
    location_name: str
    segments: list[PracticeSegment]
    guard_value: int

    @property
    def key(self) -> SaveStateKey:
        return (self.location_id, self.guard_value)

    @property
    def mem_copies_in_order(self) -> list[tuple[int, EventCommand]]:
        """Every Mem Copy across all segments, in execution order."""
        return [mem_copy for segment in self.segments for mem_copy in segment.mem_copies]


def is_unscannable_location(location_name: str) -> bool:
    """Whether `location_name` is a known placeholder for degenerate event data."""
    return _UNSCANNABLE_LOCATION_NAME_MARKER in location_name


def mem_copy_destination(command: EventCommand) -> int:
    """The absolute WRAM address a Mem Copy writes to.

    The inverse of EventCommand.mem_copy()'s encoding: args[0] is the low
    16 bits, args[1] the bank byte. Kept here rather than open-coded at
    each caller so the opcode's arg layout is asserted in exactly one
    place."""
    return command.args[0] | (command.args[1] << 16)


def mem_copy_data(command: EventCommand) -> bytearray:
    """The payload a Mem Copy writes -- its trailing data blob arg."""
    return command.args[3]


def mem_copy_data_offset(command_offset: int, command: EventCommand) -> int:
    """Absolute offset of `command`'s data blob within the owning Event's
    `data`, given the command's own absolute offset. The blob is the last
    arg and sits at the end of the encoded command."""
    return command_offset + len(command) - len(mem_copy_data(command))


def refresh_save_state(event: Event, save_state: PracticeSaveState) -> None:
    """Re-decode `save_state`'s cached Mem Copy commands from `event.data`.

    The cached EventCommand objects hold a snapshot of their payload taken
    when the event was scanned, so any in-place write to `event.data` (see
    fields.apply_field_value / dumpapply.apply_location_dump) leaves them
    stale. Offsets are unaffected because no write changes a command's
    size."""
    for segment in save_state.segments:
        segment.mem_copies = [
            (command_offset, get_command(event.data, command_offset, event.platform))
            for command_offset, _stale_command in segment.mem_copies
        ]


def _unique_function_ranges(event: Event) -> list[tuple[int, int]]:
    """Every distinct [start, end) command range across all objects and
    functions.  Several function slots routinely point at the same offset
    (an object whose functions are all empty/aliased), so identical ranges
    are collapsed rather than walked repeatedly."""
    return sorted({
        (start, end) for start, end in event.get_all_function_bounds()
        if 0 <= start < end <= len(event.data)
    })


def find_practice_segments(event: Event) -> list[PracticeSegment]:
    """Every practice-flag-guarded, Mem-Copy-bearing block anywhere in
    `event`, in address order, each tagged with the guard value that
    selects it.

    Ranges from different objects can overlap or nest, so a guard already
    collected is never collected twice.
    """
    if event.num_objects == 0:
        return []

    segments: list[PracticeSegment] = []
    seen_guard_offsets: set[int] = set()

    for range_start, range_end in _unique_function_ranges(event):
        position = range_start
        while True:
            position, guard = event.find_command_opt([_GUARD_COMMAND], position, range_end)
            if position is None:
                break

            offset, value, operator, _ = guard.args
            if (
                    offset == _FLAG_OFFSET
                    and operator == _EXPECTED_OPERATOR
                    and value != 0
                    and position not in seen_guard_offsets
            ):
                body_start = position + len(guard)
                body = event.get_jump_block(position)
                mem_copies = [
                    (body_start + body.offsets[index], command)
                    for index, command in enumerate(body.commands)
                    if command.command == MEM_COPY_COMMAND
                ]
                if mem_copies:
                    seen_guard_offsets.add(position)
                    segments.append(PracticeSegment(position, mem_copies, value))

            position += len(guard)

    segments.sort(key=lambda segment: segment.guard_offset)
    return segments


def find_practice_save_states(
        event: Event,
        location_id: int,
        location_name: str,
) -> list[PracticeSaveState]:
    """`event`'s save states, one per distinct guard value, ordered by value."""
    segments_by_value: dict[int, list[PracticeSegment]] = {}
    for segment in find_practice_segments(event):
        segments_by_value.setdefault(segment.guard_value, []).append(segment)

    return [
        PracticeSaveState(location_id, location_name, segments_by_value[value], value)
        for value in sorted(segments_by_value)
    ]


def scan_backend_for_save_states(backend: GameBackend) -> dict[SaveStateKey, PracticeSaveState]:
    """Scan every location in `backend` for practice-hack save-state blocks,
    keyed by (location id, guard value) -- a location with more than one
    entry point contributes more than one entry.

    Locations with no such block, or with known-degenerate event data, are
    omitted from the result.
    """
    save_states: dict[SaveStateKey, PracticeSaveState] = {}
    for location_id, location_name in backend.get_location_list():
        if is_unscannable_location(location_name):
            continue

        event = backend.get_script(location_id)
        for save_state in find_practice_save_states(event, location_id, location_name):
            save_states[save_state.key] = save_state

    return save_states
