"""Tile property encode/decode for location maps.

Each tile has 3 bytes of property data (from MapTileProp):
  byte 0 (bits 0-1): L1/L2 tile index bit-8 flags (already handled by mapdata.py)
  byte 0 (bits 2-3): solidity quad (upper nibble of quad index, see below)
  byte 1: extended solidity / wind / z-plane / doors / stairs
  byte 2: NPC collision, battle encounter, unknown flags
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TileProperties:
    """Decoded per-tile property data (3 bytes)."""
    raw: bytes # always exactly 3 bytes

    @property
    def b0(self) -> int: return self.raw[0]
    @property
    def b1(self) -> int: return self.raw[1]
    @property
    def b2(self) -> int: return self.raw[2]

    @property
    def solidity_quad(self) -> int:
        """Lower 4 bits of the solidity word (from b0 bits 2-5)."""
        return (self.b0 >> 2) & 0x0F

    @property
    def z_plane(self) -> bool:
        return bool(self.b0 & 0x40)

    @property
    def wind_direction(self) -> int:
        return self.b1 & 0x07

    @property
    def wind_speed(self) -> int:
        return (self.b1 >> 3) & 0x1F

    @property
    def is_door(self) -> bool:
        return bool(self.b2 & 0x10)

    @property
    def is_battle(self) -> bool:
        return bool(self.b2 & 0x20)

    @property
    def is_npc_collision(self) -> bool:
        return bool(self.b2 & 0x40)

    @classmethod
    def from_tile_props(cls, tile_props: bytearray, x: int, y: int,
                        max_width: int) -> TileProperties:
        """Read from the flat tile_props buffer at tile (x, y)."""
        off = 3 * (y * max_width + x)
        return cls(raw=bytes(tile_props[off:off + 3]))

    def write_to_tile_props(self, tile_props: bytearray, x: int, y: int,
                            max_width: int) -> None:
        """Write (preserving L1/L2 bit-8 flags in byte 0 bits 0-1)."""
        off = 3 * (y * max_width + x)
        # Preserve bits 0-1 (tile index bit-8 for L1/L2)
        tile_props[off] = (tile_props[off] & 0x03) | (self.b0 & 0xFC)
        tile_props[off + 1] = self.b1
        tile_props[off + 2] = self.b2
