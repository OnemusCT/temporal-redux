"""Resolves scanned Mem Copy payloads into named, typed fields, and writes
edited values back into the underlying Event.

`resolve_displayable_and_disabled_fields` walks each Mem Copy's destination
byte range and matches it against the address index built from
memorylocationdefs.py:

- The practice-hack guard flag byte (scanner.PRACTICE_FLAG_ADDRESS) ->
  DISABLED, whatever the rows say. Editing it could disable the guard the
  location's own state-restore block depends on. dumpapply.py protects the
  same byte on the batch-import path.
- Several rows sharing one address with a partial bitmask -> one BITMASK
  field for that byte, bundling every enabled bit.
- One row whose full length fits in the remaining bytes -> one NUMERIC
  field.
- A byte covered only by rows marked disabled=True -> DISABLED.
- Anything else (no row at all, or a row that doesn't fully fit) ->
  a single raw byte, labelled as unknown.

DISABLED fields are hidden entirely: excluded from the displayable half of
the returned pair, and their original bytes are always restored after Apply.

Every displayable field is also assigned a display `group` (see grouping.py)
and that half of the pair is sorted by (group, address) -- a fixed,
code-configurable order -- rather than the arbitrary order the ROM's Mem
Copy commands happen to execute in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from jetsoftime.byteops import get_minimal_shift
from jetsoftime.ctevent import Event
from jetsoftime.eventcommand import EventCommand, get_command

from practice import grouping
from practice.inventory import ITEMS_BASE_ADDRESS, QUANTITIES_BASE_ADDRESS
from practice.memorymap import MemoryFieldDef
from practice.scanner import (
    PRACTICE_FLAG_ADDRESS, PracticeSaveState, mem_copy_data, mem_copy_data_offset,
    mem_copy_destination,
)


class FieldKind(Enum):
    NUMERIC = auto()
    BITMASK = auto()
    RAW = auto()
    DISABLED = auto()
    INVENTORY_ITEMS = auto()
    INVENTORY_QUANTITIES = auto()

# The widest span a NUMERIC field is rendered as, since the editor shows one
# as a single spin box and 256**length stops being a usable range quickly.
#
# TODO: 20 documented rows are wider than this -- the seven character names
# and Epoch's (5 bytes each), the two tech tables (7), the six save cursors
# (4), the overworld storyline flags (0x10) and the treasure-flag table
# (0x4F). They currently fall through to the RAW path and render as
# "Unknown ($xxxxxx, N bytes)" despite having a label, because RAW is chosen
# before the label is consulted. Giving RAW spans their definition's label,
# or adding a kind that edits a wide span as labelled hex, is a follow-up.
_MAX_NUMERIC_FIELD_LENGTH = 3


@dataclass
class BitFieldOption:
    """One named bit (or sub-byte value) defined within a BITMASK field's byte."""
    mask: int
    description: str

    @property
    def is_single_bit(self) -> bool:
        """Whether this option is a true boolean flag (exactly one bit set)
        rather than a small enumeration packed into several bits."""
        return self.mask != 0 and (self.mask & (self.mask - 1)) == 0

    def extract(self, byte_value: int) -> int:
        """This option's value, shifted down out of `byte_value`."""
        return (byte_value & self.mask) >> get_minimal_shift(self.mask)

    def clear_from(self, byte_value: int) -> int:
        """`byte_value` with this option's bits zeroed."""
        return byte_value & ~self.mask & 0xFF

    def shifted_into_place(self, option_value: int) -> int:
        """`option_value` shifted up into this option's bits, ready to be
        OR-ed into a byte all of whose option bits have been cleared."""
        return (option_value << get_minimal_shift(self.mask)) & self.mask


@dataclass
class ResolvedField:
    """One user-editable value, located back to its owning Mem Copy command."""
    address: int
    length: int
    kind: FieldKind
    label: str
    current_bytes: bytes
    command_offset: int  # absolute offset of the owning Mem Copy command in event.data
    blob_offset: int     # offset of this field's bytes within that command's data blob
    group: str = grouping.UNKNOWN_GROUP
    bit_options: list[BitFieldOption] = field(default_factory=list)


def resolve_displayable_and_disabled_fields(
        save_state: PracticeSaveState,
        address_index: dict[int, list[MemoryFieldDef]],
) -> tuple[list[ResolvedField], list[ResolvedField]]:
    """Resolve `save_state` into (displayable, disabled).

    Displayable fields are the ones meant to be shown and edited, in a fixed
    display order rather than ROM execution order. Disabled fields are never
    shown -- they come back so Apply can force those bytes to their original
    value regardless of what else it wrote."""
    displayable_fields: list[ResolvedField] = []
    disabled_fields: list[ResolvedField] = []
    for resolved_field in _resolve_all_fields(save_state, address_index):
        if resolved_field.kind == FieldKind.DISABLED:
            disabled_fields.append(resolved_field)
        else:
            displayable_fields.append(resolved_field)

    displayable_fields.sort(key=lambda f: (grouping.group_sort_key(f.group), f.address))
    return displayable_fields, disabled_fields


