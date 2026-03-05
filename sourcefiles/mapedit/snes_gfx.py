"""SNES graphics decoding: 2bpp/4bpp tiles and BGR555 palettes.
"""
from __future__ import annotations
from typing import Union

import numpy as np


def decode_4bpp_tile(data: Union[bytes, bytearray], offset: int) -> np.ndarray:
    """Decode one 8x8 SNES 4bpp tile starting at data[offset].

    Format: 32 bytes per tile.
      Rows 0-7: bitplane-0 and bitplane-1 interleaved (2 bytes per row).
      Rows 0-7 (offset+16): bitplane-2 and bitplane-3 interleaved.

    Returns an (8, 8) uint8 array of palette indices 0-15.
    """
    tile = np.zeros((8, 8), dtype=np.uint8)
    for row in range(8):
        bp0 = data[offset + row * 2]
        bp1 = data[offset + row * 2 + 1]
        bp2 = data[offset + 16 + row * 2]
        bp3 = data[offset + 16 + row * 2 + 1]
        for col in range(8):
            bit = 7 - col
            p = (
                ((bp0 >> bit) & 1)
                | (((bp1 >> bit) & 1) << 1)
                | (((bp2 >> bit) & 1) << 2)
                | (((bp3 >> bit) & 1) << 3)
            )
            tile[row, col] = p
    return tile


def decode_2bpp_tile(data: Union[bytes, bytearray], offset: int) -> np.ndarray:
    """Decode one 8x8 SNES 2bpp tile starting at data[offset].

    Format: 16 bytes per tile.
      Each row: 2 bytes, bitplane-0 low then bitplane-1 high.

    Returns an (8, 8) uint8 array of palette indices 0-3.
    """
    tile = np.zeros((8, 8), dtype=np.uint8)
    for row in range(8):
        lo = data[offset + row * 2]
        hi = data[offset + row * 2 + 1]
        for col in range(8):
            bit = 7 - col
            p = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
            tile[row, col] = p
    return tile


def decode_bgr555_palette(
    data: Union[bytes, bytearray],
    offset: int,
    num_colors: int,
) -> np.ndarray:
    """Convert SNES BGR555 words to an RGBA uint8 array of shape (num_colors, 4).

    Each BGR555 word is 2 bytes little-endian:
      bits 0-4: red (x 8 -> 0-248)
      bits 5-9: green (x 8)
      bits 10-14: blue (x 8)
    Color 0 is always transparent (alpha = 0).
    """
    palette = np.zeros((num_colors, 4), dtype=np.uint8)
    for i in range(num_colors):
        word = data[offset + i * 2] | (data[offset + i * 2 + 1] << 8)
        r = (word & 0x001F) << 3
        g = (word & 0x03E0) >> 2
        b = (word & 0x7C00) >> 7
        palette[i] = [r, g, b, 255]
    palette[0, 3] = 0 # color index 0 is transparent
    return palette


def apply_flip(tile: np.ndarray, h_flip: bool, v_flip: bool) -> np.ndarray:
    """Return a flipped copy of an 8x8 tile array."""
    if h_flip:
        tile = tile[:, ::-1]
    if v_flip:
        tile = tile[::-1, :]
    return tile
