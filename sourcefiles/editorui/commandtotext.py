from jetsoftime.eventcommand import Operation, EventCommand
from jetsoftime.ctstrings import CTString
import editorui.lookups as lu

def command_to_text(command: EventCommand, bytes: int, strings: dict[int, bytearray]) -> str:
    if command.command in _command_to_text:
        if command.command in EventCommand.text_commands:
            if command.args[0] not in strings:
                return "ERROR ERROR ERROR ERROR: " + str(command)
            str_val = CTString.ct_bytes_to_ascii(strings[command.args[0]])
            return _command_to_text[command.command].format(str_val)
        elif isinstance(_command_to_text[command.command], str):
            return _command_to_text[command.command].format(*command.args)
        elif command.command == 0x10 or command.command == 0x11:
            return _command_to_text[command.command](command.args, bytes)
        elif command.command in _command_to_text:
            return _command_to_text[command.command](command.args)
    return command.to_human_readable_str()

operations = {
    Operation.EQUALS: "==",
    Operation.GREATER_THAN: ">",
    Operation.GREATER_OR_EQUAL: ">=",
    Operation.LESS_THAN: "<",
    Operation.LESS_OR_EQUAL: "<=",
    Operation.NOT_EQUALS: "!=",
    Operation.BITWISE_AND_NONZERO: "&",
    Operation.BITWISE_OR_NONZERO: "|",
}

def get_pc(pc: int) -> str:
    if pc in lu.pcs:
        return lu.pcs[pc]
    return str(pc)

def get_storyline_text(storyline: int) -> str:
    if storyline in lu.storyline:
        return lu.storyline[storyline]
    return f"0x{storyline:02X}"

def val_to_obj(obj: int) -> int:
    return int(obj/2)

def address_offset(offset: int) -> str:
    addr = offset*2 + 0x7F0200
    if addr in lu.known_mem_locations:
        return lu.known_mem_locations[addr]
    return "0x{:02X}".format(addr)

def local_address_offset(offset: int) -> str:
    addr = offset + 0x7F0000
    if addr in lu.known_mem_locations:
        return lu.known_mem_locations[addr]
    return "0x{:02X}".format(addr)


def operation_to_str(operation: Operation) -> str:
    return operations.get(operation % 0x10)

def disable_processing(args) -> str:
    return "Disable Processing(Obj{:02X})".format(val_to_obj(args[0]))

def enable_processing(args) -> str:
    return "Enable Processing(Obj{:02X})".format(val_to_obj(args[0]))

def remove_obj(args) -> str:
    return "Remove Object(Obj{:02X})".format(val_to_obj(args[0]))

def if_val(args) -> str:
    return "If({} {} {:02X})".format(address_offset(args[0]), operation_to_str(args[2]), args[1])

def if_local_val(args) -> str:
    return "If({} {} {:02X})".format(local_address_offset(args[0]), operation_to_str(args[2]), args[1])

def if_address(args) -> str:
    return "If({} {} {:02X})".format(address_offset(args[0]), operation_to_str(args[2]), args[1])

def if_local_address(args) -> str:
    return "If({} {} 0x{:02X})".format(local_address_offset(args[0]), operation_to_str(args[2]), address_offset(args[1]))

def if_visible(args) -> str:
    return "If(Obj{} visible)".format(val_to_obj(args[0]))

def if_battle_range(args) ->str:
    return "If(Obj{} in battle range)".format(val_to_obj(args[0]))

def get_result_7f0200(args) -> str:
    return "Get Result({})".format(address_offset(args[0]))

def get_result_7f0000(args) ->str:
    return "Get Result({})".format(local_address_offset(args[0]))

def load_pc(args) -> str:
    return "Load PC1 into {}".format(address_offset(args[0]))

def load_obj_coords(args) -> str:
    return "Load Obj{} Coords into {},{}".format(val_to_obj(args[0]), address_offset(args[1]), address_offset(args[2]))

