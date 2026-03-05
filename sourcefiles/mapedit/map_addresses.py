"""ROM address tables

Each entry in ROM_ADDR is (US, JP, Beta) file offsets.
Each entry in ROM_VALUE is (US, JP, Beta) counts/values.
rom_type: 0 = US, 1 = Japanese, 2 = Beta
"""

import enum

class RomAddress(enum.Enum):
    LOCATION_PROPERTIES = "location_properties"
    LOCATION_TILESET_BASE = "location_tileset_base"
    SUBTILE_GRAPHICS_PTR_TABLE = "subtile_graphics_ptr_table"
    LOCATION_PALETTE_BASE = "location_palette_base"
    LOCATION_MAP_PTR_TABLE = "location_map_ptr_table"
    OVERWORLD_PALETTE_PTR_TABLE = "overworld_palette_ptr_table"
    OVERWORLD_MAP_PTR_TABLE = "overworld_map_ptr_table"
    OVERWORLD_MAP_PROPERTIES = "overworld_map_properties"
    OVERWORLD_TILE_PTR_TABLE = "overworld_tile_ptr_table"
    LAYER_12_TILE_ASSEMBLY = "layer_12_tile_assembly"
    LAYER_3_TILE_ASSEMBLY = "layer_3_tile_assembly"
    OVERWORLD_LAYER_12_TILE_ASSEMBLY = "overworld_layer_12_tile_assembly"
    OVERWORLD_LAYER_3_TILE_ASSEMBLY = "overworld_layer_3_tile_assembly"

ROM_ADDR_MAP: dict[RomAddress, tuple[int, int, int]] = {
    RomAddress.LOCATION_PROPERTIES: (0x360000, 0x360000, 0x360000), # 0
    RomAddress.LOCATION_TILESET_BASE: (0x361C00, 0x361C00, 0x361C00), # 1
    RomAddress.SUBTILE_GRAPHICS_PTR_TABLE: (0x362220, 0x362220, 0x362220), #2
    RomAddress.LOCATION_PALETTE_BASE: (0x3624C0, 0x3624C0, 0x3624C0), # 3
    RomAddress.LOCATION_MAP_PTR_TABLE: (0x361E00, 0x361E00, 0x361E00), # 7
    RomAddress.OVERWORLD_PALETTE_PTR_TABLE: (0x06FEA0, 0x06FEA0, 0x06FEA0), # 11
    RomAddress.OVERWORLD_MAP_PTR_TABLE: (0x06FF20, 0x06FF20, 0x06FF20), #12
    RomAddress.OVERWORLD_MAP_PROPERTIES: (0x06FD10, 0x06FD10, 0x06FD10), #18
    RomAddress.OVERWORLD_TILE_PTR_TABLE: (0x06FE20, 0x06FE20, 0x06FE20), #23
    RomAddress.LAYER_12_TILE_ASSEMBLY: (0x362100, 0x362100, 0x362100), # 8
    RomAddress.LAYER_3_TILE_ASSEMBLY: (0x3621C0, 0x3621C0, 0x3621C0), #9
    RomAddress.OVERWORLD_LAYER_12_TILE_ASSEMBLY: (0x06FF00, 0x06FF00, 0x06FF00), # 13
    RomAddress.OVERWORLD_LAYER_3_TILE_ASSEMBLY: (0x06FF40, 0x06FF40, 0x06FF40), # 14
}

def get_addr(key: RomAddress, rom_type: int = 0) -> int:
    """Return the file offset for a ROM address table entry."""
    return ROM_ADDR_MAP[key][rom_type]

