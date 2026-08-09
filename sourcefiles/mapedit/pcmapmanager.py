"""PcMapManager: load and save location/overworld map data via PC filesystem."""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from .mapmanager import MapManager, LocationProperties, OverworldProperties, TileAssemblyLayer
from .mapdata import LocationMap, OverworldMap, MapHeader


# ---------------------------------------------------------------------------
# Graphics buffer sizes
# ---------------------------------------------------------------------------

# PC L12 chips: 128 chips per bank × 32 bytes (SNES 4bpp planar) = 4096 bytes/bank.
# Slots 0–5 are regular banks; slot 7 maps to dest slot 6 (slot 6 = animated, skipped).
_PC_L12_BYTES_PER_BANK = 4096
_PC_L12_NUM_BANKS = 7
_PC_L12_GFX_BUFFER_SIZE = _PC_L12_NUM_BANKS * _PC_L12_BYTES_PER_BANK  # 28672

# PC L3 chips: 256 chips × 16 bytes (SNES 2bpp planar) = 4096 bytes.
_PC_L3_GFX_BUFFER_SIZE = 4096

# PC chip raster layout: all chip bank files store chips as a 128-pixel-wide
# raster (16 chips per row, each chip 8×8 pixels, 4bpp packed -> 2 pixels/byte).
_RASTER_BYTES_PER_ROW = 64   # 128 pixels ÷ 2 (4bpp packed)
_RASTER_CHIPS_PER_ROW = 16


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _raster_to_snes_4bpp(data: bytes | bytearray) -> bytearray:
    """Convert a 128-pixel-wide packed-4bpp raster to SNES 4bpp planar format.

    PC chip bank files store 8×8 chips arranged as a grid: 16 chips per row,
    each chip 8 pixels wide.  Each byte holds 2 pixels (high nibble = left
    pixel, low nibble = right pixel).

    The output has each chip contiguous at offset ``chip_index × 32`` bytes,
    matching what ``decode_4bpp_tile`` expects.
    """
    arr = np.frombuffer(data, dtype=np.uint8)
    num_raster_rows = len(arr) // _RASTER_BYTES_PER_ROW
    num_chip_rows = num_raster_rows // 8
    num_chips = num_chip_rows * _RASTER_CHIPS_PER_ROW

    arr_2d = arr[:num_raster_rows * _RASTER_BYTES_PER_ROW].reshape(
        num_raster_rows, _RASTER_BYTES_PER_ROW
    )

    # Build index arrays for vectorised extraction.
    chip_row_idx  = np.arange(num_chip_rows)         # (ncr,)
    pixel_row_idx = np.arange(8)                     # (8,)
    chip_col_idx  = np.arange(_RASTER_CHIPS_PER_ROW) # (cpr,)
    byte_sub_idx  = np.arange(4)                     # (4,)

    # raster_row_for[chip_row, pixel_row] = chip_row*8 + pixel_row
    raster_row_for = chip_row_idx[:, None] * 8 + pixel_row_idx[None, :]  # (ncr, 8)
    # byte_start_for[chip_col] = chip_col * 4
    byte_start_for = chip_col_idx * 4                                     # (cpr,)

    # packed[chip_row, pixel_row, chip_col, byte] = arr_2d[raster_row, byte_start+byte]
    packed = arr_2d[
        raster_row_for[:, :, None, None],                                        # (ncr,8,1,1)
        byte_start_for[None, None, :, None] + byte_sub_idx[None, None, None, :]  # (1,1,cpr,4)
    ]  # -> (ncr, 8, cpr, 4)

    # Rearrange to (num_chips, 8, 4) then unpack nibbles -> (num_chips, 8, 8) pixels.
    packed = packed.transpose(0, 2, 1, 3).reshape(num_chips, 8, 4)
    pixels = np.zeros((num_chips, 8, 8), dtype=np.uint8)
    pixels[:, :, 0::2] = packed >> 4
    pixels[:, :, 1::2] = packed & 0x0F

    # Pack into SNES 4bpp planar: 32 bytes per chip.
    shifts = np.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=np.uint8)
    out = np.zeros((num_chips, 32), dtype=np.uint8)
    for bp_idx, row_off in ((0, 0), (1, 1), (2, 16), (3, 17)):
        bp = (pixels >> bp_idx) & 1  # (num_chips, 8, 8)
        out[:, row_off:row_off + 16:2] = np.einsum('crs,s->cr', bp, shifts)

    return bytearray(out.tobytes())