def _resolve_all_fields(
        save_state: PracticeSaveState,
        address_index: dict[int, list[MemoryFieldDef]],
) -> list[ResolvedField]:
    # Bound once: mem_copies_in_order rebuilds a flattened list on every access.
    mem_copies = save_state.mem_copies_in_order
    inventory_kind_by_offset = _find_inventory_command_offsets(mem_copies)

    resolved_fields: list[ResolvedField] = []
    for command_offset, command in mem_copies:
        inventory_kind = inventory_kind_by_offset.get(command_offset)
        if inventory_kind is not None:
            resolved_fields.append(_resolve_inventory_command(command_offset, command, inventory_kind))
        else:
            resolved_fields.extend(_resolve_mem_copy(command_offset, command, address_index))
    return resolved_fields


def _find_inventory_command_offsets(
        mem_copies: list[tuple[int, EventCommand]],
) -> dict[int, FieldKind]:
    """The command offsets of this save state's item-array and quantity-array
    Mem Copies, keyed to which one they are (only when BOTH are present in
    the same save state). A save state with just one of the two (or neither)
    is left alone, so it falls through to the ordinary per-byte resolution
    below. That shouldn't ever happen"""
    items_offset = None
    quantities_offset = None
    for command_offset, command in mem_copies:
        base_address = mem_copy_destination(command)
        if base_address == ITEMS_BASE_ADDRESS:
            items_offset = command_offset
        elif base_address == QUANTITIES_BASE_ADDRESS:
            quantities_offset = command_offset

    if items_offset is None or quantities_offset is None:
        return {}
    return {items_offset: FieldKind.INVENTORY_ITEMS, quantities_offset: FieldKind.INVENTORY_QUANTITIES}


def _resolve_inventory_command(command_offset: int, command: EventCommand, kind: FieldKind) -> ResolvedField:
    """The whole Mem Copy as one field -- unlike the generic per-byte path,
    this never splits it into NUMERIC/RAW pieces, since InventoryEditorWidget
    (see editorui/inventoryeditor.py) interprets the whole span as one
    array of slots."""
    base_address = mem_copy_destination(command)
    data = mem_copy_data(command)
    label = "Inventory Items" if kind == FieldKind.INVENTORY_ITEMS else "Inventory Quantities"
    return ResolvedField(
        address=base_address, length=len(data), kind=kind, label=label,
        current_bytes=bytes(data), command_offset=command_offset, blob_offset=0,
        group=grouping.group_for_address(base_address),
    )


def _resolve_mem_copy(
        command_offset: int,
        command: EventCommand,
        address_index: dict[int, list[MemoryFieldDef]],
) -> list[ResolvedField]:
    base_address = mem_copy_destination(command)
    data = mem_copy_data(command)

    resolved_fields: list[ResolvedField] = []
    blob_offset = 0
    while blob_offset < len(data):
        address = base_address + blob_offset
        remaining_length = len(data) - blob_offset

        if address == PRACTICE_FLAG_ADDRESS:
            resolved_fields.append(ResolvedField(
                address=address, length=1, kind=FieldKind.DISABLED,
                label="Practice save-state guard flag",
                current_bytes=bytes(data[blob_offset:blob_offset + 1]),
                command_offset=command_offset, blob_offset=blob_offset,
                group=grouping.group_for_address(address),
            ))
            blob_offset += 1
            continue

        definitions_at_address = address_index.get(address, [])
        active_definitions = [d for d in definitions_at_address if not d.disabled]
        whole_value_definitions = [d for d in active_definitions if d.is_whole_value]
        bit_definitions = [d for d in active_definitions if not d.is_whole_value]

        if bit_definitions:
            resolved_fields.append(ResolvedField(
                address=address, length=1, kind=FieldKind.BITMASK,
                label=_combined_label(bit_definitions),
                current_bytes=bytes(data[blob_offset:blob_offset + 1]),
                command_offset=command_offset, blob_offset=blob_offset,
                group=grouping.group_for_address(address),
                bit_options=[BitFieldOption(d.bitmask, d.description) for d in bit_definitions],
            ))
            blob_offset += 1
            continue

        if (
                whole_value_definitions
                and whole_value_definitions[0].length <= remaining_length
                and whole_value_definitions[0].length <= _MAX_NUMERIC_FIELD_LENGTH
        ):
            field_definition = whole_value_definitions[0]
            resolved_fields.append(ResolvedField(
                address=address, length=field_definition.length, kind=FieldKind.NUMERIC,
                label=field_definition.description,
                current_bytes=bytes(data[blob_offset:blob_offset + field_definition.length]),
                command_offset=command_offset, blob_offset=blob_offset,
                group=grouping.group_for_address(address),
            ))
            blob_offset += field_definition.length
            continue

        disabled_span = _disabled_span_at(definitions_at_address, remaining_length)
        if disabled_span is not None:
            span_length, representative = disabled_span
            resolved_fields.append(ResolvedField(
                address=address, length=span_length, kind=FieldKind.DISABLED,
                label=representative.description,
                current_bytes=bytes(data[blob_offset:blob_offset + span_length]),
                command_offset=command_offset, blob_offset=blob_offset,
                group=grouping.group_for_address(address),
            ))
            blob_offset += span_length
            continue

        resolved_fields.append(ResolvedField(
            address=address, length=1, kind=FieldKind.RAW,
            label=f"Unknown (${address:06X})",
            current_bytes=bytes(data[blob_offset:blob_offset + 1]),
            command_offset=command_offset, blob_offset=blob_offset,
            group=grouping.group_for_address(address),
        ))
        blob_offset += 1

    return resolved_fields


