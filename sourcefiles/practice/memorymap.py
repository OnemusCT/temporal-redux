"""The MemoryFieldDef record and the address index built from it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_WHOLE_BYTE_BITMASK = 0xFF


@dataclass
class MemoryFieldDef:
    """One named memory location.

    `bitmask` is 0xFF for a location defined as a whole value, or a
    narrower mask for one named flag bit within a shared byte. `disabled`
    hides the field from the save-state editor entirely.
    """
    address: int
    length: int
    bitmask: int
    description: str
    disabled: bool = False

    @property
    def is_whole_value(self) -> bool:
        """Whether this defines the full byte(s) rather than one flag bit."""
        return self.bitmask == _WHOLE_BYTE_BITMASK


def build_address_index(field_defs: Iterable[MemoryFieldDef]) -> dict[int, list[MemoryFieldDef]]:
    """Group field definitions by their starting address."""
    address_index: dict[int, list[MemoryFieldDef]] = {}
    for field_definition in field_defs:
        address_index.setdefault(field_definition.address, []).append(field_definition)
    return address_index