def load_pc_coords(args) -> str:
    return "Load {} Coords into {},{}".format(get_pc(val_to_obj(args[0])), address_offset(args[1]), address_offset(args[2]))

def load_obj_facing(args) -> str:
    return "Load Obj{} Facing into {}".format(val_to_obj(args[0]), address_offset(args[1]))

def load_pc_facing(args) -> str:
    return "Load {} Facing into {}".format(get_pc(val_to_obj(args[0])), address_offset(args[1]))

def assign_local(args) -> str:
    return "Set 0x{:02X} = {}".format(args[0], address_offset(args[1]))

def assign_48(args) -> str:
    return "Set {} = 0x{:02X}".format(address_offset(args[1]), args[0])


def assign_from_local(args) -> str:
    return "Set {} = 0x{:02X}".format(address_offset(args[0]), args[0])

def assign_address(args) -> str:
    return "Set 0x{:02X} = {:02X}".format(args[0], args[1])

def npc_movement_properties(args) -> str:
    return "NPC Movement Properties(Through Walls: {}, Through PCs: {})".format(bool(args[0] and 1), bool(args[0] and 2))

def assign_val_to_mem(args) -> str:
    return "Set {} = {:02X}".format(address_offset(args[1]), args[0])

def assign_mem_to_mem(args) -> str:
    return "Set {} = {}".format(address_offset(args[1]), address_offset(args[0]))

def assign_local_mem_to_mem(args) -> str:
    return "Set {} = {}".format(address_offset(args[1]), local_address_offset(args[0]))

def assign_mem_to_local_mem(args) -> str:
    return "Set {} = {}".format(local_address_offset(args[1]), address_offset(args[0]))

def assign_val_to_mem_local(args) -> str:
    return "Set {} = 0x{:02X}".format(local_address_offset(args[1]), args[0])

def get_storyline(args) -> str:
    return "Set {} = Storyline".format(address_offset(args[0]))

def add_val_to_mem_local(args) -> str:
    return "{} += 0x{:02X}".format(address_offset(args[1]), args[0])

def add_mem_to_mem(args) -> str:
    return "{} += {}".format(address_offset(args[1]), address_offset(args[0]))

def subtract_val(args) -> str:
    return "{} -= 0x{:02X}".format(address_offset(args[1]), args[0])

def subtract_mem_to_mem(args) -> str:
    return "{} -= {}".format(address_offset(args[1]), address_offset(args[0]))

def set_bit(args) -> str:
    return "Set bit {:02X} in {}".format(args[0], address_offset(args[1]))

def reset_bit(args) -> str:
    return "Reset bit {:02X} in {}".format(args[0], address_offset(args[1]))

def set_local_bit(args) -> str:
    if args[0] == 0x80:
        return "Set bit in local memory 0x{:02X}".format(args[1] + 0x100)
    else:
        return "Set bit {:02X} in {}".format(args[0], local_address_offset(args[1]))

def reset_local_bit(args) -> str:
    if args[0] == 0x80:
        return "Reset bit in local memory 0x{:02X}".format(args[1] + 0x100)
    else:
        return "Reset bit {:02X} in {}".format(args[0], local_address_offset(args[1]))

def reset_bits(args) -> str:
    return "Keep bits {:02X} in {}".format(args[0], address_offset(args[1]))

def set_bits(args) -> str:
    return "Set bits {:02X} in {}".format(args[0], address_offset(args[1]))

def toggle_bits(args) -> str:
    return "Toggle bits {:02X} in {}".format(args[0], address_offset(args[1]))

def downshift(args) -> str:
    return "Downshift {} by {:02X} bits".format(address_offset(args[1]), args[0])

def increment(args) -> str:
    return "Increment {}".format(address_offset(args[0]))

def increment_word(args) -> str:
    return "Increment {}".format(address_offset(args[0]))

def decrement(args) -> str:
    return "Decrement {}".format(address_offset(args[0]))

def set_byte(args) -> str:
    return "Set {} to 1".format(address_offset(args[0]))

def set_word(args) -> str:
    return "Set {} to 1".format(address_offset(args[0]))

