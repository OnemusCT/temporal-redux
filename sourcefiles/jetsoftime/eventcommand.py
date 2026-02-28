from __future__ import annotations
import math
from typing import Tuple

from .byteops import to_little_endian, get_value_from_bytes
from enum import Enum, IntEnum, auto
from editorui.commandgroups import EventCommandType, EventCommandSubtype


# Small enum to store the synchronization scheme when a function is called
class FuncSync(Enum):
    '''Enum of synchronization schemes for event object function calls.'''
    HALT = auto()
    CONT = auto()
    SYNC = auto()


class Platform(IntEnum):
    '''Target platform for event script decoding.'''
    SNES = 0
    PC = 1


# Opcodes whose argument sizes differ between SNES and PC.
# Maps opcode byte → arg_lens list for the PC version.
_PC_ARG_LENS_OVERRIDES: dict[int, list[int]] = {
    # Textbox: string index is u16 on PC (u8 on SNES)
    0xBB: [2],
    0xC0: [2, 1],
    0xC1: [2],
    0xC2: [2],
    0xC3: [2, 1],
    0xC4: [2, 1],
    # ChangeLocation: PC adds a separate facing byte after the scene u16
    0xDC: [2, 1, 1, 1],
    0xDD: [2, 1, 1, 1],
    0xDE: [2, 1, 1, 1],
    0xDF: [2, 1, 1, 1],
    0xE0: [2, 1, 1, 1],
    0xE1: [2, 1, 1, 1],
    # LoadEnemy: enemy index is u16 on PC
    0x83: [2, 1],
    # JumpIfHasItem: item index is u16 on PC
    0xC9: [2, 1],
    # EquipPC: extra category byte on PC
    0xD5: [1, 1, 1],
    # SetStringTable: PC stores table index u8 (not a 24-bit ROM address)
    0xB8: [1],
    # PC-only extended-memory ops (SNES aliases these to 0-arg unknown 0x01)
    0x3A: [1, 1],   # Copy8  immediate → extended-mem slot
    0x3D: [1, 1],   # Copy8  local mem → extended-mem slot
    0x3E: [1, 1],   # Copy8  extended-mem slot → local mem
    0x45: [1, 1],   # BitSet   on extended-mem slot
    0x46: [1, 1],   # BitClear on extended-mem slot
    0x6E: [1, 1, 1, 1],  # JumpIfExtended8: lhs_ext, rhs_val, cmp_op, jump_off
    0x70: [1, 1],   # Copy8  party_slot[idx] → local mem
    0x74: [1, 1],   # Copy16 extended-mem slot → local mem
    0x78: [1, 1],   # Copy16 local mem → extended-mem slot
}


class Operation(IntEnum):
    '''Enum of operations permitted in event commands'''
    EQUALS = 0
    NOT_EQUALS = 1
    GREATER_THAN = 2
    LESS_THAN = 3
    GREATER_OR_EQUAL = 4
    LESS_OR_EQUAL = 5
    BITWISE_AND_NONZERO = 6
    BITWISE_OR_NONZERO = 7


def is_script_mem(addr: int) -> bool:
    '''Whether an address is in the local script memory.'''
    return 0x7F0200 <= addr < 0x7F0400


def is_local_mem(addr: int):
    '''Whether the address is in the flag memory [0x7F0000,0x7F0200).'''
    return (
        not is_script_mem(addr) and
        0x7F0000 <= addr < 0x7F0200
    )


def is_memory_addr(addr: int):
    return 0x7E0000 < addr < 0x800000


def is_bank_7E(addr: int):
    return 0x7E0000 <= addr < 0x7F0000


def get_offset(script_addr):
    if script_addr % 2 != 0:
        raise ValueError('Script address must be even.')

    return (script_addr - 0x7F0200) // 2


