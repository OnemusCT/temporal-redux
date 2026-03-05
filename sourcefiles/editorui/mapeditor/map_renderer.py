"""Core map rendering engine.

Implements the 6-pass priority-based render algorithm using NumPy + QImage.

Pass order: [L3, L2, L1, L2, L1, L3]
  passes 0-2 -> sub-screen layers (priority bit clear)
  passes 3-5 -> main-screen layers (priority bit set)
"""
from __future__ import annotations

import numpy as np

from PyQt6.QtGui import QImage
from mapedit.snes_gfx import (
    decode_4bpp_tile, decode_2bpp_tile, decode_bgr555_palette, apply_flip,
)
from mapedit.tile_assembly import decode_tile, SubtileReference, build_priority_table
from mapedit.mapdata import LocationMap, OverworldMap

_L3_GRAPHICS_BYTES = 4096

_L12_TILE_ASSEMBLY_BYTES = 4096

_PASS_LAYER = [2, 1, 0, 1, 0, 2]
# Passes 0-2 are sub-screen; 3-5 are main-screen.
_PASS_IS_MAIN = [False, False, False, True, True, True]

# Tile/subtile geometry
_TILE_PIXELS = 16 # tile dimension in pixels (16x16)
_SUBTILE_PIXELS = 8 # subtile dimension in pixels (8x8)

_L12_SUBTILE_GRAPHICS_BYTES = 28672

# Tile assembly table
_BYTES_PER_TILE_ASM = 8 # bytes per tile assembly entry (4 subtile words x 2 bytes)
_MAX_L12_TILES = 512 # 9-bit index -> max 512 L12 tiles
_MAX_L3_TILES = 256 # 8-bit index -> max 256 L3 tiles

# Tile index bit flags
_L3_TILE_FLAG = 0x200 # set on tile_index to identify an L3 tile

# Priority table
_L3_PRIORITY_BASE = 0x800 # _prior_tbl base offset for L3 tile entries

# Graphics addressing
_LOC_L12_VRAM_TILE = 256 # CT loads location L12 gfx starting at VRAM tile 256
_OVERWORLD_MAX_L3_TILESET = 42 # Overworld L3 tileset slots 0-41 are valid; >= 42 means no L3 layer

_COLORS_PER_SUBPALETTE = 15
_BYTES_PER_BGR555 = 2

