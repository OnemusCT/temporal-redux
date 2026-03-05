"""ROM address tables

Each entry in ROM_ADDR is (US, JP, Beta) file offsets.
Each entry in ROM_VALUE is (US, JP, Beta) counts/values.
rom_type: 0 = US, 1 = Japanese, 2 = Beta
"""

ROM_ADDR: dict[int, tuple[int, int, int]] = {
    0: (3538944, 3538944, 3538944), # 0x360000 - Location properties (14 bytes each, flat uncompressed)
    1: (3546112, 3546112, 3546112), # 0x361C00 - Location tileset records (8 bytes per tileset, slot indices)
    2: (3547680, 3547680, 3547680), # 0x362220 - L12+L3 subtile graphics pointer table (3 bytes/entry, compressed blocks)
    3: (3548352, 3548352, 3548352), # 0x3624C0 - Location palette data (210 bytes/palette, flat BGR555, 7x15 colors)
    4: (462347, 462353, 481673), # 0x070E0B - Instrument/sample pointer table
    5: (452523, 452523, 0), # 0x06E7AB - NLZ decompressor patch
    6: (151137, 151137, 151137), # 0x024E61 - Dactyl ride patch
    7: (3546624, 3546624, 3546624), # 0x361E00 - Location map pointer table (256 x 3 bytes -> compressed tilemaps)
    8: (3547392, 3547392, 3547392), # 0x362100 - Location L12 tile assembly pointer table (3 bytes/entry, compressed)
    9: (3547584, 3547584, 3547584), # 0x3621C0 - Location L3 tile assembly pointer table (3 bytes/entry, compressed)
    10: (42654, 42654, 40887), # 0x00A69E - Location exit records
    11: (458400, 458400, 458400), # 0x06FEA0 - Overworld palette pointer table
    12: (458528, 458528, 458528), # 0x06FF20 - Overworld map pointer table (8 x 3 bytes -> compressed OW tilemaps)
    13: (458496, 458496, 458496), # 0x06FF00 - Overworld L12 tile assembly pointer table
    14: (458560, 458560, 458560), # 0x06FF40 - Overworld L3 tile assembly pointer table
    15: (458688, 458688, 458688), # 0x06FFC0 - Overworld exit records
    16: (3579904, 3996144, 3612672), # 0x369F00 - Location event/sprite pointer table
    17: (458624, 458624, 458624), # 0x06FF80 - Overworld tile properties pointer table
    18: (458000, 458000, 458000), # 0x06FD90 - Overworld map properties
    19: (458720, 458720, 458720), # 0x06FFE0 - Overworld event pointer table
    20: (458656, 458656, 458656), # 0x06FFA0 - Overworld music transition data
    21: (6548, 6548, 7062), # 0x001994 - Map point (minimap) location data
    22: (144908, 144908, 144541), # 0x023600 - Map point (minimap) overworld data
    23: (458272, 458272, 458272), # 0x06FE20 - Overworld tile graphics pointer table
    24: (153831, 153822, 153995), # 0x0258E7 - Main substring pointer table
    25: (4190289, 4192285, 4190289), # 0x3FF051 - Party equipment data
    26: (812800, 812288, 812800), # 0x0C6700 - Overworld tile assembly
    27: (42813, 42813, 41046), # 0x00A73D - Chest/treasure records
    28: (789342, 789342, 789244), # 0x0C0B5E - Item name string data
    29: (791520, 792015, 791296), # 0x0C13E0 - Tech name string data
    30: (0, 155878, 0), # 0x0260E6 - Character spacing table (JP-only)
    31: (143716, 143716, 143379), # 0x023164 - DactylMap [uncertain]
    32: (142742, 142742, 0), # 0x022D96 - BlackOmenStory [uncertain]
    33: (160696, 160868, 161624), # 0x0273B8 - EpochLastVillage [uncertain]
    34: (160728, 160900, 0), # 0x0273D8 - EpochLastVillage2 [uncertain]
    35: (7342, 7342, 7864), # 0x001CAE - Game over music (single byte)
    36: (183140, 182948, 182510), # 0x02CB64 - Party menu NPC (single byte)
    37: (183405, 183252, 182767), # 0x02CC6D - Party menu music (single byte)
    38: (18299, 18299, 15125), # 0x00477B - Enemy gfx bank index
    39: (3153, 3153, 3394), # 0x000C51 - Door sound (single byte)
    40: (3157, 3157, 3402), # 0x000C55 - Chest sound (single byte)
    41: (3161, 3161, 3406), # 0x000C59 - Battle music (single byte)
    42: (150084, 150084, 149483), # 0x024A44 - Epoch music (single byte)
    43: (150088, 150088, 149487), # 0x024A48 - Epoch upgraded music (single byte)
    44: (154223, 154214, 156140), # 0x025A6F - Secondary substring pointers
    45: (3581456, 2030080, 3997440), # 0x36A610 - original ROM address of substring data
}

ROM_VALUE: dict[int, tuple[int, int, int]] = {
    0: (81, 83, 70), # Location L12 tile assembly block count (pointer table length)
    1: (31, 127, 32), # Location L3 tile assembly block count (pointer table length)
    2: (242, 242, 228), # Location palette count (210 bytes each: 7 sub-palettes x 15 BGR555 colors)
    3: (8, 11, 8), # Overworld L12 tile assembly block count (pointer table length)
    4: (9, 11, 9), # Overworld L3 tile assembly block count (pointer table length)
    6: (117, 116, 109), # Overworld palette count (compressed)
    7: (3, 0, 3), # AlphaType font enum for location name strings
    9: (33, 33, 32), # Starting symbol index of the substring 0 table
    10: (256, 251, 256), # Location map count (one compressed tilemap per location, 0x00-0xFF; JP has only 251 valid)
    11: (184, 0, 0), # Number of substring 1-2 entries; US only
}


def get_addr(index: int, rom_type: int = 0) -> int:
    """Return the file offset for a ROM address table entry."""
    return ROM_ADDR[index][rom_type]


def get_value(index: int, rom_type: int = 0) -> int:
    """Return a ROM value table entry."""
    return ROM_VALUE[index][rom_type]
