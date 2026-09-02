"""Domain logic for the general inventory arrays at $7E2400 (item IDs) and
$7E2500 (quantities): decoding/encoding the fixed-length byte arrays into an
ordered list of occupied slots, and the rules for which items show a
quantity in-game.
"""
from __future__ import annotations

from dataclasses import dataclass

from jetsoftime.ctenums import ItemID

ITEMS_BASE_ADDRESS = 0x7E2400
QUANTITIES_BASE_ADDRESS = 0x7E2500

# Beyond this many slots, $7E24F2.. / $7E25F2.. is documented unused padding,
# never a real slot. A save state's Mem Copy can be shorter than this
# (it only restores as many slots as that location cares about), but never
# longer in a way that turns padding into a slot.
REAL_SLOT_COUNT = 0xF2

# Substrings marking an enum member as an array boundary rather than a real,
# ownable item (e.g. WEAPON_END_5A, UNUSED_1C, OBJ_COUNT) -- never offered as
# a choice.
_NON_ITEM_NAME_MARKERS = ("UNUSED_", "_END_", "OBJ_COUNT")


@dataclass
class InventorySlot:
    item_id: int
    quantity: int


def real_slot_count(item_bytes: bytes) -> int:
    """How many of `item_bytes` are genuine slots rather than the documented
    padding past REAL_SLOT_COUNT. A save state's Mem Copy can be shorter than
    the full array, in which case it bounds the count instead."""
    return min(len(item_bytes), REAL_SLOT_COUNT)


def selectable_items() -> list[ItemID]:
    """Every real, ownable item, in ItemID declaration order. Excludes NONE
    (an empty slot is the absence of a row, not a selectable item) and the
    enum's own boundary markers."""
    return [
        item for item in ItemID
        if item != ItemID.NONE
        and not any(marker in item.name for marker in _NON_ITEM_NAME_MARKERS)
    ]


def is_stackable(item_id: int) -> bool:
    """Whether `item_id` shows a quantity in-game. Equipment (weapons through
    accessories) and key items are unique per slot and never stack."""
    if item_id <= ItemID.ACCESSORY_END_BC:
        return False
    return ItemID(item_id) not in ItemID.get_key_items()


def decode_slots(item_bytes: bytes, quantity_bytes: bytes) -> list[InventorySlot]:
    """Every occupied slot within the real-slot region, in array order, with
    empty slots dropped -- so a save state with a gap (an occupied slot
    after an empty one) reads back already compacted, matching how the
    in-game list -- which stops at the first empty slot -- would show it."""
    slot_count = real_slot_count(item_bytes)
    slots: list[InventorySlot] = []
    for index in range(slot_count):
        item_id = item_bytes[index]
        if item_id == ItemID.NONE:
            continue
        quantity = quantity_bytes[index] if index < len(quantity_bytes) else 0
        slots.append(InventorySlot(item_id, quantity))
    return slots


def encode_slots(
        slots: list[InventorySlot],
        item_bytes: bytes,
        quantity_bytes: bytes,
) -> tuple[bytes, bytes]:
    """The inverse of decode_slots(): re-packs `slots` starting at index 0 of
    the real-slot region, zero-fills the rest of that region, and preserves
    `item_bytes`/`quantity_bytes` unchanged past REAL_SLOT_COUNT (the
    documented padding -- never a slot, so never touched here)."""
    slot_count = real_slot_count(item_bytes)
    if len(slots) > slot_count:
        raise ValueError(f"{len(slots)} slot(s) do not fit in {slot_count} available slot(s)")

    new_items = bytearray(slot_count)
    new_quantities = bytearray(slot_count)
    for index, slot in enumerate(slots):
        new_items[index] = slot.item_id
        new_quantities[index] = slot.quantity

    return (
        bytes(new_items) + bytes(item_bytes[slot_count:]),
        bytes(new_quantities) + bytes(quantity_bytes[slot_count:]),
    )


def reorder(slots: list[InventorySlot], from_index: int, to_index: int) -> list[InventorySlot]:
    """A new list with the slot at `from_index` moved to `to_index` (both
    valid indices into `slots`). Does not mutate `slots`."""
    reordered = list(slots)
    slot = reordered.pop(from_index)
    reordered.insert(to_index, slot)
    return reordered
