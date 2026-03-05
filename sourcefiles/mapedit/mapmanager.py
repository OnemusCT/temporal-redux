"""MapManager: load and save location/overworld map data via FSRom."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from sourcefiles.jetsoftime.byteops import to_rom_ptr, to_little_endian, get_value_from_bytes
from sourcefiles.jetsoftime.freespace import FSRom, FSWriteType
from sourcefiles.jetsoftime.ctdecompress import decompress, compress, get_compressed_length
from . import map_addresses as ma
from .map_addresses import RomAddress
from .mapdata import LocationMap, OverworldMap


@dataclass
class MapRecord:
    """Tracks one loaded map record for later save-back."""
    data: bytearray
    pointer_addr: int # file address of the 3-byte SNES pointer in ROM
    original_addr: int # file address where the data was read from
    original_len: int # byte length of the original compressed data
    modified: bool = False


class MapManager:
    """Load and save location / overworld map data using an FSRom instance.

    All data is lazy-loaded and cached on first access.
    """

    OVERWORLD_MAP_COUNT = 8

    _L12_GFX_BUFFER_SIZE = 24576
    _OW_L12_GFX_BUFFER_SIZE = 28672
    _SUBTILE_CHUNK_SIZE = 4096
    _ANIMATED_TILES_CHUNK_SIZE = 3968

    def __init__(self, fsrom: FSRom, rom_type: int = 0) -> None:
        self.fsrom = fsrom
        self.rom_type = rom_type

        self._loc_map_cache: dict[int, LocationMap] = {}
        self._ow_map_cache: dict[int, OverworldMap] = {}
        self._loc_rec_cache: dict[int, MapRecord] = {}
        self._ow_rec_cache: dict[int, MapRecord] = {}
        self._loc_map_idx: dict[int, int] = {} # loc_id -> map_idx
        self._raw_decompress_cache: dict[tuple[int, int], bytearray] = {}
        self._assembled_gfx_cache: dict[tuple, bytearray] = {}
        self._asm_cache: dict[tuple, bytearray] = {}
        self._loc_palette_cache: dict[int, bytearray] = {}
        self._ow_palette_cache: dict[int, bytearray] = {}

    def _rom(self) -> bytes:
        """Snapshot of the entire ROM as bytes (cheap for BytesIO)."""
        pos = self.fsrom.tell()
        self.fsrom.seek(0)
        data = self.fsrom.read()
        self.fsrom.seek(pos)
        return data

    def _snes_to_file(self, snes: int) -> int:
        """Convert a 24-bit SNES HiROM address to a file offset for a 4MB CT ROM."""
        if 0xC00000 <= snes <= 0xFFFFFF:
            return snes - 0xC00000
        elif 0x800000 <= snes <= 0xBFFFFF:
            return snes - 0x800000
        elif 0x400000 <= snes <= 0x7FFFFF:
            return snes - 0x400000
        else:
            # Low-bank HiROM access: SNES address numerically equals file offset
            return snes

    def _read_ptr(self, table_addr: int, index: int, rom: bytes | None = None) -> int:
        """Read a 3-byte SNES pointer and return its file offset.

        Pass *rom* when the caller already holds a snapshot to avoid a second
        full ROM read.
        """
        if rom is None:
            rom = self._rom()
        off = table_addr + index * 3
        snes = get_value_from_bytes(rom[off:off + 3])
        return self._snes_to_file(snes)

    def _write_record(
        self,
        data: bytearray,
        pointer_addr: int,
        old_addr: int,
        old_len: int,
    ) -> tuple[int, int]:
        """Compress *data*, free the old block, allocate new space, write, repoint.

        Returns (new_addr, new_len) so callers can update their MapRecord.
        """
        compressed = compress(data)
        new_len = len(compressed)

        # Free the old region in the free-space manager
        self.fsrom.space_manager.mark_block(
            (old_addr, old_addr + old_len), FSWriteType.MARK_FREE
        )

        # Allocate new space (raises FreeSpaceError if not enough)
        new_addr = self.fsrom.space_manager.get_free_addr(new_len)

        # Write the compressed data
        self.fsrom.seek(new_addr)
        self.fsrom.write(compressed, FSWriteType.MARK_USED)

        # Update the 3-byte SNES pointer in the pointer table
        new_snes = to_rom_ptr(new_addr)
        self.fsrom.seek(pointer_addr)
        self.fsrom.write(to_little_endian(new_snes, 3), FSWriteType.NO_MARK)

        return new_addr, new_len

    def get_location_props(self, loc_id: int) -> dict:
        """Read the 14-byte location property record for *loc_id*.

        Layout:
          byte 0: unknown
          byte 1: L12 tileset index
          byte 2: L3 tileset index
          byte 3: palette index
          byte 4: map data record index
          bytes 5-9: event/sprite data
          byte 10: scroll left
          byte 11: scroll top
          byte 12: scroll right
          byte 13: scroll bottom
        """
        base = ma.get_addr(RomAddress.LOCATION_PROPERTIES, self.rom_type)
        rom = self._rom()
        off = base + loc_id * 14
        rec = rom[off:off + 14]
        
        (
            unknown, l12_ts, l3_ts, palette, map_idx, evt_data,
            sc_l, sc_t, sc_r, sc_b
        ) = struct.unpack("<BBBBB5sBBBB", rec)
        
        return {
            'l12_tileset': l12_ts,
            'l3_tileset': l3_ts,
            'palette': palette,
            'map_index': map_idx,
            'scroll_left': sc_l,
            'scroll_top': sc_t,
            'scroll_right': sc_r,
            'scroll_bottom': sc_b,
        }

    def get_location_map(self, loc_id: int) -> LocationMap:
        """Return the LocationMap for *loc_id* (loads + caches on first call)."""
        props = self.get_location_props(loc_id)
        map_idx = props['map_index']
        self._loc_map_idx[loc_id] = map_idx # cache so write-back doesn't re-read ROM

        if map_idx in self._loc_map_cache:
            return self._loc_map_cache[map_idx]

        loc_map = self._load_loc_map_by_index(map_idx)
        self._loc_map_cache[map_idx] = loc_map
        return loc_map

    def _load_loc_map_by_index(self, map_idx: int) -> LocationMap:
        """Low-level: load a LocationMap by its map-data record index."""
        ptr_table = ma.get_addr(RomAddress.LOCATION_MAP_PTR_TABLE, self.rom_type)
        rom = self._rom()
        file_addr = self._read_ptr(ptr_table, map_idx, rom)
        raw = decompress(rom, file_addr)

        loc_map = LocationMap()
        loc_map.load(bytearray(raw), is_beta=(self.rom_type == 2))

        # Record original position for later save-back
        orig_len = get_compressed_length(rom, file_addr)
        self._loc_rec_cache[map_idx] = MapRecord(
            data = bytearray(raw),
            pointer_addr = ptr_table + map_idx * 3,
            original_addr= file_addr,
            original_len = orig_len,
        )
        return loc_map

    def write_location_map(self, loc_id: int) -> None:
        """Compress and write back the (possibly modified) location map for *loc_id*."""
        if loc_id not in self._loc_map_idx:
            raise KeyError(f'Location map {loc_id} not loaded')
        map_idx = self._loc_map_idx[loc_id]
        if map_idx not in self._loc_rec_cache or map_idx not in self._loc_map_cache:
            raise KeyError(f'Location map index {map_idx} (loc {loc_id}) not loaded')

        rec = self._loc_rec_cache[map_idx]
        data = self._loc_map_cache[map_idx].to_bytes(is_beta=(self.rom_type == 2))
        new_addr, new_len = self._write_record(data, rec.pointer_addr, rec.original_addr, rec.original_len)
        rec.data = data
        rec.original_addr = new_addr
        rec.original_len = new_len
        rec.modified = True

    def get_overworld_map(self, ow_index: int) -> OverworldMap:
        """Return the OverworldMap for *ow_index* (loads + caches on first call).

        *ow_index* is the overworld properties index (0-7).
        """
        props = self.get_overworld_props(ow_index)
        map_slot = props['map_slot']

        if map_slot in self._ow_map_cache:
            return self._ow_map_cache[map_slot]

        ptr_table = ma.get_addr(RomAddress.OVERWORLD_MAP_PTR_TABLE, self.rom_type) # overworld map
        rom = self._rom()
        file_addr = self._read_ptr(ptr_table, map_slot, rom)
        raw = decompress(rom, file_addr)

        ow_map = OverworldMap()
        ow_map.load(bytearray(raw))
        self._ow_map_cache[map_slot] = ow_map

        orig_len = get_compressed_length(rom, file_addr)
        self._ow_rec_cache[map_slot] = MapRecord(
            data = bytearray(raw),
            pointer_addr = ptr_table + map_slot * 3, # pointer is at overworld map[map_slot]
            original_addr= file_addr,
            original_len = orig_len,
        )
        return ow_map

    def write_overworld_map(self, ow_index: int) -> None:
        """Compress and write back the overworld map for *ow_index*."""
        props = self.get_overworld_props(ow_index)
        map_slot = props['map_slot']

        if map_slot not in self._ow_rec_cache or map_slot not in self._ow_map_cache:
            raise KeyError(f'Overworld map slot {map_slot} (index {ow_index}) not loaded')
        rec = self._ow_rec_cache[map_slot]
        data = bytearray(self._ow_map_cache[map_slot].raw_data)
        new_addr, new_len = self._write_record(data, rec.pointer_addr, rec.original_addr, rec.original_len)
        rec.data = data
        rec.original_addr = new_addr
        rec.original_len = new_len
        rec.modified = True

    def _decompress_at_ptr(self, ptr_table_addr: int, index: int) -> bytearray:
        """Decompress the block pointed to by ptr_table_addr[index]."""
        key = (ptr_table_addr, index)
        if key in self._raw_decompress_cache:
            return self._raw_decompress_cache[key]
        rom = self._rom()
        file_addr = self._read_ptr(ptr_table_addr, index, rom)
        raw = bytearray(decompress(rom, file_addr))
        self._raw_decompress_cache[key] = raw
        return raw

    @property
    def _max_l12_tileset(self) -> int:
        """Max valid location tileset index, derived from the address range for this rom_type."""
        return (ma.get_addr(RomAddress.LOCATION_MAP_PTR_TABLE, self.rom_type) - ma.get_addr(RomAddress.LOCATION_TILESET_BASE, self.rom_type)) // 8 - 1

    def get_l12_subtile_data(self, l12_tileset_idx: int) -> bytearray:
        """Assemble L12 subtile graphics for the given tileset index.

        The tileset record table has 8 bytes per entry; each byte is a slot index used
        to look up compressed graphics in the L12 graphics pointer table

        Returns a bytearray of 24576 bytes (5 x 4096 + 3968 data bytes, with 128
        bytes of zero padding to match the 24576 boundary limits).
        Slots 6-7 are animated subtiles loaded separately; they are skipped here.
        Raises ValueError for out-of-range tileset indices (e.g. 0xFF = unused).
        """
        max_tileset = self._max_l12_tileset
        if l12_tileset_idx > max_tileset:
            raise ValueError(
                f"L12 tileset index {l12_tileset_idx} out of range "
                f"(max {max_tileset}) - location may be unused"
            )
        key = ('l12', l12_tileset_idx)
        if key in self._assembled_gfx_cache:
            return self._assembled_gfx_cache[key]

        tileset_rec_base = ma.get_addr(RomAddress.LOCATION_TILESET_BASE, self.rom_type)
        ptr_table = ma.get_addr(RomAddress.SUBTILE_GRAPHICS_PTR_TABLE, self.rom_type)
        rom = self._rom()
        result = bytearray(self._L12_GFX_BUFFER_SIZE)

        for slot in range(8):
            sub_idx = rom[tileset_rec_base + l12_tileset_idx * 8 + slot]
            if sub_idx >= 224:
                continue
            raw = self._decompress_at_ptr(ptr_table, sub_idx)
            if slot < 5:
                dest_off = slot * self._SUBTILE_CHUNK_SIZE
                result[dest_off:dest_off + self._SUBTILE_CHUNK_SIZE] = raw[:self._SUBTILE_CHUNK_SIZE]
            elif slot == 5:
                dest_off = slot * self._SUBTILE_CHUNK_SIZE
                result[dest_off:dest_off + self._ANIMATED_TILES_CHUNK_SIZE] = raw[:self._ANIMATED_TILES_CHUNK_SIZE]
            # slots 6-7 are animated subtiles, currently skipped

        self._assembled_gfx_cache[key] = result
        return result

    # Valid indices: 0-22; higher values = no L3 layer
    _MAX_L3_TILESET = 22

    def get_l3_subtile_data(self, l3_tileset_idx: int) -> bytearray:
        """Load L3 subtile graphics (2bpp) for the given tileset index.

        L3 graphics share the same pointer table as L1/2 indexed directly
        by the L3 tileset index (not via a tileset record table).
        Raises ValueError for indices >= 23 (treated as "no L3 layer").
        """
        if l3_tileset_idx > self._MAX_L3_TILESET:
            raise ValueError(
                f"L3 tileset index {l3_tileset_idx} out of range "
                f"(max {self._MAX_L3_TILESET}) - location has no L3 layer"
            )
        key = ('l3', l3_tileset_idx)
        if key in self._assembled_gfx_cache:
            return self._assembled_gfx_cache[key]
        ptr_table = ma.get_addr(RomAddress.SUBTILE_GRAPHICS_PTR_TABLE, self.rom_type)
        raw = bytearray(self._decompress_at_ptr(ptr_table, l3_tileset_idx))
        self._assembled_gfx_cache[key] = raw
        return raw

    _TILE_ASM_ADDR: dict[str, RomAddress] = {
        'l12': RomAddress.LAYER_12_TILE_ASSEMBLY,
        'l3': RomAddress.LAYER_3_TILE_ASSEMBLY,
        'ow_l12': RomAddress.OVERWORLD_LAYER_12_TILE_ASSEMBLY,
        'ow_l3': RomAddress.OVERWORLD_LAYER_3_TILE_ASSEMBLY,
    }

    def get_tile_assembly(self, index: int, layer: str = 'l12') -> bytearray:
        """Load tile assembly data for *index*."""
        if layer not in self._TILE_ASM_ADDR:
            raise ValueError(f"Unknown tile assembly layer {layer!r}; "
                             f"expected one of {list(self._TILE_ASM_ADDR)}")
        if layer == 'l3' and index > self._MAX_L3_TILESET:
            raise ValueError(
                f"L3 tile assembly index {index} out of range "
                f"(max {self._MAX_L3_TILESET}) - location has no L3 layer"
            )
        key = (layer, index)
        if key in self._asm_cache:
            return self._asm_cache[key]
        ptr_table = ma.get_addr(self._TILE_ASM_ADDR[layer], self.rom_type)
        raw = bytearray(self._decompress_at_ptr(ptr_table, index))
        self._asm_cache[key] = raw
        return raw

    _PALETTE_STRIDE = 210 # 7 sub-palettes x 15 colors x 2 bytes/color

    def get_palette_data(self, palette_idx: int) -> bytearray:
        """Load raw palette data for *palette_idx*.

        Location palettes are stored as flat uncompressed BGR555 data. Each palette
        is 210 bytes:
            7 sub-palettes x 15 colors x 2 bytes (color 0 of each row is shared).
        """
        if palette_idx in self._loc_palette_cache:
            return self._loc_palette_cache[palette_idx]
        base = ma.get_addr(RomAddress.LOCATION_PALETTE_BASE, self.rom_type)
        rom = self._rom()
        off = base + palette_idx * self._PALETTE_STRIDE
        raw = bytearray(rom[off:off + self._PALETTE_STRIDE])
        self._loc_palette_cache[palette_idx] = raw
        return raw

    _OW_PROP_STRIDE = 23 # bytes per overworld property record

    def get_overworld_props(self, ow_index: int) -> dict:
        """Read the 23-byte overworld properties record for *ow_index*.

        Layout:
          bytes 0-6: tileset[0..6] - 7 slot indices for overworld tiles
          byte 8: l3_tileset - direct index into overworld tiles
          byte 10: palette - index into overworld palette
          byte 16: l12_asm - index into overworld L1/2 tiles
          byte 20: l3_asm - index into overworld L3 tiles
        """
        base = ma.get_addr(RomAddress.OVERWORLD_MAP_PROPERTIES, self.rom_type)
        rom = self._rom()
        off = base + ow_index * self._OW_PROP_STRIDE
        rec = rom[off:off + self._OW_PROP_STRIDE]
        
        tileset, l3_ts, palette, l12_asm, map_slot, l3_asm = struct.unpack(
            "<7s x B x B 5x B B 2x B 2x", rec
        )
        
        return {
            'tileset': list(tileset),
            'l3_tileset': l3_ts,
            'palette': palette,
            'l12_asm': l12_asm,
            'map_slot': map_slot,
            'l3_asm': l3_asm,
        }

    def get_ow_l12_subtile_data(self, tileset_slots: list) -> bytearray:
        """Assemble overworld L12 subtile graphics buffer (28672 bytes = 7 x 4096).

        *tileset_slots* is a list of 7 slot indices into overworld tiles
        Slots with index >= 42 are skipped.
        """
        key = ('ow_l12', tuple(tileset_slots))
        if key in self._assembled_gfx_cache:
            return self._assembled_gfx_cache[key]
        ptr_table = ma.get_addr("overworld_tile_ptr_table", self.rom_type)
        result = bytearray(self._OW_L12_GFX_BUFFER_SIZE)
        for slot, sub_idx in enumerate(tileset_slots[:7]):
            if sub_idx >= 42:
                continue
            raw = self._decompress_at_ptr(ptr_table, sub_idx)
            dest_off = slot * self._SUBTILE_CHUNK_SIZE
            result[dest_off:dest_off + self._SUBTILE_CHUNK_SIZE] = raw[:self._SUBTILE_CHUNK_SIZE]
        self._assembled_gfx_cache[key] = result
        return result

    _MAX_OW_L3_TILESET = 41

    def get_ow_l3_subtile_data(self, l3_ts: int) -> bytearray:
        """Load Overworld L3 subtile graphics (4096 bytes) from overworld tiles at *l3_ts*.

        Raises ValueError for indices >= 42.
        """
        if l3_ts > self._MAX_OW_L3_TILESET:
            raise ValueError(
                f"OW L3 tileset index {l3_ts} out of range "
                f"(max {self._MAX_OW_L3_TILESET}) - overworld has no L3 layer"
            )
        key = ('ow_l3', l3_ts)
        if key in self._assembled_gfx_cache:
            return self._assembled_gfx_cache[key]
        ptr_table = ma.get_addr(RomAddress.OVERWORLD_TILE_PTR_TABLE, self.rom_type)
        raw = bytearray(self._decompress_at_ptr(ptr_table, l3_ts))[:self._SUBTILE_CHUNK_SIZE]
        if len(raw) < self._SUBTILE_CHUNK_SIZE:
            raw = raw + bytearray(self._SUBTILE_CHUNK_SIZE - len(raw))
        self._assembled_gfx_cache[key] = raw
        return raw

    _OW_PALETTE_STRIDE = 512 # 16 palettes x 16 colors x 2 bytes (compressed in ROM)

    def get_ow_palette_data(self, pal_idx: int) -> bytearray:
        """Load raw overworld palette data (512 bytes)

        The overworld palette contains 13 compressed records; each decompresses to 512 bytes:
        16 sub-palettes x 16 colors x 2 bytes (BGR555).
        """
        if pal_idx in self._ow_palette_cache:
            return self._ow_palette_cache[pal_idx]
        ptr_table = ma.get_addr(RomAddress.OVERWORLD_PALETTE_PTR_TABLE, self.rom_type)
        raw = bytearray(self._decompress_at_ptr(ptr_table, pal_idx))
        self._ow_palette_cache[pal_idx] = raw
        return raw

    def invalidate(self) -> None:
        """Clear all caches (use after external ROM modifications)."""
        self._loc_map_cache.clear()
        self._ow_map_cache.clear()
        self._loc_rec_cache.clear()
        self._ow_rec_cache.clear()
        self._loc_map_idx.clear()
        self._raw_decompress_cache.clear()
        self._assembled_gfx_cache.clear()
        self._asm_cache.clear()
        self._loc_palette_cache.clear()
        self._ow_palette_cache.clear()