def _raster_to_snes_2bpp(data: bytes | bytearray) -> bytearray:
    """Convert a 128-pixel-wide packed-4bpp raster to SNES 2bpp planar format.

    Same raster layout as ``_raster_to_snes_4bpp``.  Only the lower 2 bits of
    each pixel value are used.  Output has each chip contiguous at offset
    ``chip_index × 16`` bytes, matching what ``decode_2bpp_tile`` expects.
    """
    arr = np.frombuffer(data, dtype=np.uint8)
    num_raster_rows = len(arr) // _RASTER_BYTES_PER_ROW
    num_chip_rows = num_raster_rows // 8
    num_chips = num_chip_rows * _RASTER_CHIPS_PER_ROW

    arr_2d = arr[:num_raster_rows * _RASTER_BYTES_PER_ROW].reshape(
        num_raster_rows, _RASTER_BYTES_PER_ROW
    )

    chip_row_idx  = np.arange(num_chip_rows)
    pixel_row_idx = np.arange(8)
    chip_col_idx  = np.arange(_RASTER_CHIPS_PER_ROW)
    byte_sub_idx  = np.arange(4)

    raster_row_for = chip_row_idx[:, None] * 8 + pixel_row_idx[None, :]
    byte_start_for = chip_col_idx * 4

    packed = arr_2d[
        raster_row_for[:, :, None, None],
        byte_start_for[None, None, :, None] + byte_sub_idx[None, None, None, :]
    ]  # (ncr, 8, cpr, 4)

    packed = packed.transpose(0, 2, 1, 3).reshape(num_chips, 8, 4)
    pixels = np.zeros((num_chips, 8, 8), dtype=np.uint8)
    pixels[:, :, 0::2] = packed >> 4
    pixels[:, :, 1::2] = packed & 0x0F

    shifts = np.array([128, 64, 32, 16, 8, 4, 2, 1], dtype=np.uint8)
    out = np.zeros((num_chips, 16), dtype=np.uint8)
    for bp_idx, row_off in ((0, 0), (1, 1)):
        bp = (pixels >> bp_idx) & 1
        out[:, row_off:row_off + 16:2] = np.einsum('crs,s->cr', bp, shifts)

    return bytearray(out.tobytes())


def _pc_assembly_to_snes(data: bytes | bytearray, chip_offset: int = 0) -> bytearray:
    """Convert PC tile assembly (12 bytes/tile) to SNES format (8 bytes/tile).

    PC stores each of 4 corners per tile as 3 bytes:
      u16: bits 0–9 chip index, bit 10 flip-X, bit 11 flip-Y, bits 12–15 palette (4 bits)
      u8:  bit 0 priority

    SNES stores each corner as 2 bytes (one u16):
      bits 0–9 chip, bits 10–12 palette (3 bits), bit 13 priority,
      bit 14 flip-X, bit 15 flip-Y

    ``chip_offset`` is added to each chip index before encoding.  Pass 256 for
    location L12 tiles so the renderer's ``(index - 256) * 32`` offset lands at 0.
    PC's 4-bit palette field is truncated to 3 bits; CT maps use at most 8
    sub-palettes (indices 0–7), so the top bit is always zero in practice.
    """
    num_tiles = len(data) // 12
    out = bytearray(num_tiles * 8)
    for tile_idx in range(num_tiles):
        for corner in range(4):
            pc_off = tile_idx * 12 + corner * 3
            data1 = data[pc_off] | (data[pc_off + 1] << 8)
            data2 = data[pc_off + 2]
            chip     = (data1 & 0x3FF) + chip_offset
            flip_x   = (data1 >> 10) & 1
            flip_y   = (data1 >> 11) & 1
            palette  = (data1 >> 12) & 0x7  # truncate 4-bit PC value to 3 bits
            priority = data2 & 1
            snes_word = (
                (chip & 0x3FF)
                | (palette  << 10)
                | (priority << 13)
                | (flip_x   << 14)
                | (flip_y   << 15)
            )
            snes_off = tile_idx * 8 + corner * 2
            out[snes_off]     = snes_word & 0xFF
            out[snes_off + 1] = (snes_word >> 8) & 0xFF
    return out


