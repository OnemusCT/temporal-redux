"""Applies a parsed memory dump (see dumpimport.py) onto a location's
practice-hack save-state Mem Copy commands.

This never adds, removes, or resizes a Mem Copy command, it only ever
overwrites bytes that already sit inside one of the location's existing Mem
Copy destination ranges.

One byte is protected even when a Mem Copy's range happens to include it:
the practice-hack guard flag (scanner.PRACTICE_FLAG_ADDRESS), since writing
whatever the dump captured there could disable the guard this location's
own state-restore block depends on.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jetsoftime.ctevent import Event

from practice.dumpimport import LocationDump
from practice.scanner import (
    PRACTICE_FLAG_ADDRESS, PracticeSaveState, mem_copy_data, mem_copy_data_offset,
    mem_copy_destination,
)


@dataclass
class ApplyResult:
    """Coverage/outcome of applying one dump to one save state."""
    location_id: int
    dump_path: Path                     # the dump file this result came from
    guard_value: int
    mem_copy_byte_count: int = 0        # total bytes this location's Mem Copies cover
    matched_byte_count: int = 0         # of those, how many the dump had data for
    changed_byte_count: int = 0         # of those, how many actually differed and were written
    dump_byte_count: int = 0            # total bytes captured in the dump file
    guard_flag_in_range: bool = False   # the guard flag address fell inside a Mem Copy (never written)

    @property
    def changed(self) -> bool:
        return self.changed_byte_count > 0


def apply_location_dump(
        event: Event,
        save_state: PracticeSaveState,
        dump: LocationDump,
) -> ApplyResult:
    """Overwrite `event`'s Mem Copy data in place wherever `dump` has a
    byte for an address `save_state` already restores. Returns coverage
    stats; call again after re-scanning if you need the post-write bytes."""
    dump_bytes = _build_dump_byte_map(dump)

    result = ApplyResult(
        location_id=save_state.location_id,
        dump_path=dump.source_path,
        guard_value=save_state.guard_value,
        dump_byte_count=sum(len(chunk.data) for chunk in dump.chunks),
    )

    for command_offset, command in save_state.mem_copies_in_order:
        base_address = mem_copy_destination(command)
        data = mem_copy_data(command)
        data_start = mem_copy_data_offset(command_offset, command)
        result.mem_copy_byte_count += len(data)

        for blob_offset in range(len(data)):
            address = base_address + blob_offset

            if address == PRACTICE_FLAG_ADDRESS:
                result.guard_flag_in_range = True
                continue

            new_byte = dump_bytes.get(address)
            if new_byte is None:
                continue
            result.matched_byte_count += 1

            if data[blob_offset] != new_byte:
                event.data[data_start + blob_offset] = new_byte
                result.changed_byte_count += 1

    return result


def _build_dump_byte_map(dump: LocationDump) -> dict[int, int]:
    """Flatten every chunk into one address -> byte-value lookup. A later
    chunk's byte wins over an earlier one at the same address (shouldn't
    happen with real captures, but overlap is well-defined rather than an
    error)."""
    byte_map: dict[int, int] = {}
    for chunk in dump.chunks:
        for offset, value in enumerate(chunk.data):
            byte_map[chunk.address + offset] = value
    return byte_map
