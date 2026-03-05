"""Location and overworld map data models."""
from __future__ import annotations

from dataclasses import dataclass
import enum
from typing import Union

class Layer(enum.IntEnum):
    L1 = 0
    L2 = 1
    L3 = 2

@dataclass
class MapHeader:
    """Decoded 6-byte location map header."""
    l1_width: int = 16
    l1_height: int = 16
    l2_width: int = 16
    l2_height: int = 16
    l3_width: int = 16
    l3_height: int = 16
    l1_scroll: int = 0 # 0-7 (bits 4-6 of byte 1)
    l2_scroll: int = 0 # 0-255 (byte 2)
    l3_scroll: int = 0 # 0-255 (byte 3)
    draw_l3: bool = False
    priority: int = 0 # byte 4 bitmask
    color_fx: int = 0 # byte 5 bitmask

    # byte 4 convenience properties
    @property
    def l1_main(self) -> bool: return bool(self.priority & 0x01)
    @property
    def l2_main(self) -> bool: return bool(self.priority & 0x02)
    @property
    def l3_main(self) -> bool: return bool(self.priority & 0x04)
    @property
    def sprites_main(self)-> bool: return bool(self.priority & 0x08)
    @property
    def l1_sub(self) -> bool: return bool(self.priority & 0x10)
    @property
    def l2_sub(self) -> bool: return bool(self.priority & 0x20)
    @property
    def l3_sub(self) -> bool: return bool(self.priority & 0x40)
    @property
    def sprites_sub(self) -> bool: return bool(self.priority & 0x80)

    # byte 5 convenience properties
    @property
    def l1_translucent(self) -> bool: return bool(self.color_fx & 0x01)
    @property
    def l2_translucent(self) -> bool: return bool(self.color_fx & 0x02)
    @property
    def l3_translucent(self) -> bool: return bool(self.color_fx & 0x04)
    @property
    def subtractive(self) -> bool: return bool(self.color_fx & 0x80)
    @property
    def half_color(self) -> bool: return bool(self.color_fx & 0x40)

    @staticmethod
    def decode(data: Union[bytes, bytearray]) -> MapHeader:
        """Decode from bytes[0:6]"""
        b0, b1, b2, b3, b4, b5 = (
            data[0], data[1], data[2], data[3], data[4], data[5]
        )
        return MapHeader(
            l1_width = ((b0 & 0x03) + 1) << 4,
            l1_height = ((b0 & 0x0C) + 4) << 2,
            l2_width = (b0 & 0x30) + 16,
            l2_height = ((b0 & 0xC0) + 64) >> 2,
            l3_width = ((b1 & 0x03) + 1) << 4,
            l3_height = ((b1 & 0x0C) + 4) << 2,
            l1_scroll = (b1 & 0x70) >> 4,
            draw_l3 = bool(b1 & 0x80),
            l2_scroll = b2,
            l3_scroll = b3,
            priority = b4,
            color_fx = b5,
        )

    def encode(self) -> bytes:
        """Encode back to 6 bytes."""
        b = (self.l1_width >> 4) - 1
        b2 = (self.l1_height >> 4) - 1
        b3 = (self.l2_width >> 4) - 1
        b4 = (self.l2_height >> 4) - 1
        b5 = (self.l3_width >> 4) - 1
        b6 = (self.l3_height >> 4) - 1
        byte0 = (b & 0x03) | ((b2 & 0x03) << 2) | ((b3 & 0x03) << 4) | ((b4 & 0x03) << 6)
        byte1 = (
            (b5 & 0x03)
            | ((b6 & 0x03) << 2)
            | ((self.l1_scroll & 0x07) << 4)
            | (int(self.draw_l3) << 7)
        )
        return bytes([byte0, byte1, self.l2_scroll & 0xFF,
                      self.l3_scroll & 0xFF, self.priority & 0xFF,
                      self.color_fx & 0xFF])


def rle_decompress(
    data: Union[bytes, bytearray],
    src_offset: int,
    dest_size: int,
) -> bytearray:
    """Decompress CT RunLength-encoded tile property data (triplet-level RLE).

    This codec operates on 3-byte records (one record per tile).
    Decision is based on bit 7 of the first byte of each record:

      Bit 7 clear (byte0 < 0x80):
        Literal - consume 3 bytes, copy them as-is.

      Bit 7 set (byte0 >= 0x80):
        Run - consume 4 bytes: [byte0 | byte1 | byte2 | count]
          Output the triplet (byte0 & 0x7F, byte1, byte2) repeated count times.
          count == 0 is treated as 256.
    """
    dest = bytearray(dest_size)
    src = src_offset
    dst = 0
    data_len = len(data)
    while dst < dest_size and src < data_len:
        b0 = data[src]
        if b0 & 0x80:
            # Format: [byte0 | 0x80] [byte1] [byte2] [count]
            # Run: 4-byte command
            if src + 3 >= data_len:
                break
            b1 = data[src + 1]
            b2 = data[src + 2]
            count = data[src + 3]
            if count == 0:
                count = 256
            src += 4
            for _ in range(count):
                if dst + 2 >= dest_size:
                    break
                dest[dst] = b0 & 0x7F
                dest[dst + 1] = b1
                dest[dst + 2] = b2
                dst += 3
        else:
            # Format: [byte0_literal] [byte1] [byte2]
            # Literal: 3-byte record
            if src + 2 >= data_len:
                break
            dest[dst] = b0
            dest[dst + 1] = data[src + 1]
            dest[dst + 2] = data[src + 2]
            src += 3
            dst += 3
    return dest


