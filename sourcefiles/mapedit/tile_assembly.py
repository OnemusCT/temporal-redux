"""Tile assembly codec for Chrono Trigger location and overworld maps.

Each 16x16 tile is composed of four 8x8 subtiles (top-left, top-right,
bottom-left, bottom-right), each described by a 2-byte word in the tile
assembly table (8 bytes per tile total).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass
class SubtileReference:
    """Decoded reference to one 8x8 subtile within a 16x16 tile."""
    index: int # bits 0-9: subtile index in the graphics buffer
    palette: int # bits 10-12: palette shift (0-7)
    priority: bool # bit 13: high-priority flag (rendered on main-screen pass)
    h_flip: bool # bit 14: horizontal flip
    v_flip: bool # bit 15: vertical flip

    @classmethod
    def from_word(cls, word: int) -> SubtileReference:
        return cls(
            index = word & 0x3FF,
            palette = (word >> 10) & 0x7,
            priority = bool((word >> 13) & 0x1),
            h_flip = bool((word >> 14) & 0x1),
            v_flip = bool(word >> 15),
        )

    def to_word(self) -> int:
        return (
            (self.index & 0x3FF)
            | ((self.palette & 0x7) << 10)
            | (int(self.priority) << 13)
            | (int(self.h_flip) << 14)
            | (int(self.v_flip) << 15)
        )


# Subtile layout within a 16x16 tile (chunk index -> pixel offset):
# chunk 0 = top-left (dx=0, dy=0 )
# chunk 1 = top-right (dx=8, dy=0 )
# chunk 2 = bottom-left (dx=0, dy=8 )
# chunk 3 = bottom-right(dx=8, dy=8 )
CHUNK_DX = [0, 8, 0, 8]
CHUNK_DY = [0, 0, 8, 8]


def decode_tile(
    data: Union[bytes, bytearray],
    tile_index: int,
) -> list[SubtileReference]:
    """Decode the four SubtileReferences for a 16x16 tile from the assembly table.

    Each tile occupies 8 bytes (4 x 2-byte little-endian words).
    Order: top-left, top-right, bottom-left, bottom-right.
    """
    base = tile_index * 8
    return [
        SubtileReference.from_word(data[base + i * 2] | (data[base + i * 2 + 1] << 8))
        for i in range(4)
    ]


def encode_tile(refs: list[SubtileReference]) -> bytes:
    """Encode four SubtileReferences to 8 bytes."""
    result = bytearray(8)
    for i, ref in enumerate(refs[:4]):
        w = ref.to_word()
        result[i * 2] = w & 0xFF
        result[i * 2 + 1] = (w >> 8) & 0xFF
    return bytes(result)


def build_priority_table(
    l12_asm: Union[bytes, bytearray],
    l3_asm: Union[bytes, bytearray, None],
    num_l12_tiles: int = 256,
    num_l3_tiles: int = 256,
) -> bytearray:
    """Build the priority table lookup used during map rendering.

    Returns a bytearray of length 0x1000 where:
      table[tile_index * 4 + subtile] = priority_bit (0 or 1)
      for L12 tiles (indices 0..num_l12_tiles-1)
      table[0x800 + tile_index * 4 + subtile] for L3 tiles (bit 9 stripped)
    """
    table = bytearray(0x1000)
    for tile_idx in range(num_l12_tiles):
        if tile_idx * 8 + 7 >= len(l12_asm):
            break
        for sub in range(4):
            word = (l12_asm[tile_idx * 8 + sub * 2]
                    | (l12_asm[tile_idx * 8 + sub * 2 + 1] << 8))
            table[tile_idx * 4 + sub] = (word >> 13) & 1

    if l3_asm:
        for tile_idx in range(num_l3_tiles):
            if tile_idx * 8 + 7 >= len(l3_asm):
                break
            for sub in range(4):
                word = (l3_asm[tile_idx * 8 + sub * 2]
                        | (l3_asm[tile_idx * 8 + sub * 2 + 1] << 8))
                table[0x800 + tile_idx * 4 + sub] = (word >> 13) & 1

    return table