# ---------------------------------------------------------------------------
# PcMapManager
# ---------------------------------------------------------------------------

class PcMapManager(MapManager):
    """Load and save location / overworld map data from a PC output directory."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self._loc_map_cache: dict[int, LocationMap] = {}
        self._ow_map_cache: dict[int, OverworldMap] = {}

    # ------------------------------------------------------------------
    # Location data
    # ------------------------------------------------------------------

    def get_location_props(self, loc_id: int) -> LocationProperties:
        mapinfo_path = self.base_path / f"Game/field/Mapinfo/mapinfo_{loc_id}.dat"
        if not mapinfo_path.exists():
            raise FileNotFoundError(f"Missing mapinfo for loc {loc_id} at {mapinfo_path}")

        data = mapinfo_path.read_bytes()
        music, l12, l12_asm, l3, pal, pal_anim, map_idx, chip_anim, script, unk, l, t, r, b = (
            struct.unpack("<10H4B", data[:24])
        )

        if l == 0x80:
            l, t, r, b = 0, 0, 255, 255  # 0x80 = disabled / full-scroll

        return LocationProperties(
            l12_tileset=l12,
            l3_tileset=l3,
            palette=pal,
            map_index=map_idx,
            scroll_left=l * 16,
            scroll_top=t * 16,
            scroll_right=r * 16 + 16,
            scroll_bottom=b * 16 + 16,
            l12_asm=l12_asm,
        )

    def get_location_map(self, loc_id: int) -> LocationMap:
        if loc_id in self._loc_map_cache:
            return self._loc_map_cache[loc_id]

        props = self.get_location_props(loc_id)
        maptable_path = self.base_path / f"Game/field/MapTable/MapTable_{props.map_index:04d}.dat"
        if not maptable_path.exists():
            raise FileNotFoundError(
                f"Missing MapTable for loc {loc_id} (map {props.map_index}) at {maptable_path}"
            )

        raw = maptable_path.read_bytes()
        loc_map = LocationMap()
        loc_map.header = MapHeader.from_pc_bytes(raw[:6])
        loc_map.from_pc_bytes(raw[6:])
        self._loc_map_cache[loc_id] = loc_map
        return loc_map

    def write_location_map(self, loc_id: int) -> None:
        if loc_id not in self._loc_map_cache:
            return
        loc_map = self._loc_map_cache[loc_id]
        props = self.get_location_props(loc_id)
        maptable_path = self.base_path / f"Game/field/MapTable/MapTable_{props.map_index:04d}.dat"
        out = bytearray()
        out.extend(loc_map.header.to_pc_bytes())
        out.extend(loc_map.to_pc_bytes())
        maptable_path.write_bytes(out)

    # ------------------------------------------------------------------
    # Location graphics
    # ------------------------------------------------------------------

    def get_l12_subtile_data(self, l12_tileset_idx: int) -> bytearray:
        """Assemble L12 subtile graphics for the given tileset index.

        Reads ``BGSetTable/bgsettable_{n}.dat`` to get up to 8 chip-bank indices,
        then converts each ``map_bin/cg{n}.bin`` bank from packed-4bpp raster to
        SNES 4bpp planar and places it at the correct offset in the output buffer.

        Slot 6 (animated tiles) is skipped.  Slot 7 maps to dest-slot 6 to keep
        chip indices contiguous.  Output is ``_PC_L12_GFX_BUFFER_SIZE`` (28672) bytes.
        """
        bgsettable_path = self.base_path / f"Game/field/BGSetTable/bgsettable_{l12_tileset_idx}.dat"
        if not bgsettable_path.exists():
            return bytearray(_PC_L12_GFX_BUFFER_SIZE)

        bank_indices = bgsettable_path.read_bytes()
        result = bytearray(_PC_L12_GFX_BUFFER_SIZE)

        for slot, bank_idx in enumerate(bank_indices[:8]):
            if bank_idx == 0xFF:
                continue
            if slot == 6:
                continue  # animated tiles — not needed for static rendering
            dest_slot = slot if slot < 6 else slot - 1  # slot 7 -> dest 6
            gfx_path = self.base_path / f"Game/field/map_bin/cg{bank_idx}.bin"
            if not gfx_path.exists():
                continue
            converted = _raster_to_snes_4bpp(gfx_path.read_bytes()[4:])  # skip 4-byte header
            dest_off = dest_slot * _PC_L12_BYTES_PER_BANK
            copy_len = min(len(converted), _PC_L12_BYTES_PER_BANK)
            result[dest_off:dest_off + copy_len] = converted[:copy_len]

        return result

    def get_l3_subtile_data(self, l3_tileset_idx: int) -> bytearray:
        path = self.base_path / f"Game/field/weather_bin/cg{l3_tileset_idx}.bin"
        if not path.exists():
            return bytearray(_PC_L3_GFX_BUFFER_SIZE)
        return _raster_to_snes_2bpp(path.read_bytes()[4:])

    def get_tile_assembly(self, index: int, layer: TileAssemblyLayer = TileAssemblyLayer.LAYER_12) -> bytearray:
        """Load tile assembly in native PC format (12 bytes/tile) for location layers, or
        SNES-converted format for overworld layers."""
        if layer == TileAssemblyLayer.LAYER_12:
            path = self.base_path / f"Game/field/ChipTable/ChipTable_{index:04d}.dat"
            if not path.exists():
                return bytearray()
            return bytearray(path.read_bytes())
        elif layer == TileAssemblyLayer.LAYER_3:
            path = self.base_path / f"Game/field/ChipTable/ChipTableBg3_{index:04d}.dat"
            if not path.exists():
                return bytearray()
            return bytearray(path.read_bytes())
        elif layer == TileAssemblyLayer.OVERWORLD_LAYER_12:
            path = self.base_path / f"Game/world/Chip/Chip_{index:04d}.dat"
            if not path.exists():
                return bytearray()
            return _pc_assembly_to_snes(path.read_bytes(), chip_offset=0)
        elif layer == TileAssemblyLayer.OVERWORLD_LAYER_3:
            return self._get_ow_l3_assembly(index)
        else:
            return bytearray()

    def _get_ow_l3_assembly(self, index: int) -> bytearray:
        """Load overworld L3 assembly from bankc6.bin (CT LZ77-compressed, SNES format)."""
        bank_path = self.base_path / "Game/common/bankc6.bin"
        if not bank_path.exists():
            return bytearray()
        data = bank_path.read_bytes()
        start = 0xFF40 + index * 3
        offset = int.from_bytes(data[start:start + 2], byteorder='little')
        from sourcefiles.jetsoftime.ctdecompress import decompress
        return bytearray(decompress(data, offset)[0])

    @property
    def pc_assembly_format(self) -> bool:
        return True

    @property
    def loc_l12_chip_vram_offset(self) -> int:
        # PC ChipTable files store chip indices starting at 0, not at VRAM tile 256.
        return 0

    @property
    def palette_field_shift(self) -> int:
        # PC tiles actively use palette field 0 (PC sub-palette 0 has real colors).
        # The renderer maps slot s to base = (s + 0) * 16, so field 0 -> base 0.
        return 0

    def get_palette_data(self, palette_idx: int) -> bytearray:
        """Load location palette as 16 sub-palettes × 15 colors × 2 bytes (480 bytes).

        PC palette files are 2 header bytes + 512 data bytes (256 colors × 2 bytes =
        16 sub-palettes × 16 colors × 2 bytes).

        The renderer expects sub-palette s at byte offset s * 30 (15 BGR555 words,
        color 0 omitted).  With palette_field_shift = 0, sub-palette slot s maps to
        renderer base = s * 16, so palette field p directly selects sub-palette p.

        All 16 sub-palettes are exported because PC tiles use the full 4-bit palette
        field (values 0–15); fields 8–15 reference sub-palettes 8–15.
        """
        path = self.base_path / f"Game/field/palette_bin/plt{palette_idx}.bin"
        if not path.exists():
            return bytearray(480)
        pc_colors = path.read_bytes()[2:514]  # skip 2-byte header; 256 colors × 2 bytes
        pal_out = bytearray(480)
        for sp in range(16):
            src = sp * 32 + 2  # PC sub-palette sp, color 1 (+2 to skip color 0)
            dst = sp * 30      # 15 colors × 2 bytes = 30 bytes per sub-palette
            pal_out[dst:dst + 30] = pc_colors[src:src + 30]
        return pal_out

    # ------------------------------------------------------------------
    # Overworld data
    # ------------------------------------------------------------------

    def get_overworld_map(self, ow_index: int) -> OverworldMap:
        if ow_index in self._ow_map_cache:
            return self._ow_map_cache[ow_index]

        props = self.get_overworld_props(ow_index)
        map_path = self.base_path / f"Game/world/Map/Map_{props.map_slot:04d}.dat"
        if not map_path.exists():
            raise FileNotFoundError(f"Missing overworld map for ow {ow_index} at {map_path}")

        ow_map = OverworldMap()
        ow_map.load(map_path.read_bytes())
        self._ow_map_cache[ow_index] = ow_map
        return ow_map

    def write_overworld_map(self, ow_index: int) -> None:
        if ow_index not in self._ow_map_cache:
            return
        ow_map = self._ow_map_cache[ow_index]
        props = self.get_overworld_props(ow_index)
        map_path = self.base_path / f"Game/world/Map/Map_{props.map_slot:04d}.dat"
        map_path.write_bytes(ow_map.raw_data[:OverworldMap.DATA_SIZE])
        ow_map.modified = False

    def get_overworld_props(self, ow_index: int) -> OverworldProperties:
        bank_path = self.base_path / "Game/common/bankc6.bin"
        if not bank_path.exists():
            raise FileNotFoundError("Missing bankc6.bin")
        data = bank_path.read_bytes()
        start = 0xFD10 + ow_index * 23
        rec = data[start:start + 23]
        return OverworldProperties(
            tileset=list(rec[0:8]),
            l3_tileset=rec[8],
            palette=rec[10],
            l12_asm=rec[16],
            map_slot=rec[17],
            l3_asm=rec[20],
        )

    def get_ow_l12_subtile_data(self, tileset_slots: list) -> bytearray:
        out = bytearray()
        for i in range(4):
            if i < len(tileset_slots) and tileset_slots[i] < 255:
                path = self.base_path / f"Game/world/map_bin/cg{tileset_slots[i]}.bin"
                if path.exists():
                    out.extend(_raster_to_snes_4bpp(path.read_bytes()[4:]))
        return out

    def get_ow_l3_subtile_data(self, l3_ts: int) -> bytearray:
        path = self.base_path / f"Game/world/map_bin/cg{l3_ts}.bin"
        if not path.exists():
            return bytearray(_PC_L3_GFX_BUFFER_SIZE)
        return _raster_to_snes_2bpp(path.read_bytes()[4:])

    def get_ow_palette_data(self, pal_idx: int) -> bytearray:
        path = self.base_path / f"Game/world/plt_bin/plt{pal_idx}.bin"
        if not path.exists():
            return bytearray(512)
        return bytearray(path.read_bytes()[2:514])

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def invalidate(self) -> None:
        self._loc_map_cache.clear()
        self._ow_map_cache.clear()
