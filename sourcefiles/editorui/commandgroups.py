from enum import Enum


class EventCommandType(Enum):
    UNASSIGNED = ""
    ANIMATION = "Animation"
    ASSIGNMENT = "Assignment"
    BATTLE = "Battle"
    BIT_MATH = "Bit Math"
    BYTE_MATH = "Byte Math"
    CHANGE_LOCATION = "Change Location"
    CHECK_BUTTON = "Check Button"
    CHECK_INVENTORY = "Check Inventory"
    CHECK_PARTY = "Check Party"
    CHECK_RESULT = "Check Result"
    CHECK_STORYLINE = "Check Storyline"
    COMPARISON = "Comparison"
    END = "End"
    FACING = "Facing"
    GOTO = "Goto"
    HP_MP = "HP/MP"
    INVENTORY = "Inventory"
    MEM_COPY = "Memory Copy"
    MODE7 = "Mode7"
    OBJECT_COORDINATES = "Object Coordinates"
    OBJECT_FUNCTION = "Object Function"
    PALETTE = "Palette"
    PAUSE = "Pause"
    PARTY_MANAGEMENT = "Party Management"
    RANDOM_NUM = "Random Number"
    PC_EXTENDED = "PC Extended"
    SCENE_MANIP = "Scene Manipulation"
    SOUND = "Sound"
    SPRITE_COLLISION = "Sprite Collision"
    SPRITE_DRAWING = "Sprite Drawing"
    SPRITE_MOVEMENT = "Sprite Movement"
    TEXT = "Text"
    UNKNOWN = "Unknown"

class EventCommandSubtype(Enum):
    UNASSIGNED = ""
    ANIMATION = "Animation"
    ANIMATION_LIMITER = "Animation Limiter"
    RESET_ANIMATION = "Reset Animation"
    GET_PC1 = "Get PC1"
    GET_STORYLINE = "Get Storyline"
    MEM_TO_MEM_BYTE = "Mem to Mem"
    RESULT = "Result"
    SET_STORYLINE = "Set Storyline"
    VAL_TO_MEM_BYTE = "Value To Mem"
    BATTLE = "Battle"
    BIT_MATH = "Bit Math"
    DOWNSHIFT = "Downshift"
    SET_AT = "Set Bits at 7E0154"
    MEM_TO_MEM_ASSIGN = "Mem to Mem"
    VAL_TO_MEM_ASSIGN = "Value to Mem"
    CHANGE_LOCATION = "Change Location"
    CHANGE_LOCATION_FROM_MEM = "Change Location from Mem"
    CHECK_BUTTON = "Check Button"
    CHECK_PARTY = "Check Party"
    CHECK_RESULT = "Check Result"
    CHECK_STORYLINE = "Check Storyline"
    CHECK_DRAWN = "Check Drawn"
    CHECK_IN_BATTLE = "Check in Battle"
    MEM_TO_MEM_COMP = "Mem to Mem"
    VAL_TO_MEM_COMP = "Value to Mem"
    END = "End"
    FACE_OBJECT = "Face Object"
    GET_FACING = "Get Facing"
    SET_FACING = "Set Facing"
    SET_FACING_FROM_MEM = "Set Facing From Mem"
    GOTO = "Goto"
    RESTORE_HPMP = "Restore HP/MP"
    EQUIP = "Equip"
    GET_AMOUNT = "Get Item Amount"
    CHECK_GOLD = "Check Gold"
    ADD_GOLD = "Add Gold"
    CHECK_ITEM = "Check Item"
    ITEM = "Item"
    ITEM_FROM_MEM = "Add Item from Mem"
    MEM_COPY = "Memory Copy"
    MULTI_MODE = "Multi-mode 88"
    DRAW_GEOMETRY = "Draw Geometry"
    MODE7 = "Mode 7"
    GET_OBJ_COORD = "Get Object Coordinates"
    SET_OBJ_COORD = "Set Object Coordinates"
    SET_OBJ_COORD_FROM_MEM = "Set Object Coordinates from Mem"
    ACTIVATE = "Activate/Touch"
    CALL_OBJ_FUNC = "Call Object Function"
    SCRIPT_PROCESSING = "Script Processing"
    CHANGE_PALETTE = "Change Palette"
    PAUSE = "Pause"
    PARTY_MANIP = "Party Manipulation"
    RANDOM_NUM = "Random Number"
    COLOR_ADD = "Color Addition"
    COLOR_MATH = "Color Math"
    COPY_TILES = "Copy Tiles"
    DARKEN = "Darken"
    FADE_OUT = "Fade Out"
    SCRIPT_SPEED = "Script Speed"
    SCROLL_LAYERS = "Scroll Layers"
    SCROLL_LAYERS_2F = "Scroll Layers 2F"
    SCROLL_SCREEN = "Scroll Screen"
    SHAKE_SCREEN = "Shake Screen"
    WAIT_FOR_ADD = "Wait for Color Add End"
    SOUND = "Sound"
    WAIT_FOR_SILENCE = "Wait for Silence"
    SPRITE_COLLISION = "Sprite Collision"
    DRAW_STATUS = "Drawing Status"
    DRAW_STATUS_FROM_MEM = "Drawing Status from Mem"
    LOAD_SPRITE = "Load Sprite"
    SPRITE_PRIORITY = "Sprite Priority"
    CONTROLLABLE = "Controllable"
    EXPLORE_MODE = "Explore Mode"
    JUMP = "Jump"
    JUMP_7B = "Jump 7B"
    MOVE_PARTY = "Move Party"
    MOVE_SPRITE = "Move Sprite"
    MOVE_SPRITE_FROM_MEM = "Move Sprite from Mem"
    MOVE_TOWARD_COORD = "Move Towards Coordinates"
    MOVE_TOWARD_OBJ = "Move Towards Object"
    OBJECT_FOLLOW = "Object Follow"
    OBJECT_MOVEMENT_PROPERTIES = "Object Movement Properties"
    PARTY_FOLLOW = "Party Follow"
    DESTINATION = "Destination"
    VECTOR_MOVE = "Vector Move"
    VECTOR_MOVE_FROM_MEM = "Vector Move from Mem"
    SET_SPEED = "Set Speed"
    SET_SPEED_FROM_MEM = "Set Speed from Mem"
    LOAD_ASCII = "Load Ascii"
    SPECIAL_DIALOG = "Special Dialog"
    STRING_INDEX = "String Index"
    TEXTBOX = "Textbox"
    COLOR_CRASH = "Color Crash"
    EXT_BIT = "Extended Bit Op"
    EXT_COPY = "Extended Copy"
    EXT_JUMP = "Extended Jump"
    UNKNOWN = "Unknown"