def reset_byte(args) -> str:
    return "Set {} to 0".format(address_offset(args[0]))

def npc_jump(args) -> str:
    return "NPC Jump(x:{}, y:{}, height:{})".format(args[0], args[1], args[2])

def random(args) -> str:
    return "Store random value in {}".format(address_offset(args[0]))

def load_pc_extended(args) -> str:
    return "Load {} if in party".format(get_pc(args[0]))

def load_pc_forced(args) -> str:
    return "Load {} (forced)".format(get_pc(args[0]))

def move_to_pc(args) -> str:
    return "Move to {} distance {:02X}".format(get_pc(args[0]), args[1])

def has_active_pc(args) ->str:
    return "If(!{} Active)".format(get_pc(args[0]))

def has_recruited_pc(args) -> str:
    return "If(!{} Recruited)".format(get_pc(args[0]))

def move_pc_to_reserve(args) -> str:
    return "Move {} to reserve".format(get_pc(args[0]))

def remove_pc_from_party(args) -> str:
    return "Remove {} from active party".format(get_pc(args[0]))

def remove_pc(args) -> str:
    return "Remove {}".format(get_pc(args[0]))

def follow_pc(args) -> str:
    return "Follow {}".format(get_pc(args[0]))

def add_pc_to_reserve(args) -> str:
    return "Add {} to reserve".format(get_pc(args[0]))

def add_pc_to_active(args) -> str:
    return "Add {} to active party".format(get_pc(args[0]))

def face_pc(args) -> str:
    return "Face {}".format(get_pc(args[0]))

def move_towards_pc(args) -> str:
    return "Move toward {}".format(get_pc(args[0]))

def loop_move_to_pc(args) -> str:
    return "Loop move to {}".format(get_pc(args[0]))


def load_npc(args) -> str:
    return "Load NPC ({})".format(lu.npcs.get(args[0], f"Unknown(0x{args[0]:02X})"))

def load_enemy(args) -> str:
    return "Load enemy ({})".format(lu.enemies.get(args[0], f"Unknown(0x{args[0]:02X})"))

def set_npc_solid(args) -> str:
    properties = []
    if args[0] & 0x01:
        properties.append("solid")
    if args[0] & 0x02:
        properties.append("through_walls")
    props_str = ", ".join(properties) if properties else "none"
    return "Set NPC solidity ({})".format(props_str)

def set_script_timing(args) -> str:
    if args[0] >= 0x80:
        return "Pause script processing"
    else:
        return "Set script speed to {:02X}".format(args[0])

def set_sprite_priority(args) -> str:
    mode = "high" if args[0] & 0x80 else "low"
    priority = (args[0] & 0x30) >> 4
    return "Set sprite priority (mode:{}, priority:{:X})".format(mode, priority)

def set_npc_speed(args) -> str:
    return "Speed(0x{:02X})".format(args[0])

def set_npc_speed_from_mem(args) -> str:
    return "Speed({})".format(address_offset(args[0]))

def set_coord(args) -> str:
    return "Move to ({},{}, Static)".format(args[0], args[1])

def set_coord_from_mem(args) -> str:
    return "Move to ({},{}, Static)".format(
        address_offset(args[0]), 
        address_offset(args[1])
    )

def set_pixel_coord(args) -> str:
    x = args[0] * 16
    y = args[1] * 16
    return "Set pixel position ({},{})".format(x, y)

def vector_move(args) -> str:
    direction = args[0] * (360/256)  # Convert to degrees
    return "Move in direction {:.1f}° magnitude {:02X}".format(direction, args[1])