class EventCommand:

    str_commands = [0xBB, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4]
    str_arg_pos = [0, 0, 0, 0, 0, 0]

    fwd_jump_commands = [0x10, 0x12, 0x13, 0x14, 0x15, 0x16, 0x18, 0x1A,
                         0x27, 0x28, 0x2D, 0x30, 0x31, 0x34, 0x35, 0x36,
                         0x37, 0x38, 0x39, 0x3B, 0x3C, 0x3F, 0x40, 0x41,
                         0x42, 0x43, 0x44, 0xC9, 0xCC, 0xCF, 0xD2]

    change_loc_commands = [0xDC, 0xDD, 0xDE, 0xDF, 0xE0, 0xE1, 0xE2]
    # the number of bytes to jump is always the last arg
    fwd_jump_arg_pos = [-1 for i in range(len(fwd_jump_commands))]

    back_jump_commands = [0x11]
    back_jump_arg_pos = [-1]

    conditional_commands = [x for x in fwd_jump_commands
                            if x != 0x10]
    jump_commands = fwd_jump_commands + back_jump_commands

    text_commands = [0xBB, 0xC0, 0xC1, 0xC2, 0xC3, 0xC4]

    def __init__(self, command, num_args,
                 arg_lens, arg_descs,
                 name, desc, command_type = None, command_subtype = None):
        self.command = command
        self.num_args = num_args
        self.arg_lens = arg_lens
        self.arg_descs = arg_descs
        self.name = name
        self.desc = desc

        self.command_type = command_type
        self.command_subtype = command_subtype

        # These are the actual arguments from the string of bytes in the script
        self.args = []

        # These are the decoded args
        self.logical_args = []

    def __eq__(self, other):
        return self.command == other.command and self.args == other.args

    # Returns coordinates in pixels
    def get_pixel_coordinates(self) -> Tuple[int, int]:
        if self.command == 0x8B:
            return (self.args[0]*0x10+8, self.args[1]*0x10+0x10)

        if self.command == 0x8D:
            return (self.args[0] >> 4, self.args[1] >> 4)

        raise AttributeError('This command does not set coordinates.')

    def to_bytearray(self) -> bytearray:

        x = bytearray()
        x.append(self.command)

        if self.command == 0x4E:
            x += b''.join(to_little_endian(self.args[i], self.arg_lens[i])
                          for i in range(len(self.args)-1))
            x += self.args[-1]
        else:
            x += b''.join(to_little_endian(self.args[i], self.arg_lens[i])
                          for i in range(len(self.args)))

        return x

    def to_human_readable_str(self) -> str:
        ret = self.name
        if self.num_args > 0:
            ret += " args: ("
            ret += str(hex(self.args[0]))
            for i in range(1, len(self.args)):
                if isinstance(self.args[i], int):
                    ret += ", " + str(hex(self.args[i]))
                else:
                    ret += ", {" + str(self.args[i]) + "}"
            ret += ")"
        return ret

    @staticmethod
    def set_explore_mode(is_on: bool) -> EventCommand:
        ret_cmd = event_commands[0xE3].copy()
        ret_cmd.args = [0]
        if is_on:
            ret_cmd.args[0] = 1
        else:
            ret_cmd.args[0] = 0

        return ret_cmd

    @staticmethod
    def set_controllable_once() -> EventCommand:
        return EventCommand.generic_zero_arg(0xAF)

    @staticmethod
    def set_controllable_infinite() -> EventCommand:
        return EventCommand.generic_zero_arg(0xB0)

    @staticmethod
    def party_follow() -> EventCommand:
        return EventCommand.generic_zero_arg(0xDA)

    @staticmethod
    def move_party(pc1_x, pc1_y, pc2_x, pc2_y, pc3_x, pc3_y):
        ret_cmd = event_commands[0xD9].copy()
        ret_cmd.args = [pc1_x, pc1_y, pc2_x, pc2_y, pc3_x, pc3_y]
        return ret_cmd

    @staticmethod
    def change_location(location, x_coord, y_coord, facing=0,
                        unk=0, wait_vblank=True, variant_override=None) -> EventCommand:
        # There are many different change location commands.  I'll update this
        # as I understand their differences.
        if wait_vblank:
            if variant_override is not None:
                raise ValueError('variant_override cannot be set if wait_vblank is true')
            cmd = 0xE1
        else:
            cmd = 0xE0
            if variant_override is not None:
                if variant_override not in [0xDC, 0xDD, 0xDE, 0xDF, 0xE0]:
                    raise ValueError('invalid variant_override')
                cmd = variant_override

        ret_cmd = event_commands[cmd].copy()
        ret_cmd.args = [0, 0, 0]

        ret_cmd.args[0] = (facing & 0x03) << 0xB
        ret_cmd.args[0] |= (unk & 0x03) << 0x9
        ret_cmd.args[0] |= location

        ret_cmd.args[1] = x_coord
        ret_cmd.args[2] = y_coord

        return ret_cmd

    @staticmethod
    def fade_screen() -> EventCommand:
        return EventCommand.generic_zero_arg(0xF2)

    @staticmethod
    def darken(duration) -> EventCommand:
        return EventCommand.generic_one_arg(0xF0, duration)

    @staticmethod
    def load_pc_always(pc_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0x81, int(pc_id))

    @staticmethod
    def load_pc_in_party(pc_id: int) -> EventCommand:
        if pc_id == 0:
            cmd_id = 0x57
        elif pc_id == 1:
            cmd_id = 0x5C
        elif pc_id == 2:
            cmd_id = 0x62
        elif pc_id == 3:
            cmd_id = 0x6A
        elif pc_id == 4:
            cmd_id = 0x68
        elif pc_id == 5:
            cmd_id = 0x6C
        elif pc_id == 6:
            cmd_id = 0x6D

        return EventCommand.generic_zero_arg(cmd_id)

    @staticmethod
    def load_npc(npc_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0x82, npc_id)

    @staticmethod
    def load_enemy(enemy_id: int, slot_number: int,
                   is_static: bool = False) -> EventCommand:
        # maybe validate?
        # enemy id in [0, 0xFF], slot id in [0, A]
        slot_arg = slot_number | 0x80*(is_static)
        x = EventCommand.generic_two_arg(0x83, int(enemy_id), slot_arg)
        return x

    @staticmethod
    def set_reset_bits(address: int, bitmask: int,
                       set_bits: bool = True) -> EventCommand:
        if not is_script_mem(address):
            raise ValueError('set_bits must opertate on script memory.')

        if not address % 2 == 0:
            raise ValueError('set_bits must operate on even addresses.')

        if not 0 <= bitmask < 0x100:
            raise ValueError('bitmask must be in [0, 0x100)')

        offset = (address - 0x7F0200)//2
        if set_bits:
            return EventCommand.generic_two_arg(0x69, bitmask, offset)

        return EventCommand.generic_two_arg(0x67, bitmask, offset)

    @staticmethod
    def set_reset_bit(address: int, bit: int, set_bit: bool) -> EventCommand:

        # For addresses in [0x7F0000, 0x7F0200) we can access any byte.
        # For bytes past 0x7F00FF we set the 0x80 bit of the byte indicating
        # the bit to set.
        if 0x7F0000 <= address < 0x7F0200:
            overflow = 0x80 * (address >= 0x7F0100)
            offset = address % 0x100
            if set_bit:
                cmd_id = 0x65
            else:
                cmd_id = 0x66
        # For addresses in script memory, [0x7F0200, 0x7F0400), we can only
        # access the even bytes.
        elif 0x7F0200 <= address < 0x7F0400:
            overflow = 0
            if address % 2 == 1:
                print(
                    'Warning: Script memory addresses must be even.  '
                    'Rounding down.'
                )
                address -= 1
            offset = (address - 0x7F0200)//2
            if set_bit:
                cmd_id = 0x63
            else:
                cmd_id = 0x64
        else:
            raise SystemExit(f'Error: Address {address:06X} out of range.')

        bit_byte = overflow | int(math.log2(bit))
        ret_cmd = EventCommand.generic_two_arg(cmd_id, bit_byte, offset)

        return ret_cmd

    @staticmethod
    def set_bit(address: int, bit: int) -> EventCommand:
        return EventCommand.set_reset_bit(address, bit, True)

    @staticmethod
    def reset_bit(address: int, bit: int) -> EventCommand:
        return EventCommand.set_reset_bit(address, bit, False)

    @staticmethod
    def set_object_drawing_status(obj_id: int, is_drawn: bool) -> EventCommand:
        if is_drawn:
            x = EventCommand.generic_one_arg(0x7C, obj_id*2)
        else:
            x = EventCommand.generic_one_arg(0x7D, obj_id*2)

        return x

    @staticmethod
    def set_own_drawing_status(is_drawn: bool, use_7e: bool=False):
        if is_drawn:
            if use_7e:
                raise ValueError("is_drawn and use_7e not compatible")
            cmd_id = 0x90
        else:
            cmd_id = 0x7E if use_7e else 0x91

        x = event_commands[cmd_id].copy()
        return x

    @staticmethod
    def remove_object(object_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0xA, 2*object_id)

    @staticmethod
    def vector_move(angle: int, magnitude: int,
                    keep_facing: bool) -> EventCommand:
        hex_angle = (0x100 * angle)//360
        cmd_mag = magnitude*2

        if keep_facing:
            return EventCommand.generic_two_arg(0x9C, hex_angle, cmd_mag)

        return EventCommand.generic_two_arg(0x92, hex_angle, cmd_mag)

    @staticmethod
    def call_pc_function(
            pc_id: int, fn_id: int, priority: int, sync: FuncSync
    ) -> EventCommand:
        if sync == FuncSync.HALT:
            cmd_id = 7
        elif sync == FuncSync.SYNC:
            cmd_id = 6
        elif sync == FuncSync.CONT:
            cmd_id = 5

        return EventCommand.generic_command(
            cmd_id, pc_id*2, (priority << 4) | fn_id
        )

    @staticmethod
    def call_obj_function(obj_id: int,
                          fn_id: int,
                          priority: int,
                          sync: FuncSync) -> EventCommand:

        # Format is:
        #   1st byte is command
        #   2nd byte is 2*object number
        #   3rd byte is prio in upper 8 bits, fn number in lower 8 bits

        if sync == FuncSync.HALT:
            cmd_id = 4
        elif sync == FuncSync.SYNC:
            cmd_id = 3
        elif sync == FuncSync.CONT:
            cmd_id = 2
        else:
            # Maybe an error message?  But we are using enums so no other
            # input should be possible.
            pass

        obj_byte = obj_id * 2

        # Validate fn_id, prio are between 0 and 15 inclusive
        if not 0 <= priority <= 0xF:
            print(f"Error: priority ({priority}) not between 0 and 15")

        if not 0 <= fn_id <= 0xF:
            print(f"Error: fn_id ({fn_id}) not between 0 and 15")

        # really mixture of prio and fn_id
        prio_byte = (priority << 4) | fn_id

        ret = event_commands[cmd_id].copy()
        ret.args = [obj_byte, prio_byte]

        return ret

    @staticmethod
    def copy_tiles(src_left: int, src_top: int, src_right: int, src_bot: int,
                   dest_left: int, dest_top: int,
                   copy_l1: bool = False,
                   copy_l2: bool = False,
                   copy_l3: bool = False,
                   copy_props: bool = False,
                   unk_0x10: bool = False,
                   unk_0x20: bool = False,
                   wait_vblank: bool = True) -> EventCommand:

        if src_left > src_right:
            raise SystemExit('Error, left > right')

        if src_top > src_bot:
            raise SystemError('Error: top > bot')

        if wait_vblank:
            cmd = 0xE4
        else:
            cmd = 0xE5

        ret_cmd = event_commands[cmd].copy()
        ret_cmd.args = [0 for i in range(ret_cmd.num_args)]

        ret_cmd.args[0:6] = [src_left, src_top, src_right, src_bot,
                             dest_left, dest_top]

        flags = (copy_l1) + (copy_l2 << 1) + (copy_l3 << 2) + \
            (copy_props << 3) + (unk_0x10 << 4) + (unk_0x20 << 5)
        ret_cmd.args[6] = flags

        return ret_cmd

    @staticmethod
    def get_blank_command(cmd_id: int) -> EventCommand:
        ret_cmd = event_commands[cmd_id].copy()
        ret_cmd.args = [0 for i in range(ret_cmd.num_args)]
        return ret_cmd

    @staticmethod
    def generic_command(*args) -> EventCommand:
        ret_cmd = event_commands[args[0]].copy()
        ret_cmd.args = list(args[1:])

        return ret_cmd

    @staticmethod
    def generic_zero_arg(cmd_id: int) -> EventCommand:
        ret = event_commands[cmd_id].copy()
        return ret

    # one arg, 1 byte
    @staticmethod
    def generic_one_arg(cmd_id: int, arg) -> EventCommand:
        ret = event_commands[cmd_id].copy()
        ret.args = [arg]
        return ret

    # two args, 1 byte each
    @staticmethod
    def generic_two_arg(cmd_id: int,
                        arg0: int,
                        arg1: int) -> EventCommand:
        ret = event_commands[cmd_id].copy()
        ret.args = [arg0, arg1]
        return ret

    @staticmethod
    def return_cmd() -> EventCommand:
        return EventCommand.generic_zero_arg(0)

    @staticmethod
    def break_cmd() -> EventCommand:
        return EventCommand.generic_zero_arg(0xB1)

    @staticmethod
    def end_cmd() -> EventCommand:
        return EventCommand.generic_zero_arg(0xB2)

    @staticmethod
    def add_gold(gold_amt: int) -> EventCommand:
        return EventCommand.generic_command(0xCD, gold_amt)

    @staticmethod
    def add_item(item_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0xCA, item_id)

    @staticmethod
    def remove_item(item_id: int) -> EventCommand:
        return EventCommand.generic_command(0xCB, item_id)

    @staticmethod
    def get_item_count(item_id: int, script_addr: int) -> EventCommand:
        if not is_script_mem(script_addr):
            raise ValueError('Address must be script memory.')

        offset = get_offset(script_addr)
        return EventCommand.generic_command(0xD7, item_id, offset)

    @staticmethod
    def if_storyline_counter_lt(storyline_val: int, jump_bytes: int):
        return EventCommand.generic_command(0x18, storyline_val, jump_bytes)

    @staticmethod
    def if_has_item(item_id: int, jump_bytes: int) -> EventCommand:
        return EventCommand.generic_two_arg(0xC9, int(item_id), jump_bytes)

    @staticmethod
    def if_mem_op_value(
            address: int, operation: Operation,
            value: int, num_bytes: int,  bytes_jump: int
    ) -> EventCommand:
        # TODO: Should do some validation here.  Lots of overlap with
        #       assign_val_to_mem

        operator = int(operation)

        if address in range(0x7F0000, 0x7F0200):
            cmd_id = 0x16
            if num_bytes != 1:
                raise ValueError(
                    '[0x7F0000, 0x7F0200) range requires 1 byte width.'
                )

            # Accessing the upper 0x100 bytes is done by ORing the operation
            # with 0x80
            if address >= 0x7F0100:
                operator |= 0x80

            offset = address % 0x100

        elif address in range(0x7F0200, 0x7F0400):
            if address % 2 != 0:
                print('Warning: Even address required. Rounding down.')
                address = address - 1

            offset = (address - 0x7F0200) // 2
            if num_bytes == 1:
                cmd_id = 0x12
            elif num_bytes == 2:
                cmd_id = 0x13
            else:
                print('Warning: Bad byte width.  Using 2.')
                num_bytes = 2
                cmd_id = 0x13

        ret_cmd = event_commands[cmd_id].copy()
        ret_cmd.args = [offset, value, operator, bytes_jump]

        return ret_cmd

    @staticmethod
    def set_storyline_counter(val: int) -> EventCommand:
        return EventCommand.assign_val_to_mem(val, 0x7F0000, 1)

    @staticmethod
    def increment_mem(script_addr: int, num_bytes: int = 1) -> EventCommand:
        if not is_script_mem(script_addr):
            raise ValueError('Can only increment script memory')

        if num_bytes == 1:
            cmd_id = 0x71
        else:
            cmd_id = 0x72

        offset = get_offset(script_addr)

        return EventCommand.generic_command(cmd_id, offset)
    
    @staticmethod
    def decrement_mem(script_addr: int) -> EventCommand:
        if not is_script_mem(script_addr):
            raise ValueError('Can only increment script memory')
        offset = get_offset(script_addr)

        return EventCommand.generic_command(0x73, offset)

    @staticmethod
    def add_value_to_mem(value: int, script_addr: int):
        if not is_script_mem(script_addr):
            raise ValueError('Can only add to script memory')

        if not 0 <= value < 0x100:
            raise ValueError('Can only add values in [0, 0x100)')

        cmd = event_commands[0x5B].copy()
        cmd.args = [value, get_offset(script_addr)]

        return cmd

    @staticmethod
    def assign_mem_to_mem(
            from_addr: int,
            to_addr: int,
            num_bytes: int
    ) -> EventCommand:

        if num_bytes not in (1, 2):
            raise ValueError('Num bytes must be 1 or 2')

        if is_script_mem(from_addr) and is_script_mem(to_addr):
            # arg 1: offset of from_addr
            # arg 2: offset of to_addr
            cmd_args = [get_offset(from_addr), get_offset(to_addr)]
            if num_bytes == 1:
                cmd_id = 0x51
            else:
                cmd_id = 0x52
        elif is_local_mem(from_addr) and is_script_mem(to_addr):
            # arg 1: from_addr - 0x7F0000
            # arg 2: offset of to_addr
            cmd_args = [from_addr - 0x7F0000, get_offset(to_addr)]
            if num_bytes == 1:
                cmd_id = 0x53
            else:
                cmd_id = 0x54
        elif is_script_mem(from_addr) and is_local_mem(to_addr):
            # arg 1: offset of from_addr
            # arg 2: to_addr - 0x7F0000
            cmd_args = [get_offset(from_addr), to_addr - 0x7F0000]
            if num_bytes == 1:
                cmd_id = 0x58
            else:
                cmd_id = 0x59
        elif is_bank_7E(from_addr) and is_script_mem(to_addr):
            # arg 1: from_addr (3 bytes)
            # arg 2: (0x7F0200 - to_addr) / 2 -- check int?
            cmd_args = [from_addr, get_offset(to_addr)]
            if num_bytes == 1:
                cmd_id = 0x48
            else:
                cmd_id = 0x49
        elif is_script_mem(from_addr) and is_memory_addr(to_addr):
            # arg 1: to_addr (3 bytes)
            # arg 2: (from_addr - 0x7F000) / 2
            cmd_args = [to_addr, get_offset(from_addr)]
            if num_bytes == 1:
                cmd_id = 0x4C
            else:
                cmd_id = 0x4D
        else:
            raise ValueError("Invalid address")

        cmd = event_commands[cmd_id].copy()
        cmd.args = cmd_args

        return cmd

    @staticmethod
    def assign_val_to_mem(
            val: int, address: int, num_bytes: int
    ) -> EventCommand:
        '''
        Generate an EventCommand that writes val to adddress.

        Paramters:
        val (int): The value to be written
        address (int): The address in [0x7E0000, 0x7FFFFF] to write to
        num_bytes (int):  The number of bytes to write to.  Either 1 or 2.

        Returns:
        An eventcommand.EventCommand which will perform the write.
        '''

        # First some validation.
        # Make sure that num_bytes is 1 or 2.  Otherwise try to guess it from
        # the value.
        if num_bytes not in (1, 2):
            print(f'Warning: num_bytes ({num_bytes}) must be 1 or 2.')
            if val < (1 << 8):
                print('Setting num_bytes to 1')
                num_bytes = 1
            else:
                print('Setting num_bytes to 2')
                num_bytes = 2

        # Make sure that the value fits in num_bytes
        if val < 0:
            print(f"Warning: Value ({val} < 0).  Setting to 0.")
            val = 0

        max_val = (1 << num_bytes*8) - 1
        if val > max_val:
            print(f"Warning: Value ({val}) exceeds maximum ({max_val}). "
                  f"Truncating to {max_val}")
            val = max_val

        # Make sure that the target address is in RAM - [0x7E0000, 0x7FFFFF]
        # 0x110 and 0x111 are special addresses for disabling the menu and pause.
        if not (0x7E0000 <= address <= 0x7FFFFF or address in [0x110, 0x111]):
            raise SystemExit(
                'Address not in RAM memory range [0x7E0000, 0x7FFFFF]'
            )

        # There are three types of assignments depending on the memory range
        #   1) Script memory: [0x7F0200, 0x7F03FF]
        #   2) Bank 7F: [0x7F0000, 0x7FFFFF]
        #   3) All Ram: [0x7E0000, 0x7FFFFF]
        # Each range has its own assignment commands with variants for 1 and
        # 2 bytes.
        if 0x7F0200 <= address <= 0x7F03FF and address % 2 == 0:
            if num_bytes == 1:
                cmd_id = 0x4F
            else:
                cmd_id = 0x50

            offset = (address - 0x7F0200) // 2
            out_cmd = event_commands[cmd_id].copy()
            out_cmd.args = [val, offset]
        elif 0x7F0000 <= address <= 0x7FFFFF:
            if 0x7F0200 <= address <= 0x7F03FF:
                # This means the user provided an odd adddress so we're
                # falling back to the bank 7F command
                print(
                    f"Warning: address ({address: 06X}) is in script memory "
                    "but has an odd address.  Using bank 7F command."
                )

            if num_bytes == 1:
                out_cmd = event_commands[0x56].copy()
                offset = (address - 0x7F0000)
                out_cmd.args = [val, offset]
            else:
                out_cmd = event_commands[0x4B].copy()
                out_cmd.args = [address, val]
        else:
            if num_bytes == 1:
                cmd_id = 0x4A
            else:
                cmd_id = 0x4B

            out_cmd = event_commands[cmd_id].copy()
            out_cmd.args = [address, val]

        return out_cmd

    # Reminder that jumps in CT are always computed as being a jump from the
    # last byte of the jump command.  This is what the jump_bytes argument is.
    @staticmethod
    def jump_back(jump_bytes: int) -> EventCommand:
        return EventCommand.generic_one_arg(0x11, jump_bytes)

    @staticmethod
    def jump_forward(jump_bytes: int) -> EventCommand:
        return EventCommand.generic_one_arg(0x10, jump_bytes)

    @staticmethod
    def name_pc(char_id: int) -> EventCommand:
        return EventCommand.generic_command(0xC8, 0xC0 | char_id)

    @staticmethod
    def switch_pcs() -> EventCommand:
        return EventCommand.generic_command(0xC8, 0x00)

    @staticmethod
    def check_active_pc(char_id: int, jump_bytes: int) -> EventCommand:
        return EventCommand.generic_two_arg(0xD2, char_id, jump_bytes)

    @staticmethod
    def check_recruited_pc(char_id: int, jump_bytes: int) -> EventCommand:
        return EventCommand.generic_two_arg(0xCF, char_id, jump_bytes)

    @staticmethod
    def add_pc_to_active(char_id: int) -> EventCommand:
        return EventCommand.generic_command(0xD3, char_id)

    @staticmethod
    def add_pc_to_reserve(char_id: int) -> EventCommand:
        return EventCommand.generic_command(0xD0, char_id)

    @staticmethod
    def get_object_coordinates(obj_id: int,
                               x_addr: int,
                               y_addr: int) -> EventCommand:
        return EventCommand.generic_command(
            0x21, obj_id*2,
            get_offset(x_addr),
            get_offset(y_addr)
        )
    
    @staticmethod
    def get_pc_coordinates(pc_id: int,
                           x_addr: int,
                           y_addr: int) ->EventCommand:
        return EventCommand.generic_command(
            0x22, pc_id*2,
            get_offset(x_addr),
            get_offset(y_addr)
        )

    @staticmethod
    def set_own_coordinates_from_mem(x_addr, y_addr) -> EventCommand:
        return EventCommand.generic_command(0x8C,
                                            get_offset(x_addr),
                                            get_offset(y_addr))

    @staticmethod
    def set_object_coordinates_pixels(x_coord: int,
                                      y_coord: int) -> EventCommand:
        return EventCommand.generic_command(0x8D, x_coord << 4, y_coord << 4)

    @staticmethod
    def set_object_coordinates_tile(x_coord: int,
                                    y_coord: int) -> EventCommand:
        '''
        Sets an object's coordinates to be on the given tile coordinates.
        '''

        #
        return EventCommand.generic_command(0x8B, x_coord, y_coord)

    @staticmethod
    def set_object_coordinates_auto(px_x_coord: int,
                                    px_y_coord: int) -> EventCommand:
        tile_x = px_x_coord - 0x8
        tile_y = px_y_coord - 0x10

        if (tile_x & 0xF) == 0 and (tile_y & 0xF) == 0:
            tile_x >>= 4
            tile_y >>= 4
            return EventCommand.set_object_coordinates_tile(tile_x, tile_y)

        return EventCommand.set_object_coordinates_pixels(
            px_x_coord, px_y_coord
        )

    #  Here x and y are assumed to be pixel coordinates
    @staticmethod
    def set_object_coordinates(x: int, y: int,
                               shift: bool = True) -> EventCommand:
        # print(f"set: ({x:04X}, {y:04X})")

        # Command 0x8B works based on tiles while 0x8D works on pixels.
        # It should be that the two differ by a factor of 16, but it doesn't
        # match up.
        if x % 16 == 0 and y % 16 == 0 and shift is True:
            return EventCommand.generic_two_arg(0x8B, x >> 4, y >> 4)

        # Two notes on setting commands by pixels:
        #   (1) You have to multiply pixel number by 16 for the command.
        #       I think the game gets confused if the low order bits are
        #       not 0.
        #   (2) When setting based on pixels, it doesn't seem to match
        #       tiles.  The pixels seem to need to be shifted by 0x80 to
        #       match.
        shift_x, shift_y = 0, 0
        if shift:
            shift_x, shift_y = 0x80, 0x100
        return EventCommand.generic_two_arg(0x8D,
                                            (x << 4) + shift_x,
                                            (y << 4) + shift_y)

    @staticmethod
    def set_string_index(str_ind_rom: int) -> EventCommand:
        return EventCommand.generic_one_arg(0xB8, str_ind_rom)

    @staticmethod
    def special_dialog(dialog_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0xC8, dialog_id)

    @staticmethod
    def rename_character(char_id: int) -> EventCommand:
        return EventCommand.special_dialog(0xC0 | char_id)

    @staticmethod
    def replace_characters() -> EventCommand:
        return EventCommand.special_dialog(0x00)

    @staticmethod
    def decision_box(str_id: int, first_line: int, last_line: int,
                     mode_str: str = 'auto'):
        mode_str = mode_str.lower()
        if mode_str not in ('auto', 'top', 'bottom'):
            mode_str = 'auto'

        if mode_str == 'auto':
            cmd_id = 0xC0
        elif mode_str == 'top':
            cmd_id = 0xC3
        else:
            cmd_id = 0xC4

        if first_line not in range(0, 4):
            raise ValueError('First line must be in range(0, 4)')

        if last_line not in range(0, 4):
            raise ValueError('Last line must be in range(0, 4)')

        lines_byte = first_line << 2
        lines_byte |= last_line

        return EventCommand.generic_command(cmd_id, str_id, lines_byte)

    @staticmethod
    def if_result_equals(result_val: int, jump_bytes) -> EventCommand:
        return EventCommand.generic_command(0x1A, result_val, jump_bytes)

    # TODO: merge these two textbox commands
    @staticmethod
    def auto_text_box(string_id: int) -> EventCommand:
        return EventCommand.generic_one_arg(0xBB, string_id)

    @staticmethod
    def text_box(string_id: int, top: bool = True) -> EventCommand:
        if top:
            return EventCommand.generic_one_arg(0xC1, string_id)

        return EventCommand.generic_one_arg(0xC2, string_id)

    @staticmethod
    def script_speed(speed: int) -> EventCommand:
        speed = min(speed, 0x80)
        return EventCommand.generic_one_arg(0x87, speed)

    @staticmethod
    def pause(duration_secs: float):
        if duration_secs == 0.25:
            return EventCommand.generic_zero_arg(0xB9)
        if duration_secs == 0.5:
            return EventCommand.generic_zero_arg(0xBA)
        if duration_secs == 1:
            return EventCommand.generic_zero_arg(0xBC)
        if duration_secs == 2:
            return EventCommand.generic_zero_arg(0xBD)

        num_ticks = int(duration_secs*0x10)
        return EventCommand.generic_one_arg(0xAD, num_ticks)
    
    @staticmethod
    def animation(animation_id: int, type: str = "Static", loops: int = 0):
        # Handle special cases for animation_id 0 and 1 in Normal mode
        if type == "Normal" and animation_id == 0:
            return EventCommand.generic_zero_arg(0xB3)
        if type == "Normal" and animation_id == 1:
            return EventCommand.generic_zero_arg(0xB4)
            
        # Handle other cases based on type
        if type == "Static":
            return EventCommand.generic_one_arg(0xAC, animation_id)
        elif type == "Normal":
            return EventCommand.generic_one_arg(0xAB, animation_id)
        elif type == "Loop":
            if loops == 0:
                # Infinite loop
                return EventCommand.generic_one_arg(0xAA, animation_id)
            else:
                # Specific number of loops
                return EventCommand.generic_two_arg(0xB7, animation_id, loops)
        else:
            raise ValueError(f"Invalid animation type: {type}")

    @staticmethod
    def animation_limiter(limit: int) -> EventCommand:
        return EventCommand.generic_one_arg(0x47, limit)
    
    @staticmethod
    def random_number(offset: int) -> EventCommand:
        """Generate a random number and store it to script memory."""
        if not is_script_mem(offset):
            raise ValueError('Must store to script memory')
        return EventCommand.generic_one_arg(0x7F, get_offset(offset))

    @staticmethod 
    def get_storyline(addr: int) -> EventCommand:
        """Get storyline counter value into script memory."""
        if not is_script_mem(addr):
            raise ValueError('Must store to script memory')
        return EventCommand.generic_one_arg(0x55, get_offset(addr))

    @staticmethod
    def get_pc1(offset: int) -> EventCommand:
        """Get PC1's ID into script memory."""
        if not is_script_mem(offset):
            raise ValueError('Must store to script memory')
        return EventCommand.generic_one_arg(0x20, get_offset(offset))

    @staticmethod
    def load_ascii(index: int) -> EventCommand:
        """Load ASCII text from index."""
        return EventCommand.generic_one_arg(0x29, index | 0x80)

    @staticmethod
    def change_palette(palette: int) -> EventCommand:
        """Change the calling object's palette."""
        return EventCommand.generic_one_arg(0x33, palette)

    @staticmethod
    def sprite_collision(props: int) -> EventCommand:
        """Set NPC solidity properties."""
        return EventCommand.generic_one_arg(0x84, props)

    @staticmethod
    def equip_item(pc_id: int, item_id: int) -> EventCommand:
        """Equip an item on a PC."""
        return EventCommand.generic_two_arg(0xD5, pc_id, item_id)

    @staticmethod
    def get_item_quantity(item_id: int, store_addr: int) -> EventCommand:
        """Get quantity of item in inventory to script memory."""
        if not is_script_mem(store_addr):
            raise ValueError('Must store to script memory')
        return EventCommand.generic_two_arg(0xD7, item_id, get_offset(store_addr))

    @staticmethod
    def check_gold(amount: int, jump_bytes: int) -> EventCommand:
        """Check if player has enough gold, jump if not enough."""
        if amount > 0xFFFF:
            raise ValueError('Gold amount must be <= 0xFFFF')
        return EventCommand.generic_command(0xCC, amount, jump_bytes)

    @staticmethod
    def add_gold(amount: int) -> EventCommand:
        """Add gold to inventory."""
        if amount > 0xFFFF:  # Using 16-bit limit based on command args
            raise ValueError('Gold amount must be <= 0xFFFF')
        return EventCommand.generic_command(0xCD, amount)

    @staticmethod
    def remove_gold(amount: int) -> EventCommand:
        """Remove gold from inventory."""
        if amount > 0xFFFF:
            raise ValueError('Gold amount must be <= 0xFFFF')
        return EventCommand.generic_command(0xCE, amount)

    @staticmethod
    def check_item(item_id: int, jump_bytes: int) -> EventCommand:
        """Check if item is in inventory, jump if not present."""
        return EventCommand.generic_two_arg(0xC9, item_id, jump_bytes)

    @staticmethod
    def add_item(item_id: int) -> EventCommand:
        """Add item to inventory."""
        return EventCommand.generic_one_arg(0xCA, item_id)

    @staticmethod
    def string_index(address: int) -> EventCommand:
        """Set the string index to given address."""
        return EventCommand.generic_one_arg(0xB8, address)

    @staticmethod
    def special_dialog(dialog_id: int) -> EventCommand:
        """Show special dialog with given ID."""
        return EventCommand.generic_one_arg(0xC8, dialog_id)

    @staticmethod
    def rename_character(char_id: int) -> EventCommand:
        return EventCommand.special_dialog(0xC0 | char_id)

    @staticmethod
    def replace_characters() -> EventCommand:
        return EventCommand.special_dialog(0x00)

    @staticmethod
    def textbox_auto(string_id: int, first_line: int, last_line: int) -> EventCommand:
        """Show auto-positioned textbox.
        Args:
            string_id: ID of string to display
            first_line: First line (0-3)  
            last_line: Last line (0-3)
        """
        if not (0 <= first_line <= 3 and 0 <= last_line <= 3):
            raise ValueError('Line numbers must be between 0 and 3')
        lines_byte = (first_line << 2) | last_line
        return EventCommand.generic_two_arg(0xC0, string_id, lines_byte)

    @staticmethod
    def textbox_top(string_id: int) -> EventCommand:
        """Show textbox at top of screen."""
        return EventCommand.generic_one_arg(0xC1, string_id)

    @staticmethod
    def textbox_bottom(string_id: int) -> EventCommand:
        """Show textbox at bottom of screen."""
        return EventCommand.generic_one_arg(0xC2, string_id)

    @staticmethod
    def textbox_auto_top(string_id: int, first_line: int, last_line: int) -> EventCommand:
        """Show decision box at top."""
        if not (0 <= first_line <= 3 and 0 <= last_line <= 3):
            raise ValueError('Line numbers must be between 0 and 3')
        lines_byte = (first_line << 2) | last_line
        return EventCommand.generic_two_arg(0xC3, string_id, lines_byte)

    @staticmethod
    def textbox_auto_bottom(string_id: int, first_line: int, last_line: int) -> EventCommand:
        """Show decision box at bottom."""
        if not (0 <= first_line <= 3 and 0 <= last_line <= 3):
            raise ValueError('Line numbers must be between 0 and 3')
        lines_byte = (first_line << 2) | last_line
        return EventCommand.generic_two_arg(0xC4, string_id, lines_byte)

    @staticmethod
    def personal_textbox(string_id: int) -> EventCommand:
        """Show personal textbox that closes when leaving."""
        return EventCommand.generic_one_arg(0xBB, string_id)

    @staticmethod
    def remove_item(item_id: int) -> EventCommand:
        """Remove item from inventory."""
        return EventCommand.generic_one_arg(0xCB, item_id)

    @staticmethod
    def add_item_from_mem(addr: int) -> EventCommand:
        """Add item stored in script memory to inventory."""
        if not is_script_mem(addr):
            raise ValueError('Must read from script memory')
        return EventCommand.generic_one_arg(0xC7, get_offset(addr))
    
    @staticmethod
    def get_result(addr: int) -> EventCommand:
        """Get result value into memory location."""
        if is_script_mem(addr):
            return EventCommand.generic_command(0x19, get_offset(addr))
        else:
            return EventCommand.generic_command(0x1C, addr - 0x7F0000)
        
    @staticmethod
    def reset_animation() -> EventCommand:
        return EventCommand.generic_zero_arg(0xAE)
    
    @staticmethod 
    def battle(no_win_pose: bool = False,
              bottom_menu: bool = False,
              small_pc_sol: bool = False,
              unused_108: bool = False,
              static_enemies: bool = False,
              special_event: bool = False,
              unknown_140: bool = False,
              no_run: bool = False,
              unknown_201: bool = False,
              unknown_202: bool = False,
              unknown_204: bool = False,
              unknown_208: bool = False,
              unknown_210: bool = False,
              no_game_over: bool = False,
              map_music: bool = False,
              regroup: bool = False) -> EventCommand:
        """Create a battle command with specified flags.
        
        Each parameter represents a bit flag in the battle command's two bytes.
        """
        # First byte flags
        byte1 = 0
        if no_win_pose: byte1 |= 0x01
        if bottom_menu: byte1 |= 0x02
        if small_pc_sol: byte1 |= 0x04
        if unused_108: byte1 |= 0x08
        if static_enemies: byte1 |= 0x10
        if special_event: byte1 |= 0x20
        if unknown_140: byte1 |= 0x40
        if no_run: byte1 |= 0x80
        
        # Second byte flags
        byte2 = 0
        if unknown_201: byte2 |= 0x01
        if unknown_202: byte2 |= 0x02
        if unknown_204: byte2 |= 0x04
        if unknown_208: byte2 |= 0x08
        if unknown_210: byte2 |= 0x10
        if no_game_over: byte2 |= 0x20
        if map_music: byte2 |= 0x40
        if regroup: byte2 |= 0x80
        
        return EventCommand.generic_command(0xD8, byte1, byte2)
    
    @staticmethod
    def check_button(is_action: bool, button: str, since_last: bool, jump_bytes: int) -> EventCommand:
        """Create a button check command.
        
        Args:
            is_action: True if checking an action (Dash/Confirm), False if checking a specific button
            button: The button or action to check ("A", "B", "Dash", etc.)
            since_last: True to check since last check, False to check current state
            jump_bytes: Number of bytes to jump if check fails
            
        Returns:
            EventCommand: The appropriate button check command
        """
        # Map button/action names to command IDs
        if is_action:
            if since_last:
                cmd_map = {"Dash": 0x3B, "Confirm": 0x3C}
            else:
                cmd_map = {"Dash": 0x30, "Confirm": 0x31}
        else:
            if since_last:
                cmd_map = {
                    "Any": None,  # No "since last" for Any
                    "A": 0x3F, "B": 0x40, "X": 0x41,
                    "Y": 0x42, "L": 0x43, "R": 0x44
                }
            else:
                cmd_map = {
                    "Any": 0x2D,
                    "A": 0x34, "B": 0x35, "X": 0x36,
                    "Y": 0x37, "L": 0x38, "R": 0x39
                }
                
        cmd_id = cmd_map.get(button)
        if cmd_id is None:
            raise ValueError(f"Invalid button/mode combination: {button} {'since last' if since_last else 'current'}")
            
        return EventCommand.generic_one_arg(cmd_id, jump_bytes)
    
    @staticmethod
    def move_sprite(x: int, y: int, animated: bool = False) -> EventCommand:
        """Move sprite to coordinates with optional animation."""
        cmd_id = 0xA0 if animated else 0x96
        return EventCommand.generic_two_arg(cmd_id, x, y)

    @staticmethod
    def move_sprite_from_mem(x_addr: int, y_addr: int, animated: bool = False) -> EventCommand:
        """Move sprite to coordinates stored in memory."""
        if not (is_script_mem(x_addr) and is_script_mem(y_addr)):
            raise ValueError('Addresses must be in script memory')
        cmd_id = 0xA1 if animated else 0x97
        return EventCommand.generic_two_arg(cmd_id, get_offset(x_addr), get_offset(y_addr))

    @staticmethod
    def move_toward_coord(x: int, y: int, distance: int) -> EventCommand:
        """Move toward coordinates with given distance."""
        if not (0 <= x <= 0xFF and 0 <= y <= 0xFF and 0 <= distance <= 0xFF):
            raise ValueError('Coordinates and distance must be 0-FF')
        return EventCommand.generic_command(0x9A, x, y, distance)

    @staticmethod
    def set_movement_properties(through_walls: bool = False, through_pcs: bool = False) -> EventCommand:
        """Set object movement properties."""
        flags = 0
        if through_walls:
            flags |= 0x01
        if through_pcs:
            flags |= 0x02
        return EventCommand.generic_one_arg(0x0D, flags)

    @staticmethod
    def set_destination_properties(onto_tile: bool = False, onto_object: bool = False) -> EventCommand:
        """Set destination properties."""
        flags = 0
        if onto_tile:
            flags |= 0x01
        if onto_object:
            flags |= 0x02
        return EventCommand.generic_one_arg(0x0E, flags)

    @staticmethod
    def move_toward_object(target_id: int, distance: int, is_pc: bool = False, keep_facing: bool = False) -> EventCommand:
        """Move toward an object or PC.
        
        Args:
            target_id: Object number (0-FF) or PC number (1-6)
            distance: Distance to move
            is_pc: True if target is a PC, False if target is an object
            keep_facing: True to maintain current facing during movement
        """
        if is_pc and not 1 <= target_id <= 6:
            raise ValueError("PC number must be between 1 and 6")
        elif not is_pc and not 0 <= target_id <= 0xFF:
            raise ValueError("Object number must be between 0 and FF")
            
        if not 0 <= distance <= 0xFF:
            raise ValueError("Distance must be between 0 and FF")
            
        if is_pc:
            cmd_id = 0x9F if keep_facing else 0x99
        else:
            cmd_id = 0x9E if keep_facing else 0x98
            
        return EventCommand.generic_two_arg(cmd_id, target_id, distance)

    @staticmethod
    def follow_target(target_id: int, is_pc: bool = False, repeat: bool = False) -> EventCommand:
        """Follow an object or PC.
        
        Args:
            target_id: Object number (0-FF) or PC number (1-6)
            is_pc: True if target is a PC, False if target is an object
            repeat: True for continuous following (B5/B6), False for one-time (94/95)
        """
        if is_pc:
            if not 1 <= target_id <= 6:
                raise ValueError("PC number must be between 1 and 6")
            cmd_id = 0xB6 if repeat else 0x95
        else:
            if not 0 <= target_id <= 0xFF:
                raise ValueError("Object number must be between 0 and FF")
            cmd_id = 0xB5 if repeat else 0x94
            
        return EventCommand.generic_one_arg(cmd_id, target_id)

    @staticmethod
    def follow_pc_at_distance(pc_id: int) -> EventCommand:
        """Follow a PC while maintaining distance.
        
        Args:
            pc_id: PC number (1-6)
        """
        if not 1 <= pc_id <= 6:
            raise ValueError("PC number must be between 1 and 6")
        return EventCommand.generic_one_arg(0x8F, pc_id)

    @staticmethod
    def set_speed(speed: int) -> EventCommand:
        """Set movement speed.
        
        Args:
            speed: Speed value (0-FF)
        """
        if not 0 <= speed <= 0xFF:
            raise ValueError("Speed must be between 0 and FF")
        return EventCommand.generic_one_arg(0x89, speed)

    @staticmethod
    def set_speed_from_mem(addr: int) -> EventCommand:
        """Set speed from memory value.
        
        Args:
            addr: Script memory address containing speed value
        """
        if not is_script_mem(addr):
            raise ValueError("Address must be in script memory")
        return EventCommand.generic_one_arg(0x8A, get_offset(addr))

    @staticmethod
    def toggle_bits(address: int, bitmask: int) -> EventCommand:
        """Toggle bits in script memory using bitmask.
        
        Args:
            address: Script memory address (0x7F0200-0x7F0400)
            bitmask: Mask of bits to toggle (0-0xFF)
            
        Returns:
            EventCommand that will toggle specified bits
        """
        if not is_script_mem(address):
            raise ValueError('toggle_bits must operate on script memory.')

        if not address % 2 == 0:
            raise ValueError('toggle_bits must operate on even addresses.')

        if not 0 <= bitmask < 0x100:
            raise ValueError('bitmask must be in [0, 0x100)')

        offset = (address - 0x7F0200)//2
        return EventCommand.generic_two_arg(0x6B, bitmask, offset)

    @staticmethod
    def shift_bits(address: int, shift_amount: int) -> EventCommand:
        """Shift bits right in script memory.
        
        Args:
            address: Script memory address (0x7F0200-0x7F0400)
            shift_amount: Number of bits to shift right
            
        Returns:
            EventCommand that will shift bits right
        """
        if not is_script_mem(address):
            raise ValueError('shift_bits must operate on script memory.')

        if not address % 2 == 0:
            raise ValueError('shift_bits must operate on even addresses.')

        if not 0 <= shift_amount <= 7:
            raise ValueError('shift_amount must be between 0 and 7')

        offset = (address - 0x7F0200)//2
        return EventCommand.generic_two_arg(0x6F, shift_amount, offset)

    @staticmethod
    def set_bit_at_0x7E0154(bit_pattern: int) -> EventCommand:
        """Set specific bits at memory address 0x7E0154.
        
        Args:
            bit_pattern: Which bits to set (0x04, 0x08, or 0x10)
            
        Returns:
            EventCommand that will set the specified bits
        """
        if bit_pattern == 0x04:
            return EventCommand.generic_zero_arg(0x2A)
        elif bit_pattern == 0x08:
            return EventCommand.generic_zero_arg(0x2B)
        elif bit_pattern == 0x10:
            return EventCommand.generic_zero_arg(0x32)
        else:
            raise ValueError('bit_pattern must be 0x04, 0x08 or 0x10')

    @staticmethod
    def add_mem_to_mem(from_addr: int, to_addr: int, num_bytes: int = 1) -> EventCommand:
        """Add value from one memory location to another.
        
        Args:
            from_addr: Source memory address in script memory
            to_addr: Destination memory address in script memory
            num_bytes: Number of bytes (1 or 2)
        """
        if not is_script_mem(from_addr) or not is_script_mem(to_addr):
            raise ValueError('Addresses must be in script memory')
            
        if not from_addr % 2 == 0 or not to_addr % 2 == 0:
            raise ValueError('Addresses must be even')
            
        if num_bytes not in (1, 2):
            raise ValueError('num_bytes must be 1 or 2')
            
        cmd_id = 0x5D if num_bytes == 1 else 0x5E
        return EventCommand.generic_two_arg(cmd_id, get_offset(from_addr), get_offset(to_addr))

    @staticmethod
    def subtract_mem_from_mem(from_addr: int, to_addr: int) -> EventCommand:
        """Subtract value at one memory location from another.
        
        Args:
            from_addr: Source memory address in script memory 
            to_addr: Destination memory address in script memory
        """
        if not is_script_mem(from_addr) or not is_script_mem(to_addr):
            raise ValueError('Addresses must be in script memory')
            
        if not from_addr % 2 == 0 or not to_addr % 2 == 0:
            raise ValueError('Addresses must be even')
            
        return EventCommand.generic_two_arg(0x61, get_offset(from_addr), get_offset(to_addr))

    @staticmethod
    def subtract_value_from_mem(value: int, addr: int, num_bytes: int = 1) -> EventCommand:
        """Subtract value from memory location.
        
        Args:
            value: Value to subtract
            addr: Memory address in script memory
            num_bytes: Number of bytes (1 or 2)
        """
        if not is_script_mem(addr):
            raise ValueError('Address must be in script memory')
            
        if not addr % 2 == 0:
            raise ValueError('Address must be even')

        if num_bytes == 1:
            if not 0 <= value < 0x100:
                raise ValueError('Value must be 0-FF for 1 byte operation')
            cmd_id = 0x5F
        else:
            if not 0 <= value < 0x10000:
                raise ValueError('Value must be 0-FFFF for 2 byte operation')
            cmd_id = 0x60
            
        return EventCommand.generic_two_arg(cmd_id, value, get_offset(addr))

    @staticmethod
    def check_drawn(obj_id: int, jump_bytes: int) -> EventCommand:
        """Check if object is visible, jump if not visible.
        
        Args:
            obj_id (int): Object ID to check
            jump_bytes (int): Number of bytes to jump if not visible
        """
        return EventCommand.generic_two_arg(0x27, obj_id // 2, jump_bytes)

    @staticmethod
    def check_in_battle(obj_id: int, jump_bytes: int) -> EventCommand:
        """Check if object is in battle range, jump if not in range.
        
        Args:
            obj_id (int): Object ID to check
            jump_bytes (int): Number of bytes to jump if not in battle range
        """
        return EventCommand.generic_two_arg(0x28, obj_id // 2, jump_bytes)

    @staticmethod
    def mem_to_mem_compare(address1: int, address2: int, operation: Operation, 
                        num_bytes: int, jump_bytes: int) -> EventCommand:
        """Compare two memory locations.
        
        Args:
            address1: First memory address
            address2: Second memory address 
            operation: Comparison operation to perform
            num_bytes: Number of bytes to compare (1 or 2)
            jump_bytes: Number of bytes to jump if comparison is false
        """
        command_id = 0x15 if num_bytes == 2 else 0x14
        
        if not is_script_mem(address1) or not is_script_mem(address2):
            raise ValueError('Can only compare script memory addresses')
            
        offset1 = get_offset(address1)
        offset2 = get_offset(address2)
        
        return EventCommand.generic_command(
            command_id,
            offset1, 
            offset2,
            int(operation),
            jump_bytes
        )   
    
    # Add to EventCommand class

    @staticmethod
    def color_add(color: int, intensity: int, add_sub_mode: bool = False) -> EventCommand:
        """Create a color addition command.
        
        Args:
            color: BGR color (3 bits)
            intensity: Color intensity (0-1F)
            add_sub_mode: Whether to use add/sub mode (adds additional byte)
        """
        command = EventCommand.generic_command(0xF1, (color << 5) | (intensity & 0x1F))
        if add_sub_mode:
            command.args.append(0x80)
        return command
        
    @staticmethod 
    def scroll_screen(x: int, y: int) -> EventCommand:
        """Scroll screen to coordinates."""
        return EventCommand.generic_command(0xE7, x, y)
        
    @staticmethod
    def shake_screen(enabled: bool) -> EventCommand:
        """Enable/disable screen shake.
        
        Args:
            enabled: True to enable shake, False to disable
        """
        return EventCommand.generic_command(0xF4, 1 if enabled else 0)
        
    @staticmethod
    def wait_for_brighten() -> EventCommand:
        """Wait for brighten effect to complete."""
        return EventCommand.generic_zero_arg(0xF3)

    @staticmethod
    def mem_copy(address: int, bytes: bytearray):
        command = event_commands[0x4E].copy()
        command.arg_lens[-1] = len(bytes)
        command.args = [address & 0xFFFF, (address >> 16) & 0xFF, len(bytes) + 2, bytes]

        return command

    def copy(self) -> EventCommand:
        ret_command = EventCommand(-1, 0, [], [], '', '')
        ret_command.command = self.command
        ret_command.num_args = self.num_args
        ret_command.arg_lens = self.arg_lens[:]
        ret_command.arg_descs = self.arg_descs[:]
        ret_command.name = self.name
        ret_command.desc = self.desc
        ret_command.command_type = self.command_type
        ret_command.command_subtype = self.command_subtype

        ret_command.args = self.args[:]

        return ret_command

    def __len__(self):
        return 1 + sum(self.arg_lens)

    def __str__(self):
        if self.command == 0x4E:
            ret_str = f"{self.command:02X} " + self.name + ' ' + \
                ' '.join(f"{self.args[i]:0{2*self.arg_lens[i]}X}"
                         for i in range(len(self.args)-1))
            ret_str += '('
            ret_str += ' '.join(f'{x:02X}' for x in self.args[-1])
            ret_str += ')'
        else:
            ret_str = f"{self.command:02X} " + self.name + ' ' + \
                ' '.join(f"{self.args[i]:0{2*self.arg_lens[i]}X}"
                         for i in range(len(self.args)))
        return ret_str



# Many descriptions are copied from the db's 'Event\ Commands.txt'
event_commands = \
    [EventCommand(i, -1, [], [], '', '') for i in range(0x100)]

event_commands[0] = \
    EventCommand(0, 0, [], [],
                 'Return',
                 'Returns context, but doesn\'t quit',
                 EventCommandType.END,
                 EventCommandSubtype.END)

event_commands[1] = \
    EventCommand(1, 0, [], [],
                 'Color Crash',
                 'Crashes.  Presumed leftover debug command.',
                 EventCommandType.UNKNOWN,
                 EventCommandSubtype.COLOR_CRASH)

event_commands[2] = \
    EventCommand(2, 2, [1, 1],
                 ['aa: part of offset to pointer to load',
                  'po: p - priority, o-part of Offset to pointer'],
                 'Call Event.',
                 'Call Event.  Will wait only if new thread has higher' +
                 'priority, instantly returns if object is dead or busy',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[3] = \
    EventCommand(3, 2, [1, 1],
                 ['aa: part of offset to pointer to load',
                  'po: p - priority, o - part of offset to pointer'],
                 'Call Event.',
                 'Call Event. waits until execution starts (will wait' +
                 'indefinitely if current thread has lower priority than' +
                 'new one)',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[4] = \
    EventCommand(4, 2, [1, 1],
                 ['aa: part of offset to pointer to load',
                  'po: p - priority, o - part of offset to pointer'],
                 'Call Event',
                 'Call Event. Will wait on execution.',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[5] = \
    EventCommand(5, 2, [1, 1],
                 ['cc: PC',
                  'po: Priority, part of Offset to pointer'],
                 'Call PC Event',
                 'Call PC Event. Will wait only if new thread has higher' +
                 'priority, instantly returns if object is dead or busy',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[6] = \
    EventCommand(6, 2, [1, 1],
                 ['cc: PC',
                  'po: Priority, part of Offset to pointer'],
                 'Call PC Event',
                 'Call PC Event. waits until execution starts (will wait' +
                 'indefinitely if current thread has lower priority than' +
                 'new one)',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[7] = \
    EventCommand(7, 2, [1, 1],
                 ['cc: PC',
                  'po: Priority, part of Offset to pointer'],
                 'Call PC Event',
                 'Call PC Event. Will wait on execution.',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.CALL_OBJ_FUNC)

event_commands[8] = \
    EventCommand(8, 0, [], [],
                 'Object Deactivation',
                 'Turn off object activate & touch (PC can\'t interact)',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.ACTIVATE)

event_commands[9] = \
    EventCommand(9, 0, [], [],
                 'Object Activation',
                 'Turn on object activate & touch.)',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.ACTIVATE)

event_commands[0xA] = \
    EventCommand(0xA, 1, [1],
                 ['oo: Object to remove.'],
                 'Remove Object',
                 'Turn off object activate & touch (PC can\'t interact)',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS)

event_commands[0xB] = \
    EventCommand(0xB, 1, [1],
                 ['oo: Object to disable.'],
                 'Disable Processing.',
                 'Turn off script processing.',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.SCRIPT_PROCESSING)

event_commands[0xC] = \
    EventCommand(0xC, 1, [1],
                 ['oo: Object to enable.'],
                 'Enable Processing.',
                 'Turn on script processing.',
                 EventCommandType.OBJECT_FUNCTION,
                 EventCommandSubtype.SCRIPT_PROCESSING)

event_commands[0xD] = \
    EventCommand(0xD, 1, [1],
                 ['pp: NPC movement properties.'],
                 'NPC Movement Properties.',
                 'Unknown details.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_MOVEMENT_PROPERTIES)

event_commands[0xE] = \
    EventCommand(0xE, 1, [1],
                 ['pp: Position on tile'],
                 'NPC Positioning.',
                 'Unknown details.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.DESTINATION)

event_commands[0xF] = \
    EventCommand(0xF, 0, [],
                 [],
                 'Set NPC Facing (up)',
                 'Overlaps A6 . Should be same with a hard coded 00 value.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x10] = \
    EventCommand(0x10, 1, [1],
                 ['jj: Bytes to jump forward'],
                 'Jump Forward',
                 'Jumps execution forward.',
                 EventCommandType.GOTO,
                 EventCommandSubtype.GOTO)

event_commands[0x11] = \
    EventCommand(0x11, 1, [1],
                 ['jj: Bytes to jump backwards'],
                 'Jump Backwards',
                 'Jumps execution backwards.',
                 EventCommandType.GOTO,
                 EventCommandSubtype.GOTO)

event_commands[0x12] = \
    EventCommand(0x12, 4, [1, 1, 1, 1],
                 ['aa: Offset into SNES memory (*2, + 0x7F0200)',
                  'vv: Value used in operation',
                  'oo: Index for operation pointer',
                  'jj: Bytes to jump of operation evaluates False'],
                 'If',
                 'Jumps execution if condition evaluates false.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.VAL_TO_MEM_COMP)

event_commands[0x13] = \
    EventCommand(0x13, 4, [1, 2, 1, 1],
                 ['aa: Offset into SNES memory (*2, + 0x7F0200)',
                  'vvvv: Value used in operation',
                  'oo: Index for operation pointer',
                  'jj: Bytes to jump of operation evaluates False'],
                 'If',
                 'Jumps execution if operation evaluates false.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.VAL_TO_MEM_COMP)

event_commands[0x14] = \
    EventCommand(0x14, 4, [1, 1, 1, 1],
                 ['aa: Offset into SNES memory (*2, + 0x7F0200)',
                  'bb: Offset into SNES memory (*2, + 0x7F0200)',
                  'oo: Index for operation pointer',
                  'jj: Bytes to jump of operation evaluates False'],
                 'If',
                 'Jumps execution if operation evaluates false.  ' +
                 'Partial overlap with 0x16.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.MEM_TO_MEM_COMP)

event_commands[0x15] = \
    EventCommand(0x15, 4, [1, 1, 1, 1],
                 ['aa: Offset into SNES memory (*2, + 0x7F0200)',
                  'bb: Offset into SNES memory (*2, + 0x7F0200)',
                  'oo: Index for operation pointer',
                  'jj: Bytes to jump of operation evaluates False'],
                 'If',
                 'Jumps execution if operation evaluates false.  ' +
                 'Two byte operand version of 0x14.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.MEM_TO_MEM_COMP)

event_commands[0x16] = \
    EventCommand(0x16, 4, [1, 1, 1, 1],
                 ['aa: Offset into SNES memory (*2, + 0x7F0200)',
                  'vv: Value used in operation.',
                  'oo: Index for operation pointer',
                  'jj: Bytes to jump if operation evaluates False'],
                 'If',
                 'Jumps execution if condition evaluates false.  ' +
                 'Two byte operand version of 0x14.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.VAL_TO_MEM_COMP)

event_commands[0x17] = \
    EventCommand(0x17, 0, [],
                 [],
                 'Set NPC Facing (down)',
                 'Overlaps A6 . Should be same with a hard coded 01 value.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x18] = \
    EventCommand(0x18, 2, [1, 1],
                 ['vv: Storyline point to check for.',
                  'jj: Bytes to jump if storyline point reached or passed.'],
                 'Check Storyline',
                 'Overlaps A6 . Should be same with a hard coded 00 value.',
                 EventCommandType.CHECK_STORYLINE,
                 EventCommandSubtype.CHECK_STORYLINE)

event_commands[0x19] = \
    EventCommand(0x19, 1, [1],
                 ['aa: Address to load result from (*2, +7F0200)'],
                 'Get Result',
                 'Overlaps 1C . Should be same with a hard coded 00 value.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.RESULT)

event_commands[0x1A] = \
    EventCommand(0x1A, 2, [1, 1],
                 ['rr: Target result',
                  'jj: Bytes to jump if result does not match target'],
                 'Jump Result',
                 'Jumps if result does not match target.',
                 EventCommandType.CHECK_RESULT,
                 EventCommandSubtype.CHECK_RESULT)

event_commands[0x1B] = \
    EventCommand(0x1B, 0, [],
                 [],
                 'Set NPC Facing (left)',
                 'Overlaps A6 . Should be same with a hard coded 02 value.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x1C] = \
    EventCommand(0x1C, 1, [2],
                 ['aaaa: Address to load result from (+7F0000)'],
                 'Get Result',
                 'Overlapped by 0x19.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.RESULT)

event_commands[0x1D] = \
    EventCommand(0x1D, 0, [],
                 [],
                 'Set NPC Facing (right)',
                 'Overlaps A6 . Should be same with a hard coded 03 value.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x1E] = \
    EventCommand(0x1E, 1, [1],
                 ['nn: NPC to change facing for.'],
                 'Set NPC Facing (up)',
                 'Overlaps A6.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x1F] = \
    EventCommand(0x1F, 1, [1],
                 ['nn: NPC to change facing for.'],
                 'Set NPC Facing (down)',
                 'Overlaps A6.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x20] = \
    EventCommand(0x20, 1, [1],
                 ['oo: Offset to store to (*2, +7F0200)'],
                 'Get PC1',
                 'Gets PC1 id and stores in memory',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.GET_PC1)

event_commands[0x21] = \
    EventCommand(0x21, 3, [1, 1, 1],
                 ['oo: Object (/2)',
                  'aa: Offset to store X Coord to (*2, +7F0200)',
                  'bb: Offset to store X Coord to (*2, +7F0200)'],
                 'Get Object Coords',
                 'Store object coords to memory.  Overlapped by 0x22.',
                 EventCommandType.OBJECT_COORDINATES,
                 EventCommandSubtype.GET_OBJ_COORD)

event_commands[0x22] = \
    EventCommand(0x22, 3, [1, 1, 1],
                 ['cc: PC (/2)',
                  'aa: Offset to store X Coord to (*2, +7F0200)',
                  'bb: Offset to store X Coord to (*2, +7F0200)'],
                 'Get PC Coords',
                 'Store PC coords to memory.  Overlaps 0x21.',
                 EventCommandType.OBJECT_COORDINATES,
                 EventCommandSubtype.GET_OBJ_COORD)

event_commands[0x23] = \
    EventCommand(0x23, 2, [1, 1],
                 ['cc: PC (/2)',
                  'aa: Offset to store to (*2, +7F0200)'],
                 'Get Obj Facing',
                 'Store object facing to memory.  Overlapped by 0x24.',
                 EventCommandType.FACING,
                 EventCommandSubtype.GET_FACING)

event_commands[0x24] = \
    EventCommand(0x24, 2, [1, 1],
                 ['cc: PC (/2)',
                  'aa: Offset to store to (*2, +7F0200)'],
                 'Get PC Facing',
                 'Store PC facing to memory.  Overlaps 0x23.',
                 EventCommandType.FACING,
                 EventCommandSubtype.GET_FACING)

event_commands[0x25] = \
    EventCommand(0x25, 1, [1],
                 ['nn: NPC to change facing for.'],
                 'Set NPC Facing (left)',
                 'Overlaps A6.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x26] = \
    EventCommand(0x26, 1, [1],
                 ['nn: NPC to change facing for.'],
                 'Set NPC Facing (right)',
                 'Overlaps A6.',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0x27] = \
    EventCommand(0x27, 2, [1, 1],
                 ['oo: Object Number (/2)',
                  'jj: Bytes to jump if object is not visible.'],
                 'Check Object Status',
                 'Jump when object is not visible' +
                 '(offcreen, not loaded, hidden)',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.CHECK_DRAWN)

event_commands[0x28] = \
    EventCommand(0x28, 2, [1, 1],
                 ['oo: Object Number (/2)',
                  'jj: Bytes to jump if object is not in battle range.'],
                 'Check Battle Range',
                 'Jump when object is out or range for battle.',
                 EventCommandType.COMPARISON,
                 EventCommandSubtype.CHECK_IN_BATTLE)

event_commands[0x29] = \
    EventCommand(0x29, 1, [1],
                 ['ii: Index (+0x80)'],
                 'Load ASCII text',
                 'Loads ASCII text from 0x3DA000',
                 EventCommandType.TEXT,
                 EventCommandSubtype.LOAD_ASCII)

event_commands[0x2A] = \
    EventCommand(0x2A, 0, [],
                 [],
                 'Unknown 0x2A',
                 'Sets 0x04 Bit of 0x7E0154',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.SET_AT)

event_commands[0x2B] = \
    EventCommand(0x2B, 0, [],
                 [],
                 'Unknown 0x2B',
                 'Sets 0x08 Bit of 0x7E0154',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.SET_AT)

event_commands[0x2C] = \
    EventCommand(0x2C, 2, [1, 1],
                 ['Unknown', 'Unknown'],
                 'Unknown 0x2C',
                 'Unknown',
                 EventCommandType.UNKNOWN,
                 EventCommandSubtype.UNKNOWN)

event_commands[0x2D] = \
    EventCommand(0x2D, 1, [1],
                 ['jj: Bytes to jump if no button pressed.'],
                 'Check Button Pressed',
                 'Jumps if no buttons are pressed (0x7E00F8',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x2E] = \
    EventCommand(0x2E, 1, [1],
                 ['m?: Mode'],
                 'Color Math',
                 'No description given.',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.COLOR_MATH)

event_commands[0x2F] = \
    EventCommand(0x2F, 2, [1, 1],
                 ['??: Unknown', '??: Unknown'],
                 'Unknown 0x2F',
                 'Unknown.  Stores to 0x7E0BE3 and 0x7E0BE4.' +
                 'Appears to have something to do with scrolling layers',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.SCROLL_LAYERS_2F)

event_commands[0x30] = \
    EventCommand(0x30, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No Dash',
                 'Jump if dash is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x31] = \
    EventCommand(0x31, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No Confirm',
                 'Jump if confirm button is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x32] = \
    EventCommand(0x32, 0, [],
                 [],
                 'Unknown 0x32',
                 'Overlaps 0x2A, sets 0x10 Bit of 0x7E0154.',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.SET_AT)

event_commands[0x33] = \
    EventCommand(0x33, 1, [1],
                 ['pp: palette to change to.'],
                 'Change Palette',
                 'Changes the calling object\'s palette.',
                 EventCommandType.PALETTE,
                 EventCommandSubtype.CHANGE_PALETTE)

event_commands[0x34] = \
    EventCommand(0x34, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump A Button',
                 'Jump if A is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x35] = \
    EventCommand(0x35, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump B Button',
                 'Jump if B is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x36] = \
    EventCommand(0x36, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump X Button',
                 'Jump if X is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x37] = \
    EventCommand(0x37, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump Y Button',
                 'Jump if Y is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x38] = \
    EventCommand(0x38, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump L Button',
                 'Jump if L is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x39] = \
    EventCommand(0x39, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump R Button',
                 'Jump if R is not pressed.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x3A] = event_commands[0x01]
event_commands[0x3A].command = 0x3A
event_commands[0x3A].desc += 'Alias of 0x01.'

event_commands[0x3B] = \
    EventCommand(0x3B, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No Dash',
                 'Jump if dash has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x3C] = \
    EventCommand(0x3C, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No Confirm',
                 'Jump if confirm has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x3D] = event_commands[0x01]
event_commands[0x3D].command = 0x3D
event_commands[0x3D].desc += 'Alias of 0x01.'

event_commands[0x3E] = event_commands[0x01]
event_commands[0x3E].command = 0x3E
event_commands[0x3E].desc += 'Alias of 0x01.'

event_commands[0x3F] = \
    EventCommand(0x3F, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No A',
                 'Jump if A has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x40] = \
    EventCommand(0x40, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No B',
                 'Jump if B has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x41] = \
    EventCommand(0x41, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No X',
                 'Jump if X has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x42] = \
    EventCommand(0x42, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No Y',
                 'Jump if Y has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x43] = \
    EventCommand(0x43, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No L',
                 'Jump if L has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x44] = \
    EventCommand(0x44, 1, [1],
                 ['jj: Number of bytes to jump'],
                 'Jump No R',
                 'Jump if R has not been pressed since last check.',
                 EventCommandType.CHECK_BUTTON,
                 EventCommandSubtype.CHECK_BUTTON)

event_commands[0x45] = event_commands[0x01]
event_commands[0x45].command = 0x45
event_commands[0x45].desc += 'Alias of 0x01.'

event_commands[0x46] = event_commands[0x01]
event_commands[0x46].command = 0x46
event_commands[0x46].desc += 'Alias of 0x01.'

event_commands[0x47] = \
    EventCommand(0x47, 1, [1],
                 ['ll: limit on animations (unknown meaning).'],
                 'Animation Limiter',
                 'Limits which animations can be performed.  ' +
                 'Used to avoid slowdown in high activity scenes.',
                 EventCommandType.ANIMATION,
                 EventCommandSubtype.ANIMATION_LIMITER)

event_commands[0x48] = \
    EventCommand(0x48, 2, [3, 1],
                 ['aaaaaa: Address to load from.',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment',
                 'Assign from any address to local script memory (1 byte)',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x49] = \
    EventCommand(0x49, 2, [3, 1],
                 ['aaaaaa: Address to load from.',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment',
                 'Assign from any address to local script memory (2 bytes)',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x4A] = \
    EventCommand(0x4A, 2, [3, 1],
                 ['aaaaaa: SNES Address to store to.',
                  'vv: Value to load'],
                 'Assignment',
                 'Assign value (1 byte) to any memory address.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x4B] = \
    EventCommand(0x4B, 2, [3, 2],
                 ['aaaaaa: SNES Address to store to.',
                  'vvvv: Value to load'],
                 'Assignment',
                 'Assign value (2 byte) to any memory address.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x4C] = \
    EventCommand(0x4C, 2, [3, 1],
                 ['aaaaaa: SNES Address to store to.',
                  'oo: Offset to load from (*2, +7F0200)'],
                 'Assignment',
                 'Assign value (1 byte) to local script memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x4D] = \
    EventCommand(0x4D, 2, [3, 1],
                 ['aaaaaa: SNES Address to store to.',
                  'oo: Offset to load from (*2, +7F0200)'],
                 'Assignment',
                 'Assign value (2 bytes) to local script memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

# Will need special case in parser
event_commands[0x4E] = \
    EventCommand(0x4E, 4, [2, 1, 2, 1],
                 ['aaaa: Destination bank address',
                  'bb: Destination bank',
                  'cc: Bytes to copy + 2.  Data follows command.'],
                 'Memory Copy',
                 'Copy data from script to memory',
                 EventCommandType.MEM_COPY,
                 EventCommandSubtype.MEM_COPY)

event_commands[0x4F] = \
    EventCommand(0x4F, 2, [1, 1],
                 ['vv: Value to store',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Val to Mem)',
                 'Assign value (1 byte) to local script memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x50] = \
    EventCommand(0x50, 2, [2, 1],
                 ['vvvv: Value to store',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Val to Mem)',
                 'Assign value (2 bytes) to local script memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x51] = \
    EventCommand(0x51, 2, [1, 1],
                 ['aa: Offset to load from (*2, +7F0200)',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Mem to Mem)',
                 'Assign local memory to local memory (1 byte).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x52] = \
    EventCommand(0x52, 2, [1, 1],
                 ['aa: Offset to load from (*2, +7F0200)',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Mem to Mem)',
                 'Assign local memory to local memory (2 bytes).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x53] = \
    EventCommand(0x53, 2, [2, 1],
                 ['aaaa: Offset to load from (+7F0000)',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Mem to Mem)',
                 'Assign bank 7F memory to local memory (1 byte).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x54] = \
    EventCommand(0x54, 2, [2, 1],
                 ['aaaa: Offset to load from (+7F0000)',
                  'oo: Offset to store to (*2, +7F0200)'],
                 'Assignment (Mem to Mem)',
                 'Assign bank 7F memory to local memory (2 bytes).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x55] = \
    EventCommand(0x55, 1, [1],
                 ['oo: Offset to store to (*2, +7F0200)'],
                 'Get Storyline Counter',
                 'Assign storyline counter to local memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.GET_STORYLINE)

event_commands[0x56] = \
    EventCommand(0x56, 2, [1, 2],
                 ['vv: Value to Store',
                  'aaaa: Offset to store to (+7F0000)'],
                 'Assignment (Value to Mem)',
                 'Assign value to bank 7F memory.',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x57] = \
    EventCommand(0x57, 0, [],
                 [],
                 'Load Crono',
                 'Load Crono if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x58] = \
    EventCommand(0x58, 2, [1, 2],
                 ['oo: Offset to load from (*2, +7F0200)',
                  'aaaa: Address to store to (+7F0000)'],
                 'Assignment (Mem to Mem)',
                 'Assign local memory to bank 7F memory (1 byte).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x59] = \
    EventCommand(0x59, 2, [1, 2],
                 ['oo: Offset to load from (*2, +7F0200)',
                  'aaaa: Address to store to (+7F0000)'],
                 'Assignment (Mem to Mem)',
                 'Assign local memory to bank 7F memory (2 bytes).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.MEM_TO_MEM_ASSIGN)

event_commands[0x5A] = \
    EventCommand(0x5A, 1, [1],
                 ['vv: Value to assign'],
                 'Assign Storyline',
                 'Assign value to storyline (0x7F0000)',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.SET_STORYLINE)

event_commands[0x5B] = \
    EventCommand(0x5B, 2, [1, 1],
                 ['vv: Value to add',
                  'oo: Offset in memory to add to (*2, +7F0200)'],
                 'Add (Val to Mem)',
                 'Add a value to local memory.',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x5C] = \
    EventCommand(0x5C, 0, [],
                 [],
                 'Load Marle',
                 'Load Marle if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x5D] = \
    EventCommand(0x5D, 2, [1, 1],
                 ['oo: Offset in memory to load from (*2, +7F0200)',
                  'aa: Offset in memory to add to (*2, +7F0200)'],
                 'Add (Mem to Mem)',
                 'Add from local memory to local memory (1 byte)',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.MEM_TO_MEM_BYTE)

event_commands[0x5E] = \
    EventCommand(0x5E, 2, [1, 1],
                 ['oo: Offset in memory to load from (*2, +7F0200)',
                  'aa: Offset in memory to add to (*2, +7F0200)'],
                 'Add (Mem to Mem)',
                 'Add from local memory to local memory (2 bytes)',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.MEM_TO_MEM_BYTE)

event_commands[0x5F] = \
    EventCommand(0x5F, 2, [1, 1],
                 ['vv: Value to subtract',
                  'oo: Offset in memory to subtract from (*2, +7F0200)'],
                 'Subtract (Val to Mem)',
                 'Subtract a value from local memory (1 byte).',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x60] = \
    EventCommand(0x60, 2, [2, 1],
                 ['vvvv: Value to subtract',
                  'oo: Offset in memory to subtract from (*2, +7F0200)'],
                 'Subtract (Val to Mem)',
                 'Subtract a value from local memory (2 bytes).',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x61] = \
    EventCommand(0x61, 2, [1, 1],
                 ['oo: Offset in memory to load from (*2, +7F0200)',
                  'aa: Offset in memory to subtract from (*2, +7F0200)'],
                 'Add (Mem to Mem)',
                 'Subtract local memory from local memory (1 byte?)',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.MEM_TO_MEM_BYTE)

event_commands[0x62] = \
    EventCommand(0x62, 0, [],
                 [],
                 'Load Lucca',
                 'Load Lucca if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x63] = \
    EventCommand(0x63, 2, [1, 1],
                 ['bb: Bit to set.',
                  'oo: Offset in memory to set bit in (*2, +7F0200)'],
                 'Set Bit',
                 'Set bit in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x64] = \
    EventCommand(0x64, 2, [1, 1],
                 ['bb: Bit to reset.',
                  'oo: Offset in memory to reset bit in (*2, +7F0200)'],
                 'Reset Bit',
                 'Reset bit in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x65] = \
    EventCommand(0x65, 2, [1, 1],
                 ['bs: 0x80 set -> add 0x100 to aa. Set bit 0x1 << s.',
                  'aa: Offset in memory to set bit in (+7F0000)'],
                 'Set Bit',
                 'Set bit in bank 7F.  Usually storyline-related.',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x66] = \
    EventCommand(0x66, 2, [1, 1],
                 ['bs: 0x80 set -> add 0x100 to aa. Reset bit 0x1 << s.',
                  'aa: Offset in memory to reset bit in (+7F0000)'],
                 'Reset Bit',
                 'Reset bit in bank 7F.  Usually storyline-related.',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x67] = \
    EventCommand(0x67, 2, [1, 1],
                 ['bb: Bits to keep.'
                  'oo: Offset in memory to reset bits in (*2, +7F0200)'],
                 'Reset Bits',
                 'Reset bits in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x68] = \
    EventCommand(0x68, 0, [],
                 [],
                 'Load Frog',
                 'Load Frog if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x69] = \
    EventCommand(0x69, 2, [1, 1],
                 ['bb: Bits to set.'
                  'oo: Offset in memory to reset bits in (*2, +7F0200)'],
                 'Set Bits',
                 'Set bits in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x6A] = \
    EventCommand(0x6A, 0, [],
                 [],
                 'Load Robo',
                 'Load Robo if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x6B] = \
    EventCommand(0x6B, 2, [1, 1],
                 ['bb: Bits to toggle.'
                  'oo: Offset in memory to toggle bits in (*2, +7F0200)'],
                 'Toggle Bits',
                 'Toggle bits in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.BIT_MATH)

event_commands[0x6C] = \
    EventCommand(0x6C, 0, [],
                 [],
                 'Load Ayla',
                 'Load Ayla if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x6D] = \
    EventCommand(0x6D, 0, [],
                 [],
                 'Load Magus',
                 'Load Magus if in party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x6E] = event_commands[0x01]
event_commands[0x6E].command = 0x46
event_commands[0x6E].desc += 'Alias of 0x01.'

event_commands[0x6F] = \
    EventCommand(0x6F, 2, [1, 1],
                 ['ss: length of shift.'
                  'oo: Offset in memory to shift bits in (*2, +7F0200)'],
                 'Shift Bits',
                 'Shift bits in local memory',
                 EventCommandType.BIT_MATH,
                 EventCommandSubtype.DOWNSHIFT)

event_commands[0x70] = event_commands[0x01]
event_commands[0x70].command = 0x70
event_commands[0x70].desc += 'Alias of 0x01.'

event_commands[0x71] = \
    EventCommand(0x71, 1, [1],
                 ['oo: Offset to increment (*2, +7F0200)'],
                 'Increment',
                 'Increment local memory (1 byte).',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x72] = \
    EventCommand(0x72, 1, [1],
                 ['oo: Offset to increment (*2, +7F0200)'],
                 'Increment',
                 'Increment local memory (2 bytes).',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x73] = \
    EventCommand(0x73, 1, [1],
                 ['oo: Offset to decrement (*2, +7F0200)'],
                 'Decrement',
                 'Decrement local memory (1 byte).',
                 EventCommandType.BYTE_MATH,
                 EventCommandSubtype.VAL_TO_MEM_BYTE)

event_commands[0x74] = event_commands[0x01]
event_commands[0x74].command = 0x74
event_commands[0x74].desc += 'Alias of 0x01.'

event_commands[0x75] = \
    EventCommand(0x75, 1, [1],
                 ['oo: Offset to set (*2, +7F0200)'],
                 'Set Byte',
                 'Set local memory to 1 (0xFF?) (1 byte).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x76] = \
    EventCommand(0x76, 1, [1],
                 ['oo: Offset to set (*2, +7F0200)'],
                 'Set Byte',
                 'Set local memory to 1 (0xFF?) (2 bytes).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x77] = \
    EventCommand(0x77, 1, [1],
                 ['oo: Offset to set (*2, +7F0200)'],
                 'Reset Byte',
                 'Reset local memory to 0 (1 byte?).',
                 EventCommandType.ASSIGNMENT,
                 EventCommandSubtype.VAL_TO_MEM_ASSIGN)

event_commands[0x78] = event_commands[0x01]
event_commands[0x78].command = 0x78
event_commands[0x78].desc += 'Alias of 0x01.'

event_commands[0x79] = event_commands[0x01]
event_commands[0x79].command = 0x79
event_commands[0x79].desc += 'Alias of 0x01.'

event_commands[0x7A] = \
    EventCommand(0x7A, 3, [1, 1, 1],
                 ['xx: X-coordinate of jump',
                  'yy: Y-coordinate of jump',
                  'hh: height/speed of jump'],
                 'NPC Jump',
                 'Jump NPC to an unoccupied, walkable spot.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.JUMP)

event_commands[0x7B] = \
    EventCommand(0x7B, 4, [1, 1, 1, 1],
                 ['dd: Related to destination',
                  'ee: Related to destination',
                  'ff: Speed/Height?',
                  'gg: Speed/Height?'],
                 'NPC Jump',
                 'Unused command related to NPC jumping.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.JUMP_7B)

event_commands[0x7C] = \
    EventCommand(0x7C, 1, [1],
                 ['oo: Object to turn drawing on for.'],
                 'Turn Drawing On',
                 'Turn drawing on for the given object.  Overlaps 0x90.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS_FROM_MEM)

event_commands[0x7D] = \
    EventCommand(0x7D, 1, [1],
                 ['oo: Object to turn drawing off for.'],
                 'Turn Drawing Off',
                 'Turn drawing off for the given object.  Overlaps 0x90.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS_FROM_MEM)

event_commands[0x7E] = \
    EventCommand(0x7E, 0, [],
                 [],
                 'Turn Drawing Off',
                 'Turn drawing off.  Uses value 80.  Overlaps 0x90.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS)

event_commands[0x7F] = \
    EventCommand(0x7F, 1, [1],
                 ['oo: Offset to store random number at (*2, +7F0200)'],
                 'Random',
                 'Load random data into local memory.',
                 EventCommandType.RANDOM_NUM,
                 EventCommandSubtype.RANDOM_NUM)

event_commands[0x80] = \
    EventCommand(0x80, 1, [1],
                 ['cc: PC to load'],
                 'Load PC',
                 'Load PC if the PC is in the party.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x81] = \
    EventCommand(0x81, 1, [1],
                 ['xx: PC to load'],
                 'Load PC',
                 'Load PC regardless of party status.',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x82] = \
    EventCommand(0x82, 1, [1],
                 ['xx: PC to load'],
                 'Load NPC',
                 'Load NPC',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x83] = \
    EventCommand(0x83, 2, [1, 1],
                 ['ee: Enemy to load',
                  'ii: Enemy Data (0x80 status, 0x7F slot)'],
                 'Load Enemy',
                 'Load Enemy into given target slot',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.LOAD_SPRITE)

event_commands[0x84] = \
    EventCommand(0x84, 1, [1],
                 ['pp: NPC solidity properties'],
                 'NPC Solidity',
                 'Alter NPC solidity properties',
                 EventCommandType.SPRITE_COLLISION,
                 EventCommandSubtype.SPRITE_COLLISION)

event_commands[0x85] = event_commands[0x01]
event_commands[0x85].command = 0x85
event_commands[0x85].desc += 'Alias of 0x01.'

event_commands[0x86] = event_commands[0x01]
event_commands[0x86].command = 0x86
event_commands[0x86].desc += 'Alias of 0x01.'

event_commands[0x87] = \
    EventCommand(0x87, 1, [1],
                 ['ss: Script Timing (0 fastest, 0x80 stop)'],
                 'Script Speed',
                 'Alter speed of script execution.',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.SCRIPT_SPEED)

# Argument number varies depending on mode
event_commands[0x88] = \
    EventCommand(0x88, 1, [1],
                 ['m?: mode'],
                 'Mem Copy',
                 'Long description in db.',
                 EventCommandType.MEM_COPY,
                 EventCommandSubtype.MULTI_MODE)

event_commands[0x89] = \
    EventCommand(0x89, 1, [1],
                 ['ss: Speed of movement'],
                 'NPC Speed',
                 'Alter speed of NPCs.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.SET_SPEED)

event_commands[0x8A] = \
    EventCommand(0x8A, 1, [1],
                 ['oo: Offset to load speed from (*2, 7F0200)'],
                 'NPC Speed',
                 'Alter speed of NPCs from local memory.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.SET_SPEED_FROM_MEM)

event_commands[0x8B] = \
    EventCommand(0x8B, 2, [1, 1],
                 ['xx: X-coordinate',
                  'yy: Y-coordinate'],
                 'Set Object Position',
                 'Place object at given coordinates.',
                 EventCommandType.OBJECT_COORDINATES,
                 EventCommandSubtype.SET_OBJ_COORD)

event_commands[0x8C] = \
    EventCommand(0x8C, 2, [1, 1],
                 ['aa: Offset to load x-coordinate from (*2, 7F0200)',
                  'bb: Offset to load y-coordinate from (*2, 7F0200)'],
                 'Set Object Position',
                 'Place object at given coordinates from local memory.',
                 EventCommandType.OBJECT_COORDINATES,
                 EventCommandSubtype.SET_OBJ_COORD_FROM_MEM)

event_commands[0x8D] = \
    EventCommand(0x8D, 2, [2, 2],
                 ['xxxx: X-coordinate in pixels',
                  'yyyy: Y-coordinate in pixels'],
                 'Set Object Pixel Position',
                 'Place object at given pixel coordinates.',
                 EventCommandType.OBJECT_COORDINATES,
                 EventCommandSubtype.SET_OBJ_COORD)

event_commands[0x8E] = \
    EventCommand(0x8E, 1, [1],
                 ['pp: Priority (0x80 mode, rest ???)'],
                 'Set Sprite Priority',
                 'Set Sprite Priority',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.SPRITE_PRIORITY)

event_commands[0x8F] = \
    EventCommand(0x8F, 1, [1],
                 ['cc: PC to follow'],
                 'Follow at Distance',
                 'Follow the given character at a distance.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_FOLLOW)

event_commands[0x90] = \
    EventCommand(0x90, 0, [],
                 [],
                 'Drawing On',
                 'Turn object drawing on',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS)

event_commands[0x91] = \
    EventCommand(0x91, 0, [],
                 [],
                 'Drawing On',
                 'Turn object drawing off. Uses value 00 (?). Overlaps 0x90',
                 EventCommandType.SPRITE_DRAWING,
                 EventCommandSubtype.DRAW_STATUS)

event_commands[0x92] = \
    EventCommand(0x92, 2, [1, 1],
                 ['dd: Direction of movement (0x40 = 90 deg, 0 = right)',
                  'mm: Magnitude of movement'],
                 'Vector Move',
                 'Move object along given vector.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.VECTOR_MOVE)

event_commands[0x93] = event_commands[0x01]
event_commands[0x93].command = 0x93
event_commands[0x93].desc += 'Alias of 0x01.'

event_commands[0x94] = \
    EventCommand(0x94, 1, [1],
                 ['oo: Object to follow'],
                 'Follow Object',
                 'Follow the given object.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_FOLLOW)

event_commands[0x95] = \
    EventCommand(0x95, 1, [1],
                 ['cc: PC to follow'],
                 'Follow PC',
                 'Follow the given PC',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_FOLLOW)

event_commands[0x96] = \
    EventCommand(0x96, 2, [1, 1],
                 ['xx: X-coordinate',
                  'yy: Y-coordinate'],
                 'NPC move',
                 'Move the given NPC (to given coordinates? vector?)',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_SPRITE)

event_commands[0x97] = \
    EventCommand(0x97, 2, [1, 1],
                 ['aa: Offset to load x-coordinate from (*2, 7F0200)',
                  'bb: Offset to load y-coordinate from (*2, 7F0200)'],
                 'NPC move',
                 'Move the given NPC with coordinates from local memory.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_SPRITE_FROM_MEM)

event_commands[0x98] = \
    EventCommand(0x98, 2, [1, 1],
                 ['oo: Object',
                  'mm: Distance to travel'],
                 'Move Toward',
                 'Move toward the given object.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_TOWARD_OBJ)

event_commands[0x99] = \
    EventCommand(0x99, 2, [1, 1],
                 ['cc: PC',
                  'mm: Distance to travel'],
                 'Move Toward',
                 'Move toward the given PC. Overlaps 0x98.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_TOWARD_OBJ)

event_commands[0x9A] = \
    EventCommand(0x9A, 3, [1, 1],
                 ['xx: X-coordinate',
                  'yy: Y-coordinate',
                  'mm: Distance to travel'],
                 'Move Toward Coordinates',
                 'Move toward the given coordinates.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_TOWARD_COORD)

event_commands[0x9B] = event_commands[0x01]
event_commands[0x9B].command = 0x9B
event_commands[0x9B].desc += 'Alias of 0x01.'

event_commands[0x9C] = \
    EventCommand(0x9C, 2, [1, 1],
                 ['dd: Direction of movement (0x40 = 90 deg, 0 = right)',
                  'mm: Magnitude of movement'],
                 'Vector Move',
                 'Move object along given vector.  Does not change facing.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.VECTOR_MOVE)

event_commands[0x9D] = \
    EventCommand(0x9D, 2, [1, 1],
                 ['aa: Offset to load direction from (*2, +7F0200)' +
                  '(0x40 = 90 deg, 0 = right)',
                  'bb: Offset to load magnitude from (*2, +7F0200)'],
                 'Vector Move',
                 'Move object along given vector.  Does not change facing.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.VECTOR_MOVE_FROM_MEM)

event_commands[0x9E] = \
    EventCommand(0x9D, 1, [1],
                 ['oo: Object (/2) to move to'],
                 'Vector Move to Object',
                 'Move to given object. Does not change facing.  ' +
                 'Overlapped by 0x9F',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_TOWARD_OBJ)

event_commands[0x9F] = \
    EventCommand(0x9D, 1, [1],
                 ['oo: Object (/2) to move to'],
                 'Vector Move to Object',
                 'Move to given object. Does not change facing.  ' +
                 'Overlaps 0x9E',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_TOWARD_OBJ)

event_commands[0xA0] = \
    EventCommand(0xA0, 2, [1, 1],
                 ['xx: X-coordinate.',
                  'yy: Y-coordinate.'],
                 'Animated Move',
                 'Move while playing an animation.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_SPRITE)

event_commands[0xA1] = \
    EventCommand(0xA1, 2, [1, 1],
                 ['aa: Offset (*2, +7F0200) to load x-coordinate from',
                  'bb: Offset (*2, +7F0200) to load y-coordinate from'],
                 'Animated Move',
                 'Move while playing an animation.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_SPRITE_FROM_MEM)

event_commands[0xA2] = event_commands[0x01]
event_commands[0xA2].command = 0xA2
event_commands[0xA2].desc += 'Alias of 0x01.'

event_commands[0xA3] = event_commands[0x01]
event_commands[0xA3].command = 0xA3
event_commands[0xA3].desc += 'Alias of 0x01.'

event_commands[0xA4] = event_commands[0x01]
event_commands[0xA4].command = 0xA4
event_commands[0xA4].desc += 'Alias of 0x01.'

event_commands[0xA5] = event_commands[0x01]
event_commands[0xA5].command = 0xA5
event_commands[0xA5].desc += 'Alias of 0x01.'

event_commands[0xA6] = \
    EventCommand(0xA6, 1, [1],
                 ['ff: Facing (0 = up, 1 = down, 2 = left, 3 = right)'],
                 'NPC Facing',
                 'Set NPC facing. Overlapped by 0x17',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING)

event_commands[0xA7] = \
    EventCommand(0xA7, 1, [1],
                 ['oo: Offset to load facing from (*2, +7F0200)'],
                 'NPC Facing',
                 'Set NPC facing. Overlaps 0xA6',
                 EventCommandType.FACING,
                 EventCommandSubtype.SET_FACING_FROM_MEM)

event_commands[0xA8] = \
    EventCommand(0xA8, 1, [1],
                 ['oo: Object (/2) to face.'],
                 'NPC Facing',
                 'Set NPC to face object. Overlapped by 0xA9.',
                 EventCommandType.FACING,
                 EventCommandSubtype.FACE_OBJECT)

event_commands[0xA9] = \
    EventCommand(0xA9, 1, [1],
                 ['cc: PC (/2) to face.'],
                 'NPC Facing',
                 'Set NPC to face PC. Overlaps 0xA9.',
                 EventCommandType.FACING,
                 EventCommandSubtype.FACE_OBJECT)

event_commands[0xAA] = \
    EventCommand(0xAA, 1, [1],
                 ['aa: Animation to play'],
                 'Animation',
                 'Play animation. Loops.', 
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xAB] = \
    EventCommand(0xAB, 1, [1],
                 ['aa: Animation to play'],
                 'Animation',
                 'Play animation.', 
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xAC] = \
    EventCommand(0xAC, 1, [1],
                 ['aa: Animation to play'],
                 'Static Animation',
                 'Play static animation.', 
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xAD] = \
    EventCommand(0xAD, 1, [1],
                 ['tt: Time to wait in 1/16 seconds.'],
                 'Pause',
                 'Pause',
                 EventCommandType.PAUSE,
                 EventCommandSubtype.PAUSE)

event_commands[0xAE] = \
    EventCommand(0xAE, 0, [],
                 [],
                 'Reset Animation',
                 'Resets the object\'s animation.',
                 EventCommandType.ANIMATION,
                 EventCommandSubtype.RESET_ANIMATION)

event_commands[0xAF] = \
    EventCommand(0xAF, 0, [],
                 [],
                 'Exploration.',
                 'Allows player to control PCs (single controller check).',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.CONTROLLABLE)

event_commands[0xB0] = \
    EventCommand(0xB0, 0, [],
                 [],
                 'Exploration.',
                 'Allows player to control PCs (infinite controller check).',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.CONTROLLABLE)

event_commands[0xB1] = \
    EventCommand(0xB1, 0, [],
                 [],
                 'Break',
                 'End command for arbitrary access contexts.  ' +
                 'Sets conditions for loops to end.  ' +
                 'Advances to next command.')

event_commands[0xB2] = \
    EventCommand(0xB2, 0, [],
                 [],
                 'End',
                 'End command for arbitrary access contexts.  ' +
                 'Sets conditions for loops to end.')

event_commands[0xB3] = \
    EventCommand(0xB3, 0, [],
                 [],
                 'Animation',
                 'Should be equivalent to 0xAA with hardcoded 00',
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xB4] = \
    EventCommand(0xB4, 0, [],
                 [],
                 'Animation',
                 'Should be equivalent to 0xAA with hardcoded 01',
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xB5] = \
    EventCommand(0xB5, 1, [1],
                 ['oo: Object'],
                 'Move to Object',
                 'Loops 0x94.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_FOLLOW)

event_commands[0xB6] = \
    EventCommand(0xB6, 1, [1],
                 ['cc: PC'],
                 'Move to PC',
                 'Loops 0x95.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.OBJECT_FOLLOW)

event_commands[0xB7] = \
    EventCommand(0xB7, 2, [1, 1],
                 ['aa: Animation',
                  'll: Number of loops'],
                 'Loop Animation',
                 'Play animation some number of times.',
                 EventCommandType.ANIMATION, 
                 EventCommandSubtype.ANIMATION)

event_commands[0xB8] = \
    EventCommand(0xB8, 1, [3],
                 ['aaaaaa: Address to set string index to.'],
                 'String Index',
                 'Sets String Index.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.STRING_INDEX)

event_commands[0xB9] = \
    EventCommand(0xB9, 0, [],
                 [],
                 'Pause 1/4',
                 'Pauses 1/4 second.',
                 EventCommandType.PAUSE,
                 EventCommandSubtype.PAUSE)

event_commands[0xBA] = \
    EventCommand(0xBA, 0, [],
                 [],
                 'Pause 1/2',
                 'Pauses 1/2 second.',
                 EventCommandType.PAUSE,
                 EventCommandSubtype.PAUSE)

event_commands[0xBB] = \
    EventCommand(0xBB, 1, [1],
                 ['ss: String displayed'],
                 'Personal Textbox',
                 'Displays textbox.  Closes after leaving.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xBC] = \
    EventCommand(0xBC, 0, [],
                 [],
                 'Pause 1',
                 'Pauses 1 second.',
                 EventCommandType.PAUSE,
                 EventCommandSubtype.PAUSE)

event_commands[0xBD] = \
    EventCommand(0xBD, 0, [],
                 [],
                 'Pause 2',
                 'Pauses 2 seconds.',
                 EventCommandType.PAUSE,
                 EventCommandSubtype.PAUSE)

event_commands[0xBE] = event_commands[0x01]
event_commands[0xBE].command = 0xBE
event_commands[0xBE].desc += 'Alias of 0x01.'

event_commands[0xBF] = event_commands[0x01]
event_commands[0xBF].command = 0xBF
event_commands[0xBF].desc += 'Alias of 0x01.'

# Dec box = decision box?
event_commands[0xC0] = \
    EventCommand(0xC0, 2, [1, 1],
                 ['ss: String Displayed',
                  'll: 03 - last line, 0C - first line.'],
                 'Dec Box Auto',
                 'Decision box.  Auto top/bottom.  Stores 00 to 7E0130.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xC1] = \
    EventCommand(0xC1, 1, [1],
                 ['ss: String Displayed'],
                 'Textbox Top',
                 'Textbox displayed at top of screen.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xC2] = \
    EventCommand(0xC2, 1, [1],
                 ['ss: String Displayed'],
                 'Textbox Bottom',
                 'Textbox displayed at bottom of screen.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xC3] = \
    EventCommand(0xC3, 2, [1, 1],
                 ['ss: String Displayed',
                  'll: 03 - last line, 0C - first line.'],
                 'Dec Box Auto',
                 'Decision box at top.  Stores 01 to 7E0130. Overlaps 0xC0',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xC4] = \
    EventCommand(0xC4, 2, [1, 1],
                 ['ss: String Displayed',
                  'll: 03 - last line, 0C - first line.'],
                 'Dec Box Bottom',
                 'Decision box at bottom.  Stores 01 to 7E0130. Overlaps 0xC0',
                 EventCommandType.TEXT,
                 EventCommandSubtype.TEXTBOX)

event_commands[0xC5] = event_commands[0x01]
event_commands[0xC5].command = 0xC5
event_commands[0xC5].desc += 'Alias of 0x01.'

event_commands[0xC6] = event_commands[0x01]
event_commands[0xC6].command = 0xC6
event_commands[0xC6].desc += 'Alias of 0x01.'

event_commands[0xC7] = \
    EventCommand(0xC7, 1, [1],
                 ['oo: Offset (*2, +7F0200) to load item from'],
                 'Add Item',
                 'Add item stored in local memory to inventory.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.ITEM_FROM_MEM)

event_commands[0xC8] = \
    EventCommand(0xC8, 1, [1],
                 ['dd: Dialog to display'],
                 'Special Dialog',
                 'Special Dialog.',
                 EventCommandType.TEXT,
                 EventCommandSubtype.SPECIAL_DIALOG)

event_commands[0xC9] = \
    EventCommand(0xC9, 2, [1, 1],
                 ['ii: Item to check for',
                  'jj: Bytes to jump if item not present'],
                 'Check Inventory',
                 'Jump if item not present in inventory.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.CHECK_ITEM)

event_commands[0xCA] = \
    EventCommand(0xCA, 1, [1],
                 ['ii: Item to add'],
                 'Add Item',
                 'Add item to inventory.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.ITEM)

event_commands[0xCB] = \
    EventCommand(0xCB, 1, [1],
                 ['ii: Item to remove'],
                 'Remove Item',
                 'Remove item from inventory.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.ITEM)

event_commands[0xCC] = \
    EventCommand(0xCC, 2, [2, 1],
                 ['gggg: Gold to check for',
                  'jj: Bytes to jump if not enough gold.'],
                 'Check Gold',
                 'Jump if the player does not have enough gold.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.CHECK_GOLD)

event_commands[0xCD] = \
    EventCommand(0xCD, 1, [2],
                 ['gggg: Gold to add'],
                 'Add Gold',
                 'Add Gold.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.ADD_GOLD)

event_commands[0xCE] = \
    EventCommand(0xCE, 1, [2],
                 ['gggg: Gold to remove.'],
                 'Remove Gold',
                 'Remove Gold.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.ADD_GOLD)

event_commands[0xCF] = \
    EventCommand(0xCF, 2, [1, 1],
                 ['cc: PC to check for',
                  'jj: Bytes to jump if PC not recruited'],
                 'Check Recruited',
                 'Check if a PC is recruited.',
                 EventCommandType.CHECK_PARTY,
                 EventCommandSubtype.CHECK_PARTY)

event_commands[0xD0] = \
    EventCommand(0xD0, 1, [1],
                 ['cc: PC to add'],
                 'Add Reserve',
                 'Add PC to the reserve party.',
                 EventCommandType.PARTY_MANAGEMENT,
                 EventCommandSubtype.PARTY_MANIP)

event_commands[0xD1] = \
    EventCommand(0xD1, 1, [1],
                 ['cc: PC to remove'],
                 'Remove PC',
                 'Remove PC (from party? recruited?)',
                 EventCommandType.PARTY_MANAGEMENT,
                 EventCommandSubtype.PARTY_MANIP)

event_commands[0xD2] = \
    EventCommand(0xD2, 2, [1, 1],
                 ['cc: PC to check for',
                  'jj: Bytes to jump if PC not active'],
                 'Check Active PC',
                 'Jump if PC not active.  May check and load?',
                 EventCommandType.CHECK_PARTY,
                 EventCommandSubtype.CHECK_PARTY)

event_commands[0xD3] = \
    EventCommand(0xD3, 1, [1],
                 ['cc: PC to add'],
                 'Add PC to Party',
                 'Add PC to Party.',
                 EventCommandType.PARTY_MANAGEMENT,
                 EventCommandSubtype.PARTY_MANIP)

event_commands[0xD4] = \
    EventCommand(0xD4, 1, [1],
                 ['cc: PC to reserve'],
                 'Move to Reserve',
                 'Move PC to reserve party.',
                 EventCommandType.PARTY_MANAGEMENT,
                 EventCommandSubtype.PARTY_MANIP)

event_commands[0xD5] = \
    EventCommand(0xD5, 2, [1, 1],
                 ['cc: PC to equip',
                  'ii: Item to equip'],
                 'Equip Item',
                 'Equip PC with an item.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.EQUIP)

event_commands[0xD6] = \
    EventCommand(0xD6, 1, [1],
                 ['cc: PC to remove'],
                 'Remove Active PC',
                 'Remove PC from active party.',
                 EventCommandType.PARTY_MANAGEMENT,
                 EventCommandSubtype.PARTY_MANIP)

event_commands[0xD7] = \
    EventCommand(0xD7, 2, [1, 1],
                 ['ii: Item to check quantity of',
                  'oo: Offset to store quantity (*2, +7F0200)'],
                 'Get Item Quantity',
                 'Get quantity of item in inventory.',
                 EventCommandType.INVENTORY,
                 EventCommandSubtype.EQUIP)

event_commands[0xD8] = \
    EventCommand(0xD8, 2, [1, 1],
                 ['ffff: Various flags for battle'],
                 'Battle',
                 'Battle.',
                 EventCommandType.BATTLE,
                 EventCommandSubtype.BATTLE)

event_commands[0xD9] = \
    EventCommand(0xD9, 6, [1, 1, 1, 1, 1, 1],
                 ['uu: PC1 x-coord',
                  'vv: PC1 y-coord',
                  'ww: PC2 x-coord',
                  'xx: PC2 y-coord',
                  'yy: PC3 x-coord',
                  'zz: PC3 y-coord'],
                 'Move Party',
                 'Move party to specified coordinates.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.MOVE_PARTY)

event_commands[0xDA] = \
    EventCommand(0xDA, 0, [],
                 [],
                 'Party Follow',
                 'Makes PC2 and PC3 follow PC1.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.PARTY_FOLLOW)

event_commands[0xDB] = event_commands[0x01]
event_commands[0xDB].command = 0xDB
event_commands[0xDB].desc += 'Alias of 0x01.'

event_commands[0xDC] = \
    EventCommand(0xDC, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xDD] = \
    EventCommand(0xDD, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xDE] = \
    EventCommand(0xDE, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location. Overlaps 0xDD.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xDF] = \
    EventCommand(0xDF, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location. Overlaps 0xE1.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xE0] = \
    EventCommand(0xE0, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xE1] = \
    EventCommand(0xE1, 3, [2, 1, 1],
                 ['llll: 01FF - location to change to, ' +
                  '0600 - facing, 1800 - ???, 8000 - unused',
                  'xx: X-coord',
                  'yy: Y-coord'],
                 'Change Location',
                 'Instantly moves party to another location. Waits vsync.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION)

event_commands[0xE2] = \
    EventCommand(0xE2, 4, [1, 1, 1, 1],
                 ['aa: Offset (*2, +7F0200) to load from',
                  'bb: Offset (*2, +7F0200) to load from',
                  'cc: Offset (*2, +7F0200) to load from',
                  'dd: Offset (*2, +7F0200) to load from'],
                 'Change Location',
                 'Instantly moves party to another location.  ' +
                 'Uses local memory to get paramters.  See e.g. E1.',
                 EventCommandType.CHANGE_LOCATION,
                 EventCommandSubtype.CHANGE_LOCATION_FROM_MEM)

event_commands[0xE3] = \
    EventCommand(0xE3, 1, [1],
                 ['tt: Toggle value.  On - Can explore, Off- cannot.'],
                 'Explore Mode',
                 'Set whether the party can freely move.',
                 EventCommandType.SPRITE_MOVEMENT,
                 EventCommandSubtype.EXPLORE_MODE)

event_commands[0xE4] = \
    EventCommand(0xE4, 7, [1, 1, 1, 1, 1, 1, 1],
                 ['ll: X-coord of top left corner of source',
                  'tt: Y-coord of top left corner of source',
                  'rr: X-coord of bottom right corner of source',
                  'bb: Y-coord of bottom right corner of soucre',
                  'xx: X-coord of destination',
                  'yy: Y-coord of destination',
                  'ff: Bitfield (see long notes in db)'],
                 'Copy Tiles',
                 'Copies tiles (from data onto map?)',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.COPY_TILES)

event_commands[0xE5] = \
    EventCommand(0xE5, 7, [1, 1, 1, 1, 1, 1, 1],
                 ['ll: X-coord of top left corner of source',
                  'tt: Y-coord of top left corner of source',
                  'rr: X-coord of bottom right corner of source',
                  'bb: Y-coord of bottom right corner of soucre',
                  'xx: X-coord of destination',
                  'yy: Y-coord of destination',
                  'ff: Bitfield (see long notes in db)'],
                 'Copy Tiles',
                 'Copies tiles (from data onto map?)',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.COPY_TILES)

event_commands[0xE6] = \
    EventCommand(0xE6, 3, [2, 1, 1],
                 ['????: Unknown',
                  'll: Layers to scroll bitfield',
                  '??: Unknown'],
                 'Scroll Layers',
                 'Scroll Layers',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.SCROLL_LAYERS)

event_commands[0xE7] = \
    EventCommand(0xE7, 2, [1, 1],
                 ['xx: X-coordinate',
                  'yy: Y-coordinate'],
                 'Scroll Screen',
                 'Scroll Screen',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.SCROLL_SCREEN)

event_commands[0xE8] = \
    EventCommand(0xE8, 1, [1],
                 ['ss: Sound Effect'],
                 'Play Sound',
                 'Plays a sound.',
                 EventCommandType.SOUND,
                 EventCommandSubtype.SOUND)

event_commands[0xE9] = event_commands[0x01]
event_commands[0xE9].command = 0xE9
event_commands[0xE9].desc += 'Alias of 0x01.'

event_commands[0xEA] = \
    EventCommand(0xEA, 1, [1],
                 ['ss: Song'],
                 'Play Song',
                 'Plays a song.',
                 EventCommandType.SOUND,
                 EventCommandSubtype.SOUND)

event_commands[0xEB] = \
    EventCommand(0xEB, 2, [1, 1],
                 ['ss: Speed of change',
                  'vv: Volume (0xFF=normal)'],
                 'Change Volume',
                 'Change Volume.',
                 EventCommandType.SOUND,
                 EventCommandSubtype.SOUND)

event_commands[0xEC] = \
    EventCommand(0xEC, 3, [1, 1, 1],
                 ['cc: Command',
                  '??: Unknown',
                  '??: Unknown'],
                 'All Purpose Sound',
                 'All Purpose Sound Command.',
                 EventCommandType.SOUND,
                 EventCommandSubtype.SOUND)

event_commands[0xED] = \
    EventCommand(0xED, 0, [],
                 [],
                 'Wait for Silence',
                 'Wait for Silence',
                 EventCommandType.SOUND,
                 EventCommandSubtype.WAIT_FOR_SILENCE)

event_commands[0xEE] = \
    EventCommand(0xEE, 0, [],
                 [],
                 'Wait for Song End',
                 'Wait for Song End',
                 EventCommandType.SOUND,
                 EventCommandSubtype.WAIT_FOR_SILENCE)

event_commands[0xEF] = event_commands[0x01]
event_commands[0xEF].command = 0xEF
event_commands[0xEF].desc += 'Alias of 0x01.'

event_commands[0xF0] = \
    EventCommand(0xF0, 1, [1],
                 ['bb: Amount to darken'],
                 'Darken Screen',
                 'Darken Screen',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.DARKEN)

# Variable length
event_commands[0xF1] = \
    EventCommand(0xF1, 2, [1, 1],
                 ['cc: 0xE0 - 3 bit BGR color, 0x1F - Intensity',
                  '(dd): 0x80 add/sub mode only if cc != 0'],
                 'Color Addition',
                 'Color Addition',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.COLOR_ADD)

event_commands[0xF2] = \
    EventCommand(0xF2, 0, [],
                 [],
                 'Fade Out',
                 'Fade Out',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.FADE_OUT)

event_commands[0xF3] = \
    EventCommand(0xF3, 0, [],
                 [],
                 'Wait for Brighten End',
                 'Wait for brighten end.',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.WAIT_FOR_ADD)

event_commands[0xF4] = \
    EventCommand(0xF4, 1, [1],
                 ['rr: Shake Screen, 00 = off'],
                 'Shake Screen',
                 'Shake screen.',
                 EventCommandType.SCENE_MANIP,
                 EventCommandSubtype.SHAKE_SCREEN)

event_commands[0xF5] = event_commands[0x01]
event_commands[0xF5].command = 0xF5
event_commands[0xF5].desc += 'Alias of 0x01.'

event_commands[0xF6] = event_commands[0x01]
event_commands[0xF6].command = 0xF6
event_commands[0xF6].desc += 'Alias of 0x01.'

event_commands[0xF7] = event_commands[0x01]
event_commands[0xF7].command = 0xF7
event_commands[0xF7].desc += 'Alias of 0x01.'

event_commands[0xF8] = \
    EventCommand(0xF8, 0, [],
                 [],
                 'Restore hp/mp.',
                 'Restore hp/mp.',
                 EventCommandType.HP_MP,
                 EventCommandSubtype.RESTORE_HPMP)

event_commands[0xF9] = \
    EventCommand(0xF9, 0, [],
                 [],
                 'Restore hp.',
                 'Restore hp.',
                 EventCommandType.HP_MP,
                 EventCommandSubtype.RESTORE_HPMP)

event_commands[0xFA] = \
    EventCommand(0xFA, 0, [],
                 [],
                 'Restore mp.',
                 'Restore mp.',
                 EventCommandType.HP_MP,
                 EventCommandSubtype.RESTORE_HPMP)

event_commands[0xFB] = event_commands[0x01]
event_commands[0xFB].command = 0xFB
event_commands[0xFB].desc += 'Alias of 0x01.'

event_commands[0xFC] = event_commands[0x01]
event_commands[0xFC].command = 0xFC
event_commands[0xFC].desc += 'Alias of 0x01.'

event_commands[0xFD] = event_commands[0x01]
event_commands[0xFD].command = 0xFD
event_commands[0xFD].desc += 'Alias of 0x01.'

event_commands[0xFE] = \
    EventCommand(0xFE, 17, [1 for i in range(17)],
                 ['Unknown' for i in range(17)],
                 'Unknown Geometry',
                 'Something relating to on screen geometry',
                 EventCommandType.MODE7,
                 EventCommandSubtype.DRAW_GEOMETRY)

event_commands[0xFF] = \
    EventCommand(0xFF, 1, [1],
                 ['ss: Scene to play'],
                 'Mode 7 Scene',
                 'Mode 7 Scene.',
                 EventCommandType.MODE7,
                 EventCommandSubtype.MODE7)



def get_command(buf: bytes, offset: int = 0,
                platform: Platform = Platform.SNES) -> EventCommand:

    command_id = buf[offset]
    command = event_commands[command_id].copy()

    # Apply PC-specific argument-length overrides before mode-based fixups.
    if platform == Platform.PC and command_id in _PC_ARG_LENS_OVERRIDES:
        command.arg_lens = _PC_ARG_LENS_OVERRIDES[command_id][:]
        command.num_args = len(command.arg_lens)

    if command_id == 0x2E:
        mode = buf[offset+1] >> 4
        if mode in [4, 5]:
            command.arg_lens = [1, 1, 1, 1, 1]
        elif mode == 8:
            if platform == Platform.PC:
                # PC: cmd byte + bits byte + palette-index byte = 3 args
                command.arg_lens = [1, 1, 1]
            else:
                copy_len = get_value_from_bytes(buf[offset+3:offset+4]) - 2
                command.arg_lens = [1, 1, 2, copy_len]
        else:
            print(f"{command_id:02X}: Error, Unknown Mode")
    elif command_id == 0x4E:
        # Data to copy follows command.  Shove data in last arg.
        data_len = get_value_from_bytes(buf[offset+4:offset+6]) - 2
        command.arg_lens = [2, 1, 2, data_len]
    elif command_id == 0x88:
        mode = buf[offset+1] >> 4
        if mode == 0:
            command.arg_lens = [1]
        elif mode in [2, 3]:
            command.arg_lens = [1, 1, 1]
        elif mode in [4, 5]:
            command.arg_lens = [1, 1, 1, 1]
        elif mode == 8:
            if platform == Platform.PC:
                # PC: cmd byte + palette-index byte = 2 args
                command.arg_lens = [1, 1]
            else:
                # SNES: variable-length copy; length encoded in third byte
                copy_len = buf[offset+2] - 2
                command.arg_lens = [1, 1, 1, copy_len]
        else:
            print(f"{command_id:02X}: Error, Unknown Mode")
    elif command_id == 0xF1:
        color = buf[offset+1]
        if color == 0:
            command.arg_lens = [1]
        else:
            command.arg_lens = [1, 1]
    elif command_id == 0xFF:  # Mode7 scenes can be weird
        scene = buf[offset+1]
        if scene == 0x90:
            command.arg_lens = [1, 1, 1, 1]
        if scene == 0x97:
            command.arg_lens = [1, 1, 1]

    # Now we can use arg_lens to extract the args
    pos = offset + 1
    command.args = []

    if command.command == 0x4E:
        for i in command.arg_lens[0:-1]:
            command.args.append(get_value_from_bytes(buf[pos:pos+i]))
            pos += i

        command.args.append(
            bytearray(buf[pos:pos+command.arg_lens[-1]])
        )
        pos += command.arg_lens[-1]
    else:
        for i in command.arg_lens:
            command.args.append(get_value_from_bytes(buf[pos:pos+i]))
            pos += i

    return command