def rle_compress(data: Union[bytes, bytearray]) -> bytearray:
    """Compress tile property data with CT triplet-level RunLength encoding.

    Operates on 3-byte records. Greedy: prefer runs of 2+ identical triplets.

    Encoding rules:
      - Identical triplets (run >= 2): emit 4-byte run command
          [byte0 | 0x80] [byte1] [byte2] [count] (count capped at 255)
      - Triplet where byte0 has bit 7 set (can't be a literal): emit as run
          of 1: [byte0] [byte1] [byte2] [0x01] - byte0 already has bit 7 set
      - Otherwise: emit 3-byte literal triplet.
    """
    result = bytearray()
    n = len(data)
    i = 0
    while i + 2 < n:
        b0, b1, b2 = data[i], data[i + 1], data[i + 2]

        # Count identical triplets ahead
        run_len = 1
        while (i + (run_len + 1) * 3 <= n
               and data[i + run_len * 3] == b0
               and data[i + run_len * 3 + 1] == b1
               and data[i + run_len * 3 + 2] == b2
               and run_len < 255):
            run_len += 1

        if run_len >= 2 or (b0 & 0x80):
            # Format: [byte0 | 0x80] [byte1] [byte2] [count]
            # Run encoding: count capped at 255; emit one run at a time if > 255
            count = min(run_len, 255)
            result.append(b0 | 0x80)
            result.append(b1)
            result.append(b2)
            result.append(count)
            i += count * 3
        else:
            # Format: [byte0_literal] [byte1] [byte2]
            # Literal triplet
            result.append(b0)
            result.append(b1)
            result.append(b2)
            i += 3
    return result