def vector_move_from_mem(args) -> str:
    if len(args) == 1:
        return "Move to object {:02X}".format(args[0] // 2)
    return "Move using direction from {} magnitude from {}".format(
        address_offset(args[0]),
        address_offset(args[1])
    )

def move_to_coords(args) -> str:
    if len(args) >= 3:
        return "Move toward ({},{}) distance {:02X}".format(args[0], args[1], args[2])
    return "Move toward ({},{})".format(args[0], args[1])

def if_item(args) -> str:
    return "If(!has_item({}))".format(lu.items.get(args[0], f"Unknown(0x{args[0]:02X})")),

def add_item(args) -> str:
    return "Add {}".format(lu.items.get(args[0], f"Unknown(0x{args[0]:02X})"))

def remove_item(args) -> str:
    return "Remove {}".format(lu.items.get(args[0], f"Unknown(0x{args[0]:02X})"))

def equip_item(args) -> str:
    return "Equip {} on {}".format(lu.items.get(args[0], f"Unknown(0x{args[0]:02X})"), get_pc(args[1]))

def item_quantity(args) -> str:
    return "Get {} quantity into 0x{:02X}".format(lu.items.get(args[0], f"Unknown(0x{args[0]:02X})"), args[1])

def goto_forward(args, curr_bytes) -> str:
    return "Goto(0x{:02X})".format(args[-1] + curr_bytes + 1)

def goto_backward(args, curr_bytes) -> str:
    return "Goto(0x{:02X})".format(curr_bytes - args[-1] + 1)

def change_location(args) -> str:
    for (id, name) in lu.locations:
        if args[0] == id:
            return "Change Location({}, {},{})".format(name, args[1], args[2])
    return "Change Location({:02X}, {},{})".format(args[0], args[1], args[2])

def if_storyline(args) -> str:
    return "If(Storyline < {})".format(get_storyline_text(args[0]))

def set_storyline(args) -> str:
    return "Set Storyline = {}".format(get_storyline_text(args[0]))

def play_song(args) -> str:
    song = f"{args[0]:02X}"
    if args[0] in lu.music:
        song = lu.music[args[0]]
    return "Play song {}".format(song)

def play_sound(args) -> str:
    sound = f"{args[0]:02X}"
    if args[0] in lu.sounds:
        sound = lu.sounds[args[0]]
    return "Play sound {}".format(sound)

def _get_function_name(num: int) -> str:
    """Get the function name based on its number"""
    if num == 0:
        return "Startup"
    elif num == 1:
        return "Activate" 
    elif num == 2:
        return "Touch"
    else:
        func_id = num - 3
        return f"Function {func_id:02X}"

def call_event_cont(args) -> str:
    return call_event(args, "Obj", "cont")
def call_event_sync(args) -> str:
    return call_event(args, "Obj", "sync")
def call_event_halt(args) -> str:
    return call_event(args, "Obj", "halt")


def call_event(args, type, sync) -> str:
    priority = args[1] & 0xF0
    priority /= 0x10
    func = _get_function_name(args[1] & 0xF)
    return "Call({}{}, {}, {}, {})".format(type, val_to_obj(args[0]),priority ,func, sync)

_command_to_text = {
    0x00: "Return",
    0x01: "Color Crash",
    0x02: call_event_cont,
    0x03: call_event_sync,
    0x04: call_event_halt,
    0x05: "Call PC Event({:02X} {:02X})",
    0x06: "Call PC Event({} {:02X})",
    0x07: "Call PC Event({} {:02X})",
    0x08: "Deactivate Object",
    0x09: "Activate Object",
    0x0A: remove_obj,
    0x0B: disable_processing,
    0x0C: enable_processing,
    0x0D: npc_movement_properties,
    0x0E: "Unknown NPC Positioning({:02X})",
    0x0F: "Set NPC Facing Up",
    0x10: goto_forward,
    0x11: goto_backward,
    0x12: if_val,
    0x13: if_val,
    0x14: if_address,
    0x15: if_address,
    0x16: if_local_val,
    0x17: "Set NPC Facing Down",
    0x18: if_storyline,
    0x19: get_result_7f0200,
    0x1A: "If(!{:02X})",
    0x1B: "Set NPC Facing Left",
    0x1C: get_result_7f0000,
    0x1D: "Set NPC Facing Right",
    0x1E: "Set NPC ({}) Facing Up",
    0x1F: "Set NPC ({}) Facing Down",
    0x20: load_pc,
    0x21: load_obj_coords,
    0x22: load_pc_coords,
    0x23: load_obj_facing,
    0x24: load_pc_facing,
    0x25: "Set NPC({}) Facing Left",
    0x26: "Set NPC({}) Facing Right",
    0x27: if_visible,
    0x28: if_battle_range,
    0x29: "Load Ascii Text({:02X})",
    0x2A: "Set bit 0x4 at 7E0154",
    0x2B: "Set bit 0x8 at 7E0154",
    0x2C: "Unknown 0x2C",
    0x2D: "If(no buttons pressed)",
    0x2E: "Color Math (mode: {})",
    0x2F: "Scroll Layers 0x2F",
    0x30: "If(dashing)",
    0x31: "If(confirm)",
    0x32: "Set bit 0x10 at 7E0154",
    0x33: "Change Palette to {:02X}",
    0x34: "If(A pressed)",
    0x35: "If(B pressed)",
    0x36: "If(X pressed)",
    0x37: "If(Y pressed)",
    0x38: "If(L pressed)",
    0x39: "If(R pressed)",
    0x3A: "Color crash",
    0x3B: "If(dashing since last check)",
    0x3C: "If(confirm since last check)",
    0x3D: "Color crash",
    0x3E: "Color crash",
    0x3F: "If(A pressed since last check)",
    0x40: "If(B pressed since last check)",
    0x41: "If(X pressed since last check)",
    0x42: "If(Y pressed since last check)",
    0x43: "If(L pressed since last check)",
    0x44: "If(R pressed since last check)",
    0x45: "Color crash",
    0x46: "Color crash",
    0x47: "Limit Animations({:02X})",
    0x48: assign_48,
    0x49: assign_local,
    0x4A: assign_address,
    0x4B: assign_address,
    0x4C: assign_from_local,
    0x4D: assign_from_local,
    0x4E: "Mem Copy({:02X} {:02X} bytes to copy {:02X})",
    0x4F: assign_val_to_mem,
    0x50: assign_val_to_mem,
    0x51: assign_mem_to_mem,
    0x52: assign_mem_to_mem,
    0x53: assign_local_mem_to_mem,
    0x54: assign_local_mem_to_mem,
    0x55: get_storyline,
    0x56: assign_val_to_mem_local,
    0x57: "Load Crono",
    0x58: assign_mem_to_local_mem,
    0x59: assign_mem_to_local_mem,
    0x5A: set_storyline,
    0x5B: add_val_to_mem_local,
    0x5C: "Load Marle",
    0x5D: add_mem_to_mem,
    0x5E: add_mem_to_mem,
    #0x5F:
    0x5F: subtract_val,
    #0x60: "0x{:02X} -= {:04X}".format(address_offset(args[2]), args[0:2]),  # Two byte version
    0x61: subtract_mem_to_mem,
    0x63: set_bit,
    0x64: reset_bit,
    0x65: set_local_bit,   # Not right
    0x66: reset_local_bit, # Not right
    0x67: reset_bits,
    0x69: set_bits,
    0x6B: toggle_bits,
    0x6F: downshift,
    0x71: increment,
    0x72: increment_word,
    0x73: decrement,
    0x75: set_byte,
    0x76: set_word,
    0x77: reset_byte,
    0x7A: npc_jump,
    0x7F: random,
    0x80: load_pc_extended,
    0x81: load_pc_forced,
    0x82: load_npc,
    0x83: load_enemy,
    0x84: set_npc_solid,
    0x87: set_script_timing,
    0x88: "Memory copy mode {:02X}",  # Specific mode handling would need game-specific knowledge
    0x89: set_npc_speed,
    0x8A: set_npc_speed_from_mem,
    0x8B: set_coord,
    0x8C: set_coord_from_mem,
    0x8D: set_pixel_coord,
    0x8E: set_sprite_priority,
    0x8F: "Unknown 8F {:02X}",  # Based on docs this is unknown
    0x90: "Enable object drawing",
    0x91: "Disable object drawing",
    0x92: vector_move,
    0x94: "Follow object {:02X}",
    0x95: follow_pc,
    0x96: set_coord,  # Similar to 8B but specifically for NPC movement
    0x97: "Move to coords from (0x{:02X},0x{:02X})",
    0x98: "Move to object {:02X} distance {:02X}",
    0x99: move_to_pc,
    0x9A: move_to_coords,
    0x9C: vector_move,  # Similar to 92 but doesn't change facing
    0x9D: vector_move_from_mem,
    0x9E: "Move toward object {:02X}",
    0x9F: move_towards_pc,
    0xA0: "Move to ({}, {}, Animated)",
    0xA1: "Move to (0x{:02X}, 0x{:02X}, Animated)",
    0xA6: "Set NPC facing {:02X}",
    0xA7: "Set NPC facing from 0x{:02X}",
    0xA8: "Face object {:02X}",
    0xA9: face_pc,
    0xAA: "Play looping animation {:02X}",
    0xAB: "Play animation {:02X}",
    0xAC: "Play static animation {:02X}",
    0xAD: "Pause for {:02X}/16 seconds",
    0xAE: "Reset animation",
    0xAF: "Enable exploration (single check)",
    0xB0: "Enable exploration (continuous check)",
    0xB1: "Break",
    0xB2: "End",
    0xB3: "Play animation 00",
    0xB4: "Play animation 01",
    0xB5: "Loop move to object {:02X}",
    0xB6: loop_move_to_pc,
    0xB7: "Play animation {:02X} for {:02X} loops",
    0xB8: "Set string index to 0x{:06X}",
    0xB9: "Pause for 1/4 second",
    0xBA: "Pause for 1/2 second",
    0xBB: "Textbox({})",
    0xBC: "Pause for 1 second",
    0xBD: "Pause for 2 seconds",
    0xC0: "Textbox({})",
    0xC1: "Textbox({})",
    0xC2: "Textbox({})",
    0xC3: "Textbox({})",
    0xC4: "Textbox({})",
    0xC7: "Add item from 0x{:02X}",
    0xC8: "Display special dialog {:02X}",
    0xC9: if_item,
    0xCA: add_item,
    0xCB: remove_item,
    0xCC: "If(gold < {:04X})",
    0xCD: "Add {:04X} gold",
    0xCE: "Subtract {:04X} gold",
    0xCF: has_recruited_pc,
    0xD0: add_pc_to_reserve,
    0xD1: remove_pc,
    0xD2: has_active_pc,
    0xD3: add_pc_to_active,
    0xD4: move_pc_to_reserve,
    0xD5: equip_item,
    0xD6: remove_pc_from_party,
    0xD7: item_quantity,
    0xD8: "Start battle (flags: {:02X} {:02X})",
    0xD9: "Move party to ({},{}) ({},{}) ({},{})",
    0xDA: "Enable party follow",
    0xE0: change_location,
    0xE1: change_location,
    0xE3: "Set explore mode {:02X}",
    0xE4: "Copy tiles ({},{}) to ({},{}) at ({},{}) flags:{:02X}",
    0xE5: "Copy tiles ({},{}) to ({},{}) at ({},{}) flags:{:02X}",
    0xE6: "Scroll layers (mask: {:02X})",
    0xE7: "Scroll screen to ({},{})",
    0xE8: play_sound,
    0xEA: play_song,
    0xEB: "Set music volume to {:02X} at speed {:02X}",
    0xEC: "Sound command {:02X}",
    0xED: "Wait for silence",
    0xEE: "Wait for song end",
    0xF0: "Darken screen by {:02X}",
    0xF1: "Brighten screen (color:{:02X})",
    0xF2: "Fade out screen",
    0xF4: "Set screen shake {:02X}",
    0xF8: "Restore HP/MP",
    0xF9: "Restore HP",
    0xFA: "Restore MP",
    0xFE: "Draw geometry",
    0xFF: "Mode 7 scene {:02X}"
}