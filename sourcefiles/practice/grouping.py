"""Curated display grouping and ordering for resolved save-state fields.

Grouping is purely address-based: an address falling in one of the curated
ranges below takes that range's name, and anything else is UNKNOWN_GROUP.
"""
from __future__ import annotations

from dataclasses import dataclass

UNKNOWN_GROUP = "Unknown / Undocumented"


@dataclass(frozen=True)
class GroupRule:
    name: str
    start_address: int
    end_address: int  # exclusive


# Each playable character's stat block.
CHARACTER_STAT_BLOCK_LENGTH = 0x50
CHARACTER_BASE_ADDRESSES: list[tuple[str, int]] = [
    ("Crono", 0x7E2600),
    ("Marle", 0x7E2650),
    ("Lucca", 0x7E26A0),
    ("Robo", 0x7E26F0),
    ("Frog", 0x7E2740),
    ("Ayla", 0x7E2790),
    ("Magus", 0x7E27E0),
]

# Checked in order; the first matching range wins
_GROUP_RULES: list[GroupRule] = [
    GroupRule(name, base_address, base_address + CHARACTER_STAT_BLOCK_LENGTH)
    for name, base_address in CHARACTER_BASE_ADDRESSES
] + [
    GroupRule("Techs", 0x7E2830, 0x7E2880),
    GroupRule("Inventory (Items & Quantities)", 0x7E2400, 0x7E2600),
    GroupRule("Party Composition", 0x7E2980, 0x7E2989),
    GroupRule("Character Names", 0x7E2C23, 0x7E2C53),
    GroupRule("Gold", 0x7E2C53, 0x7E2C56),
    GroupRule("Story Flags / Events", 0x7F0000, 0x7F0200),
    # Epoch and Dactyl position/state, one struct each, back to back and
    # ending just before the first unrelated row at 0x7E02A1.
    GroupRule("Vehicles (Epoch & Dactyl)", 0x7E0290, 0x7E02A1),
    # Battle speed, stereo, button remapping, menu background, save counts,
    # and the attract-mode/current-song bytes that sit with them.
    GroupRule("Settings & Session State", 0x7E2989, 0x7E29B0),
    # Per-character saved battle/skill cursor positions, Crono through Magus.
    GroupRule("Save Cursors", 0x7E2C7C, 0x7E2C9A),
]

# Explicit, code-configurable display order for the groups above. Anything
# not listed here sorts after all of these, alphabetically; UNKNOWN_GROUP
# always sorts last of all.
GROUP_DISPLAY_ORDER: list[str] = [
    "Crono", "Marle", "Lucca", "Robo", "Frog", "Ayla", "Magus",
    "Party Composition", "Character Names",
    "Inventory (Items & Quantities)", "Gold", "Techs",
    "Vehicles (Epoch & Dactyl)",
    "Story Flags / Events",
    "Settings & Session State", "Save Cursors",
]


def group_for_address(address: int) -> str:
    """The curated group `address` falls in, or UNKNOWN_GROUP."""
    for rule in _GROUP_RULES:
        if rule.start_address <= address < rule.end_address:
            return rule.name
    return UNKNOWN_GROUP


def group_sort_key(group_name: str) -> tuple:
    """Sort key implementing: GROUP_DISPLAY_ORDER, then any unlisted group
    (A-Z), then Unknown last."""
    if group_name == UNKNOWN_GROUP:
        return (2, group_name)
    try:
        return (0, GROUP_DISPLAY_ORDER.index(group_name))
    except ValueError:
        return (1, group_name)