class LocationMap:
    """Decompressed location map: header + 3 tile layers + tile properties."""

    MAP_DATA_MAX = 24582
    TILE_PROP_MAX = 3*64*64

    def __init__(self) -> None:
        self.header = MapHeader()
        self.raw_data = bytearray(self.MAP_DATA_MAX)
        self.tile_props = bytearray(self.TILE_PROP_MAX)
        self._layer_offset = [6, 0, 0]
        self._max_width = 16
        self._max_height = 16
        self._widths = [16, 16, 16]
        self._heights = [16, 16, 16]
        self._tile_prop_offset = 6

    def load(self, data: Union[bytes, bytearray], is_beta: bool = False) -> None:
        """Populate from a decompressed map data block."""
        self.raw_data = bytearray(data[:self.MAP_DATA_MAX])
        if len(self.raw_data) < self.MAP_DATA_MAX:
            self.raw_data += b'\x00' * (self.MAP_DATA_MAX - len(self.raw_data))

        self.header = MapHeader.decode(self.raw_data)
        self._layer_offset[0] = 6
        self._layer_offset[1] = 6 + self.header.l1_width * self.header.l1_height
        self._layer_offset[2] = self._layer_offset[1] + self.header.l2_width * self.header.l2_height

        self._max_width = max(self.header.l1_width, self.header.l2_width)
        self._max_height = max(self.header.l1_height, self.header.l2_height)
        self._widths = [self.header.l1_width, self.header.l2_width, self.header.l3_width]
        self._heights = [self.header.l1_height, self.header.l2_height, self.header.l3_height]

        tile_prop_offset = self._layer_offset[2]
        if self.header.draw_l3:
            tile_prop_offset += self.header.l3_width * self.header.l3_height
        self._tile_prop_offset = tile_prop_offset

        dest_size = 3 * self._max_width * self._max_height
        if is_beta:
            count = self._max_width * self._max_height
            for i in range(min(count, (len(self.raw_data) - tile_prop_offset))):
                self.tile_props[i * 3] = self.raw_data[tile_prop_offset + i]
                self.tile_props[i * 3 + 1] = self.raw_data[tile_prop_offset + i + count]
                self.tile_props[i * 3 + 2] = self.raw_data[tile_prop_offset + i + count * 2]
        else:
            self.tile_props = rle_decompress(self.raw_data, tile_prop_offset, dest_size)

        # Zero out the tile property region from raw_data (it lives in tile_props now)
        self.raw_data[tile_prop_offset:] = b'\x00' * (self.MAP_DATA_MAX - tile_prop_offset)

    def to_bytes(self, is_beta: bool = False) -> bytearray:
        """Serialize back to a bytearray suitable for CT compression."""
        result = bytearray(self.raw_data[:self._tile_prop_offset])
        if is_beta:
            count = self._max_width * self._max_height
            for i in range(count):
                result.append(self.tile_props[i * 3])
            for i in range(count):
                result.append(self.tile_props[i * 3 + 1])
            for i in range(count):
                result.append(self.tile_props[i * 3 + 2])
        else:
            used = 3 * self._max_width * self._max_height
            result.extend(rle_compress(self.tile_props[:used]))
        return result

    def get_tile(self, layer: Layer | int, x: int, y: int) -> int:
        """Return the tile index for (layer, x, y).

        L1/L2 -> 9-bit index (bit 8 from tile_props).
        L3 -> 8-bit index OR'd with 0x200.
        """
        if x >= self._widths[layer] or y >= self._heights[layer]:
            return 0
        index = self._layer_offset[layer] + y * self._widths[layer] + x
        val = self.raw_data[index]
        if layer == Layer.L3:
            return val | 0x200
        prop_idx = 3 * (y * self._max_width + x)
        if layer == Layer.L1:
            return val | ((self.tile_props[prop_idx] & 0x01) << 8)
        return val | (((self.tile_props[prop_idx] & 0x02) >> 1) << 8)

    def set_tile(self, layer: Layer | int, x: int, y: int, value: int) -> None:
        """Write a tile value. value is 9-bit for L1/L2, 8-bit for L3."""
        if x >= self._widths[layer] or y >= self._heights[layer]:
            return
        idx = self._layer_offset[layer] + y * self._widths[layer] + x
        # Low 8 bits of the tile index go directly into the raw layer data.
        self.raw_data[idx] = value & 0xFF

        # L3 tile indices are 8-bit only; no 9th bit to store.
        if layer == Layer.L3:
            return

        # The 9th bit (bit 8) of L1/L2 tile indices is packed into the first
        # byte of the tile's 3-byte tile_props record:
        # bit 0 = L1 high bit
        # bit 1 = L2 high bit
        # This mirrors the ROM layout and is the inverse of get_tile().
        prop_idx = 3 * (y * self._max_width + x)
        high_bit = (value >> 8) & 0x01
        if layer == Layer.L1:
            # Write high_bit into bit 0; preserve all other bits.
            self.tile_props[prop_idx] = (self.tile_props[prop_idx] & 0xFE) | high_bit
        else:
            # Write high_bit into bit 1; preserve all other bits.
            self.tile_props[prop_idx] = (self.tile_props[prop_idx] & 0xFD) | (high_bit << 1)

    @property
    def max_width(self) -> int:
        return self._max_width

    @property
    def max_height(self) -> int:
        return self._max_height

    @property
    def layer_offset(self) -> list[int]:
        return list(self._layer_offset)


class OverworldMap:
    """Decompressed overworld map: 96x64 tiles, 2 layers."""

    WIDTH = 96
    HEIGHT = 64
    DATA_SIZE = WIDTH * HEIGHT * 2 # 12288 bytes

    # Layer 1 at offset 0, layer 2 at offset WIDTH*HEIGHT = 6144.
    _LAYER_OFFSET = [0, WIDTH * HEIGHT]

    def __init__(self) -> None:
        self.raw_data = bytearray(self.DATA_SIZE)

    def load(self, data: Union[bytes, bytearray]) -> None:
        self.raw_data = bytearray(data[:self.DATA_SIZE])
        if len(self.raw_data) < self.DATA_SIZE:
            self.raw_data += b'\x00' * (self.DATA_SIZE - len(self.raw_data))

    def get_tile(self, layer: int, x: int, y: int) -> int:
        if layer >= len(self._LAYER_OFFSET) or x >= self.WIDTH or y >= self.HEIGHT:
            return 0
        idx = self._LAYER_OFFSET[layer] + y * self.WIDTH + x
        val = self.raw_data[idx]
        # Layer 2 always has bit 8 set
        if layer == 1:
            return val | 0x100
        return val

    def set_tile(self, layer: int, x: int, y: int, value: int) -> None:
        if layer >= len(self._LAYER_OFFSET) or x >= self.WIDTH or y >= self.HEIGHT:
            return
        idx = self._LAYER_OFFSET[layer] + y * self.WIDTH + x
        self.raw_data[idx] = value & 0xFF
