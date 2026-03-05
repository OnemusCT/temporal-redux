"""ROM address tables

Each entry in ROM_ADDR is (US, JP, Beta) file offsets.
Each entry in ROM_VALUE is (US, JP, Beta) counts/values.
rom_type: 0 = US, 1 = Japanese, 2 = Beta
"""

ROM_ADDR_MAP: dict[str, tuple[int, int, int]] = {
    "location_properties": (0x360000, 0x360000, 0x360000), # 0
    "location_tileset_base": (0x361C00, 0x361C00, 0x361C00), # 1
    "subtile_graphics_ptr_table": (0x362220, 0x362220, 0x362220), #2
    "location_palette_base": (0x3624C0, 0x3624C0, 0x3624C0), # 3
    "location_map_ptr_table": (0x361E00, 0x361E00, 0x361E00), # 7
    "overworld_palette_ptr_table": (0x06FEA0, 0x06FEA0, 0x06FEA0), # 11
    "overworld_map_ptr_table": (0x06FF20, 0x06FF20, 0x06FF20), #12
    "overworld_map_properties": (0x06FD10, 0x06FD10, 0x06FD10), #18
    "overworld_tile_ptr_table": (0x06FE20, 0x06FE20, 0x06FE20), #23
    "layer_12_tile_assembly": (0x362100, 0x362100, 0x362100), # 8
    "layer_3_tile_assembly": (0x3621C0, 0x3621C0, 0x3621C0), #9
    "overworld_layer_12_tile_assembly": (0x06FF00, 0x06FF00, 0x06FF00), # 13
    "overworld_layer_3_tile_assembly": (0x06FF40, 0x06FF40, 0x06FF40), # 14
}

def get_addr(key: str, rom_type: int = 0) -> int:
    """Return the file offset for a ROM address table entry."""
    return ROM_ADDR_MAP[key][rom_type]