event_command_groupings = {
    EventCommandType.ANIMATION: {
        EventCommandSubtype.ANIMATION: [0xAA, 0xAB, 0xAC, 0xB3, 0xB4, 0xB7],
        EventCommandSubtype.ANIMATION_LIMITER: [0x47],
        EventCommandSubtype.RESET_ANIMATION: [0xAE],
    },
    EventCommandType.ASSIGNMENT: {
        EventCommandSubtype.GET_PC1: [0x20],
        EventCommandSubtype.GET_STORYLINE: [0x55],
        EventCommandSubtype.MEM_TO_MEM_ASSIGN: [0x48, 0x49, 0x4C, 0x4D, 0x51, 0x52, 0x53, 0x54, 0x58, 0x59],
        EventCommandSubtype.RESULT: [0x19, 0x1C],
        EventCommandSubtype.SET_STORYLINE: [0x5A],
        EventCommandSubtype.VAL_TO_MEM_ASSIGN: [0x4A, 0x4B, 0x4F, 0x50, 0x56, 0x75, 0x76, 0x77],
    },
    EventCommandType.BATTLE: {
        EventCommandSubtype.BATTLE: [0xD8],
    },
    EventCommandType.BIT_MATH: {
        EventCommandSubtype.BIT_MATH: [0x63, 0x64, 0x65, 0x66, 0x67, 0x69, 0x6B],
        EventCommandSubtype.DOWNSHIFT: [0x6F],
        EventCommandSubtype.SET_AT: [0x2A, 0x2B, 0x32],
    },
    EventCommandType.BYTE_MATH: {
        EventCommandSubtype.MEM_TO_MEM_BYTE: [0x5D, 0x5E, 0x61],
        EventCommandSubtype.VAL_TO_MEM_BYTE: [0x5B, 0x5F, 0x60, 0x71, 0x72, 0x73],
    },
    EventCommandType.CHANGE_LOCATION: {
        EventCommandSubtype.CHANGE_LOCATION: [0xDC, 0xDD, 0xDE, 0xDF, 0xE0, 0xE1],
        EventCommandSubtype.CHANGE_LOCATION_FROM_MEM: [0xE2],
    },
    EventCommandType.CHECK_BUTTON: {
        EventCommandSubtype.CHECK_BUTTON: [0x2D, 0x30, 0x31, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3B, 0x3C, 0x3F, 0x40, 0x41, 0x42, 0x43, 0x44],
    },
    EventCommandType.CHECK_PARTY: {
        EventCommandSubtype.CHECK_PARTY: [0xCF, 0xD2],
    },
    EventCommandType.CHECK_RESULT: {
        EventCommandSubtype.CHECK_RESULT: [0x1A],
    },
    EventCommandType.CHECK_STORYLINE: {
        EventCommandSubtype.CHECK_STORYLINE: [0x18],
    },
    EventCommandType.COMPARISON: {
        EventCommandSubtype.CHECK_DRAWN: [0x27],
        EventCommandSubtype.CHECK_IN_BATTLE: [0x28],
        EventCommandSubtype.MEM_TO_MEM_COMP: [0x14, 0x15],
        EventCommandSubtype.VAL_TO_MEM_COMP: [0x12, 0x13, 0x16],
    },
    EventCommandType.END: {
        EventCommandSubtype.END: [0x00, 0xB1, 0xB2],
    },
    EventCommandType.FACING: {
        EventCommandSubtype.FACE_OBJECT: [0xA8, 0xA9],
        EventCommandSubtype.GET_FACING: [0x23, 0x24],
        EventCommandSubtype.SET_FACING: [0x0F, 0x17, 0x1B, 0x1D, 0x1E, 0x1F, 0x25, 0x26, 0xA6],
        EventCommandSubtype.SET_FACING_FROM_MEM: [0xA7],
    },
    EventCommandType.GOTO: {
        EventCommandSubtype.GOTO: [0x10, 0x11],
    },
    EventCommandType.HP_MP: {
        EventCommandSubtype.RESTORE_HPMP: [0xF8, 0xF9, 0xFA]
    },
    EventCommandType.INVENTORY: {
        EventCommandSubtype.EQUIP: [0xD5],
        EventCommandSubtype.GET_AMOUNT: [0xD7],
        EventCommandSubtype.CHECK_GOLD: [0xCC],
        EventCommandSubtype.ADD_GOLD: [0xCD, 0xCE],
        EventCommandSubtype.CHECK_ITEM: [0xC9],
        EventCommandSubtype.ITEM: [0xCA, 0xCB],
        EventCommandSubtype.ITEM_FROM_MEM: [0xC7],
    },
    EventCommandType.MEM_COPY: {
        EventCommandSubtype.MEM_COPY: [0x4E],
        EventCommandSubtype.MULTI_MODE: [0x88],
    },
    EventCommandType.MODE7: {
        EventCommandSubtype.MODE7: [0xFF],
        EventCommandSubtype.DRAW_GEOMETRY: [0xFE],
    },
    EventCommandType.OBJECT_COORDINATES: {
        EventCommandSubtype.GET_OBJ_COORD: [0x21, 0x22],
        EventCommandSubtype.SET_OBJ_COORD: [0x8B, 0x8D],
        EventCommandSubtype.SET_OBJ_COORD_FROM_MEM: [0x8C],
    },
    EventCommandType.OBJECT_FUNCTION: {
        EventCommandSubtype.ACTIVATE: [0x08, 0x09],
        EventCommandSubtype.CALL_OBJ_FUNC: [0x02, 0x03, 0x04, 0x05, 0x06, 0x07],
        EventCommandSubtype.SCRIPT_PROCESSING: [0x0B, 0x0C],
    },
    EventCommandType.PALETTE: {
        EventCommandSubtype.CHANGE_PALETTE: [0x33],
    },
    EventCommandType.PAUSE: {
        EventCommandSubtype.PAUSE: [0xAD, 0xB9, 0xBA, 0xBC, 0xBD],
    },
    EventCommandType.PARTY_MANAGEMENT: {
        EventCommandSubtype.PARTY_MANIP: [0xD0, 0xD1, 0xD3, 0xD4, 0xD6],
    },
    EventCommandType.RANDOM_NUM: {
        EventCommandSubtype.RANDOM_NUM: [0x7F],
    },
    EventCommandType.SCENE_MANIP: {
        EventCommandSubtype.COLOR_ADD: [0xF1],
        EventCommandSubtype.COLOR_MATH: [0x2E],
        EventCommandSubtype.COPY_TILES: [0xE4, 0xE5],
        EventCommandSubtype.DARKEN: [0xF0],
        EventCommandSubtype.FADE_OUT: [0xF2],
        EventCommandSubtype.SCRIPT_SPEED: [0x87],
        EventCommandSubtype.SCROLL_LAYERS: [0xE6],
        EventCommandSubtype.SCROLL_LAYERS_2F: [0x2F],
        EventCommandSubtype.SCROLL_SCREEN: [0xE7],
        EventCommandSubtype.SHAKE_SCREEN: [0xF4],
        EventCommandSubtype.WAIT_FOR_ADD: [0xF3],
    },
    EventCommandType.SOUND: {
        EventCommandSubtype.SOUND: [0xE8, 0xEA, 0xEB, 0xEC],
        EventCommandSubtype.WAIT_FOR_SILENCE: [0xED, 0xEE],
    },
    EventCommandType.SPRITE_COLLISION: {
        EventCommandSubtype.SPRITE_COLLISION: [0x84],
    },
    EventCommandType.SPRITE_DRAWING: {
        EventCommandSubtype.DRAW_STATUS: [0x0A, 0x7E, 0x90, 0x91],
        EventCommandSubtype.DRAW_STATUS_FROM_MEM: [0x7C, 0x7D],
        EventCommandSubtype.LOAD_SPRITE: [0x57, 0x5C, 0x62, 0x68, 0x6A, 0x6C, 0x6D, 0x80, 0x81, 0x82, 0x83],
        EventCommandSubtype.SPRITE_PRIORITY: [0x8E],
    },
    EventCommandType.SPRITE_MOVEMENT: {
        EventCommandSubtype.CONTROLLABLE: [0xAF, 0xB0],
        EventCommandSubtype.EXPLORE_MODE: [0xE3],
        EventCommandSubtype.JUMP: [0x7A],
        EventCommandSubtype.JUMP_7B: [0x7B],
        EventCommandSubtype.MOVE_PARTY: [0xD9],
        EventCommandSubtype.MOVE_SPRITE: [0x96, 0xA0],
        EventCommandSubtype.MOVE_SPRITE_FROM_MEM: [0x97, 0xA1],
        EventCommandSubtype.MOVE_TOWARD_COORD: [0x9A],
        EventCommandSubtype.MOVE_TOWARD_OBJ: [0x98, 0x99, 0x9E, 0x9F],
        EventCommandSubtype.OBJECT_FOLLOW: [0x8F, 0x94, 0x95, 0xB5, 0xB6],
        EventCommandSubtype.OBJECT_MOVEMENT_PROPERTIES: [0x0D],
        EventCommandSubtype.PARTY_FOLLOW: [0xDA],
        EventCommandSubtype.DESTINATION: [0x0E],
        EventCommandSubtype.VECTOR_MOVE: [0x92, 0x9C],
        EventCommandSubtype.VECTOR_MOVE_FROM_MEM: [0x9D],
        EventCommandSubtype.SET_SPEED: [0x89],
        EventCommandSubtype.SET_SPEED_FROM_MEM: [0x8A],
    },
    EventCommandType.TEXT: {
        EventCommandSubtype.LOAD_ASCII: [0x29],
        EventCommandSubtype.SPECIAL_DIALOG: [0xC8],
        EventCommandSubtype.STRING_INDEX: [0xB8],
        EventCommandSubtype.TEXTBOX: [0xBB, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4],
    },
    EventCommandType.PC_EXTENDED: {
        EventCommandSubtype.EXT_COPY: [0x3A, 0x3D, 0x3E, 0x70, 0x74, 0x78],
        EventCommandSubtype.EXT_BIT: [0x45, 0x46],
        EventCommandSubtype.EXT_JUMP: [0x6E],
    },
    EventCommandType.UNKNOWN: {
        EventCommandSubtype.COLOR_CRASH: [0x01],
        EventCommandSubtype.UNKNOWN: [0x2C],
    }

}