def _disabled_span_at(
        definitions_at_address: list[MemoryFieldDef],
        remaining_length: int,
) -> tuple[int, MemoryFieldDef] | None:
    """If every row at this address is disabled (there's no enabled
    alternative that could have been used instead), the byte span they cover
    and a representative row to label it with; otherwise None.

    A defined-but-non-fitting enabled row (e.g. a 2-byte field with only
    1 byte left in this Mem Copy) is not disabled -- that still falls
    through to the ordinary RAW/Unknown path, unchanged from before."""
    if not definitions_at_address or any(not d.disabled for d in definitions_at_address):
        return None

    whole_value = next((d for d in definitions_at_address if d.is_whole_value), None)
    if whole_value is not None and whole_value.length <= remaining_length:
        return whole_value.length, whole_value
    return 1, definitions_at_address[0]


def _combined_label(bit_definitions: list[MemoryFieldDef]) -> str:
    return ' / '.join(dict.fromkeys(d.description for d in bit_definitions))


def apply_field_value(event: Event, resolved_field: ResolvedField, new_bytes: bytes) -> None:
    """Overwrite `resolved_field`'s bytes in place.  `new_bytes` must match its length."""
    if len(new_bytes) != resolved_field.length:
        raise ValueError(
            f"Expected {resolved_field.length} byte(s) for {resolved_field.label!r}, "
            f"got {len(new_bytes)}"
        )

    command = get_command(event.data, resolved_field.command_offset, event.platform)
    data_start = mem_copy_data_offset(resolved_field.command_offset, command)
    field_start = data_start + resolved_field.blob_offset

    event.data[field_start:field_start + resolved_field.length] = new_bytes


def merge_consecutive_raw_fields(resolved_fields: list[ResolvedField]) -> list[ResolvedField]:
    """Collapse runs of adjacent, undefined single-byte RAW fields into one
    field per run, so a location with hundreds of undefined bytes doesn't
    render as hundreds of one-byte rows.

    Only fields contiguous within the same Mem Copy are merged -- a merged
    field keeps the run's first command_offset/blob_offset, so the result is
    still writable through apply_field_value()."""
    merged: list[ResolvedField] = []
    run: list[ResolvedField] = []

    def flush_run() -> None:
        if not run:
            return
        if len(run) == 1:
            merged.append(run[0])
        else:
            first = run[0]
            combined_bytes = b''.join(f.current_bytes for f in run)
            merged.append(ResolvedField(
                address=first.address, length=len(combined_bytes), kind=FieldKind.RAW,
                label=f"Unknown (${first.address:06X}, {len(combined_bytes)} bytes)",
                current_bytes=combined_bytes,
                command_offset=first.command_offset, blob_offset=first.blob_offset,
                group=first.group,
            ))
        run.clear()

    for resolved_field in resolved_fields:
        if resolved_field.kind != FieldKind.RAW:
            flush_run()
            merged.append(resolved_field)
            continue
        if run and not _is_contiguous(run[-1], resolved_field):
            flush_run()
        run.append(resolved_field)
    flush_run()

    return merged


def _is_contiguous(previous: ResolvedField, following: ResolvedField) -> bool:
    """Whether `following` starts exactly where `previous` ends, inside the
    same Mem Copy's data blob."""
    return (
        previous.command_offset == following.command_offset
        and previous.blob_offset + previous.length == following.blob_offset
    )