class MapRenderer:
    """Renders a Chrono Trigger location or overworld map to a QImage.

    Usage:
        renderer = MapRenderer()
        renderer.load_location_data(mgr, loc_props)
        img = renderer.render_map(loc_map, layers_visible=[True,True,True])
    """

    def __init__(self) -> None:
        self._tile_cache: dict[int, np.ndarray] = {} # tile_idx -> (16,16,4) RGBA
        self._l12_gfx: bytes | bytearray = b''
        self._l3_gfx: bytes | bytearray = b''
        self._l12_asm: bytes | bytearray = b''
        self._l3_asm: bytes | bytearray | None = None
        self._palette: np.ndarray = np.zeros((128, 4), dtype=np.uint8)
        self._priority_tbl: bytearray = bytearray(0x1000)
        self._is_location = True

    def load_location_data(self, mgr, loc_props: dict) -> None:
        """Load all rendering resources for a location.

        *mgr* is a MapManager; *loc_props* is the dict returned by
        MapManager.get_location_props().
        """
        self._is_location = True
        l12_ts = loc_props['l12_tileset']
        l3_ts = loc_props['l3_tileset']
        pal_idx = loc_props['palette']

        try:
            self._l12_gfx = mgr.get_l12_subtile_data(l12_ts)
        except (ValueError, IndexError):
            self._l12_gfx = b'\x00' * 24640

        # L3 tileset indices >= 23 mean "no L3 layer"
        try:
            self._l3_gfx = mgr.get_l3_subtile_data(l3_ts)
        except (ValueError, IndexError):
            self._l3_gfx = b'\x00' * 4096

        try:
            self._l12_asm = mgr.get_tile_assembly(l12_ts, 'l12')
        except (ValueError, IndexError):
            self._l12_asm = b'\x00' * 4096

        try:
            self._l3_asm = mgr.get_tile_assembly(l3_ts, 'l3')
        except (ValueError, IndexError, RuntimeError):
            self._l3_asm = None

        # Build a 128-entry RGBA palette table mirroring the SNES CGRAM layout:
        #
        # indices 0-15 : palette shift 0 = CGRAM backdrop, always transparent (left as zeros)
        # indices 16-31 : palette shift 1 = ROM sub-palette 0
        # indices 32-47 : palette shift 2 = ROM sub-palette 1
        # ...
        # indices 112-127 : palette shift 7 = ROM sub-palette 6
        #
        # Each sub-palette entry occupies 16 slots; slot 0 within each entry is
        # always transparent (CGRAM hardware rule), so ROM colors 1-15 are stored
        # at base+1..base+15. ROM palette data is 15 BGR555 words per sub-palette
        # (color 0 is not stored because it is never used).
        pal_raw = mgr.get_palette_data(pal_idx)
        palette = np.zeros((128, 4), dtype=np.uint8)
        # There are at most 7 subpalettes
        num_subpalettes = min(7, len(pal_raw) // (_COLORS_PER_SUBPALETTE * _BYTES_PER_BGR555))
        for subpalette in range(num_subpalettes):
            decoded = decode_bgr555_palette(pal_raw, subpalette * _COLORS_PER_SUBPALETTE * _BYTES_PER_BGR555, _COLORS_PER_SUBPALETTE)
            decoded[:, 3] = 255 # restore alpha: all 15 ROM colors are opaque
            base = (subpalette + 1) * 16 # shift 1-7 maps to CGRAM rows 1-7 (16 entries each)
            palette[base + 1 : base + 16] = decoded # color 0 slot stays transparent
        self._palette = palette
        self._priority_tbl = build_priority_table(
            self._l12_asm, self._l3_asm,
            num_l12_tiles=min(len(self._l12_asm) // _BYTES_PER_TILE_ASM, _MAX_L12_TILES),
            num_l3_tiles=min(len(self._l3_asm) // _BYTES_PER_TILE_ASM if self._l3_asm else _MAX_L3_TILES, _MAX_L3_TILES),
        )
        self._tile_cache.clear()

    def load_overworld_data(self, mgr, overworld_index: int) -> None:
        """Load rendering resources for an overworld map."""
        self._is_location = False

        props = mgr.get_overworld_props(overworld_index)

        # L12 subtile graphics (28672 bytes)
        try:
            self._l12_gfx = mgr.get_ow_l12_subtile_data(props['tileset'])
        except (ValueError, IndexError):
            self._l12_gfx = b'\x00' * _L12_SUBTILE_GRAPHICS_BYTES

        # L12 tile assembly
        try:
            self._l12_asm = mgr.get_tile_assembly(props['l12_asm'], 'ow_l12')
        except (ValueError, IndexError):
            self._l12_asm = b'\x00' * _L12_TILE_ASSEMBLY_BYTES

        # Palette: 16 sub-palettes x 16 colors (BGR555) -> 256-entry RGBA table
        num_palettes = 16
        num_colors = 16
        try:
            pal_raw = mgr.get_ow_palette_data(props['palette'])
            palette = np.zeros((num_palettes * num_colors, 4), dtype=np.uint8)
            for sp in range(num_palettes):
                decoded = decode_bgr555_palette(pal_raw, sp * num_colors * 2, num_colors)
                # Color 0 of each sub-palette is transparent (already set by decode_bgr555_palette)
                palette[sp * num_colors : sp * num_colors + num_colors] = decoded
            self._palette = palette
        except (ValueError, IndexError):
            self._palette = np.zeros((256, 4), dtype=np.uint8)

        # L3 subtile graphics (4096 bytes, optional)
        l3_ts = props['l3_tileset']
        try:
            if l3_ts < _OVERWORLD_MAX_L3_TILESET:
                self._l3_gfx = mgr.get_ow_l3_subtile_data(l3_ts)
            else:
                self._l3_gfx = b'\x00' * _L3_GRAPHICS_BYTES
        except (ValueError, IndexError):
            self._l3_gfx = b'\x00' * _L3_GRAPHICS_BYTES

        # L3 tile assembly (optional)
        try:
            self._l3_asm = mgr.get_tile_assembly(props['l3_asm'], 'ow_l3')
        except (ValueError, IndexError):
            self._l3_asm = None

        self._priority_tbl = build_priority_table(
            self._l12_asm, self._l3_asm,
            num_l12_tiles=min(len(self._l12_asm) // _BYTES_PER_TILE_ASM, _MAX_L12_TILES),
            num_l3_tiles=min(len(self._l3_asm) // _BYTES_PER_TILE_ASM if self._l3_asm else _MAX_L3_TILES, _MAX_L3_TILES),
        )
        self._tile_cache.clear()

    def _subtile_rgba(self, ref: SubtileRef, is_l3: bool) -> np.ndarray:
        """Decode one 8x8 subtile to (8,8,4) RGBA using the current palette."""
        if is_l3:
            gfx_offset = ref.index * 16
            gfx = self._l3_gfx
            if gfx_offset + 16 > len(gfx):
                return np.zeros((_SUBTILE_PIXELS, _SUBTILE_PIXELS, 4), dtype=np.uint8)
            pixels = decode_2bpp_tile(gfx, gfx_offset)
            pal_off = ref.palette * 4 # 2bpp uses 4-color sub-palettes
        else:
            # Location maps: CT loads L12 gfx at VRAM tile 256 -> offset = (index-256)*32
            # Overworld maps: gfx loaded at VRAM tile 0 -> offset = index*32 (no subtraction)
            if self._is_location:
                gfx_offset = (ref.index - _LOC_L12_VRAM_TILE) * 32
            else:
                gfx_offset = ref.index * 32
            gfx = self._l12_gfx
            if gfx_offset < 0 or gfx_offset + 32 > len(gfx):
                return np.zeros((_SUBTILE_PIXELS, _SUBTILE_PIXELS, 4), dtype=np.uint8)
            pixels = decode_4bpp_tile(gfx, gfx_offset)
            pal_off = ref.palette * 16 # 4bpp uses 16-color sub-palettes

        pixels = apply_flip(pixels, ref.h_flip, ref.v_flip)

        rgba = np.zeros((_SUBTILE_PIXELS, _SUBTILE_PIXELS, 4), dtype=np.uint8)
        mask = pixels > 0
        if np.any(mask):
            raw_idx = pal_off + pixels.astype(np.intp)
            np.clip(raw_idx, 0, len(self._palette) - 1, out=raw_idx)
            rgba[mask] = self._palette[raw_idx[mask]]
        return rgba

    def render_tile(self, tile_index: int) -> np.ndarray:
        """Return a (16,16,4) RGBA array for one 16x16 tile."""
        if tile_index in self._tile_cache:
            return self._tile_cache[tile_index]

        canvas = np.zeros((_TILE_PIXELS, _TILE_PIXELS, 4), dtype=np.uint8)
        is_l3 = bool(tile_index & _L3_TILE_FLAG)

        if is_l3:
            asm = self._l3_asm
            idx = tile_index & 0xFF
        else:
            asm = self._l12_asm
            idx = tile_index

        if asm is None or len(asm) < idx * _BYTES_PER_TILE_ASM + _BYTES_PER_TILE_ASM:
            self._tile_cache[tile_index] = canvas
            return canvas

        refs = decode_tile(asm, idx)
        # Subtile layout: 0=top-left, 1=top-right, 2=bottom-left, 3=bottom-right
        # Pairs are (col_off, row_off) -- i.e. (x, y) into the 16x16 canvas.
        positions = [(0, 0), (_SUBTILE_PIXELS, 0), (0, _SUBTILE_PIXELS), (_SUBTILE_PIXELS, _SUBTILE_PIXELS)]
        for chunk, (col_off, row_off) in enumerate(positions):
            ref = refs[chunk]
            sub = self._subtile_rgba(ref, is_l3)
            canvas[row_off:row_off + _SUBTILE_PIXELS, col_off:col_off + _SUBTILE_PIXELS] = np.where(
                sub[:, :, 3:4] > 0, sub, canvas[row_off:row_off + _SUBTILE_PIXELS, col_off:col_off + _SUBTILE_PIXELS]
            )

        self._tile_cache[tile_index] = canvas
        return canvas

    def render_map(
        self,
        map_data, # LocationMap or OverworldMap
        layers_visible: list[bool] = None,
    ) -> 'QImage':
        """Render the entire map to a QImage.

        *map_data* is a LocationMap or OverworldMap.
        *layers_visible*: list[bool] of length 3 (default all True).
        """
        if layers_visible is None:
            layers_visible = [True, True, True]

        is_loc = isinstance(map_data, LocationMap)

        if is_loc:
            max_width = map_data.max_width
            max_height = map_data.max_height
        else:
            max_width, max_height = OverworldMap.WIDTH, OverworldMap.HEIGHT

        canvas = np.zeros((max_height * _TILE_PIXELS, max_width * _TILE_PIXELS, 4), dtype=np.uint8)

        # 6-pass render: [L3,L2,L1,L2,L1,L3], passes 0-2 sub-screen (priority=0),
        # passes 3-5 main-screen (priority=1). Every layer participates in both
        # sub and main passes - bLSub/bLMain are SNES color-math flags, not
        # tile-visibility flags. Only the per-subtile priority bit gates passes.
        for pass_idx in range(6):
            layer = _PASS_LAYER[pass_idx]
            is_main = _PASS_IS_MAIN[pass_idx]

            if not layers_visible[layer]:
                continue
            # Overworld only has 2 layers (L1=0, L2=1); skip L3 passes.
            if not is_loc and layer == 2:
                continue

            if is_loc:
                h = map_data.header
                layer_widths = [h.l1_width, h.l2_width, h.l3_width]
                layer_heights = [h.l1_height, h.l2_height, h.l3_height]
            else:
                layer_widths = [OverworldMap.WIDTH] * 3
                layer_heights = [OverworldMap.HEIGHT] * 3

            for y in range(max_height):
                for x in range(max_width):
                    if x >= layer_widths[layer] or y >= layer_heights[layer]:
                        continue
                    tile_idx = map_data.get_tile(layer, x, y)

                    # Priority gate: applies to both location and overworld.
                    # Locations: L3 tiles (bit 9) use _L3_PRIORITY_BASE; L12 use 9-bit index directly.
                    # Overworld: L2 indices have bit 8 (0x100) set as a layer-select flag;
                    # strip it to get the tile assembly index for the priority lookup.
                    if is_loc:
                        if tile_idx & _L3_TILE_FLAG:
                            prior_base = _L3_PRIORITY_BASE + (tile_idx & 0xFF) * 4
                        else:
                            prior_base = tile_idx * 4
                    else:
                        prior_base = (tile_idx & 0xFF) * 4
                    subtile_priority = 0
                    for _sub in range(4):
                        if prior_base + _sub < len(self._priority_tbl):
                            subtile_priority |= self._priority_tbl[prior_base + _sub]
                    if is_main and not subtile_priority:
                        continue
                    if not is_main and subtile_priority:
                        continue

                    tile_img = self.render_tile(tile_idx)
                    px = x * _TILE_PIXELS
                    py = y * _TILE_PIXELS
                    mask = tile_img[:, :, 3:4] > 0
                    canvas[py:py + _TILE_PIXELS, px:px + _TILE_PIXELS] = np.where(
                        mask, tile_img, canvas[py:py + _TILE_PIXELS, px:px + _TILE_PIXELS]
                    )

        return _ndarray_to_qimage(canvas)

    def render_tile_palette(self, max_cols: int = 16) -> 'QImage':
        """Render all L12 tiles as a palette grid (16 tiles wide)."""
        if not self._l12_asm:
            return _ndarray_to_qimage(np.zeros((_TILE_PIXELS, _TILE_PIXELS, 4), dtype=np.uint8))

        num_tiles = len(self._l12_asm) // _BYTES_PER_TILE_ASM
        num_cols = min(max_cols, num_tiles)
        num_rows = (num_tiles + num_cols - 1) // num_cols

        canvas = np.zeros((num_rows * _TILE_PIXELS, num_cols * _TILE_PIXELS, 4), dtype=np.uint8)
        for i in range(num_tiles):
            col = i % num_cols
            row = i // num_cols
            img = self.render_tile(i)
            px = col * _TILE_PIXELS
            py = row * _TILE_PIXELS
            canvas[py:py + _TILE_PIXELS, px:px + _TILE_PIXELS] = img

        return _ndarray_to_qimage(canvas)


def _ndarray_to_qimage(arr: np.ndarray) -> 'QImage':
    """Convert an (H, W, 4) RGBA uint8 ndarray to a QImage."""
    h, w = arr.shape[:2]
    rgba = np.ascontiguousarray(arr)
    img = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return img.copy() # detach from the numpy buffer