"""Tests for the event diff engine."""
import pytest

from jetsoftime.ctevent import Event
from jetsoftime.eventcommand import EventCommand, Platform
from jetsoftime.byteops import to_little_endian
from editorui.eventdiff import (
    compute_location_diff,
    compute_location_identical,
    DiffStatus,
    CopyEligibility,
    get_copy_eligibility,
    _command_signature,
    PC_ONLY_OPCODES,
    CROSS_PLATFORM_INCOMPATIBLE_OPCODES,
)


def _build_event(
    num_objects: int,
    functions: dict[tuple[int, int], list[EventCommand]],
    platform: Platform = Platform.SNES,
) -> Event:
    """Build a minimal Event from a dict of (obj_id, func_id) -> [commands].

    Each object has 16 function slots (pointers). Functions not in the dict
    get a pointer to the same location as the next defined function (or end
    of bytecode), which makes them appear empty.
    """
    # First, serialize all command bytecodes per (obj, func)
    func_bytes: dict[tuple[int, int], bytearray] = {}
    for key, cmds in functions.items():
        data = bytearray()
        for cmd in cmds:
            data.extend(cmd.to_bytearray())
        func_bytes[key] = data

    # Pointer table size
    ptr_table_size = num_objects * 32  # 16 pointers * 2 bytes each per object

    # Lay out bytecode sequentially after the pointer table
    bytecode = bytearray()
    # Track the offset where each (obj, func) bytecode starts
    func_offsets: dict[tuple[int, int], int] = {}

    for obj_id in range(num_objects):
        for func_id in range(16):
            key = (obj_id, func_id)
            if key in func_bytes:
                func_offsets[key] = ptr_table_size + len(bytecode)
                bytecode.extend(func_bytes[key])

    # End offset (for empty function pointers)
    end_offset = ptr_table_size + len(bytecode)

    # Build pointer table
    ptr_table = bytearray(ptr_table_size)
    for obj_id in range(num_objects):
        # Find the next defined function offset for empty slots
        for func_id in range(16):
            key = (obj_id, func_id)
            if key in func_offsets:
                offset = func_offsets[key]
            else:
                # Point to the next defined function or end
                offset = end_offset
                for fid in range(func_id, 16):
                    if (obj_id, fid) in func_offsets:
                        offset = func_offsets[(obj_id, fid)]
                        break
            ptr_pos = obj_id * 32 + func_id * 2
            ptr_table[ptr_pos:ptr_pos + 2] = to_little_endian(offset, 2)

    event = Event()
    event.num_objects = num_objects
    event.data = ptr_table + bytecode
    event.platform = platform
    event.strings = []
    return event


class TestCommandSignature:
    def test_same_commands_same_signature(self):
        cmd1 = EventCommand.script_speed(5)
        cmd2 = EventCommand.script_speed(5)
        assert _command_signature(cmd1) == _command_signature(cmd2)

    def test_different_args_different_signature(self):
        cmd1 = EventCommand.script_speed(5)
        cmd2 = EventCommand.script_speed(10)
        assert _command_signature(cmd1) != _command_signature(cmd2)

    def test_different_opcodes_different_signature(self):
        cmd1 = EventCommand.return_cmd()
        cmd2 = EventCommand.break_cmd()
        assert _command_signature(cmd1) != _command_signature(cmd2)


class TestIdenticalScripts:
    def test_single_function_identical(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        assert diff.is_identical
        assert diff.left_num_objects == 1
        assert diff.right_num_objects == 1
        assert len(diff.functions) == 1
        assert all(line.status == DiffStatus.EQUAL for line in diff.functions[0].lines)

    def test_multiple_objects_identical(self):
        cmds0 = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        cmds1 = [EventCommand.set_speed(3), EventCommand.return_cmd()]
        left = _build_event(2, {(0, 0): cmds0, (1, 0): cmds1})
        right = _build_event(2, {(0, 0): cmds0, (1, 0): cmds1})

        diff = compute_location_diff(left, right, 0)
        assert diff.is_identical

    def test_empty_scripts_identical(self):
        left = _build_event(1, {(0, 0): [EventCommand.return_cmd()]})
        right = _build_event(1, {(0, 0): [EventCommand.return_cmd()]})

        diff = compute_location_diff(left, right, 0)
        assert diff.is_identical


class TestAddedRemovedCommands:
    def test_command_added_on_right(self):
        left_cmds = [EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        assert not diff.is_identical
        lines = diff.functions[0].lines

        # Should have at least one RIGHT_ONLY line for the added command
        right_only = [l for l in lines if l.status == DiffStatus.RIGHT_ONLY]
        assert len(right_only) >= 1

    def test_command_removed_on_right(self):
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        assert not diff.is_identical
        lines = diff.functions[0].lines

        left_only = [l for l in lines if l.status == DiffStatus.LEFT_ONLY]
        assert len(left_only) >= 1

    def test_extra_object_on_left(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(2, {(0, 0): cmds, (1, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        assert diff.left_num_objects == 2
        assert diff.right_num_objects == 1
        assert not diff.is_identical

        # Object 1's functions should be LEFT_ONLY
        obj1_funcs = [f for f in diff.functions if f.object_index == 1]
        assert len(obj1_funcs) > 0
        for func_diff in obj1_funcs:
            assert all(l.status == DiffStatus.LEFT_ONLY for l in func_diff.lines)

    def test_extra_object_on_right(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(2, {(0, 0): cmds, (1, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        assert diff.left_num_objects == 1
        assert diff.right_num_objects == 2

        obj1_funcs = [f for f in diff.functions if f.object_index == 1]
        assert len(obj1_funcs) > 0
        for func_diff in obj1_funcs:
            assert all(l.status == DiffStatus.RIGHT_ONLY for l in func_diff.lines)


class TestModifiedCommands:
    def test_same_opcode_different_args(self):
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(10), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        assert not diff.is_identical
        lines = diff.functions[0].lines

        modified = [l for l in lines if l.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        assert modified[0].left.command == 0x87  # script_speed opcode
        assert modified[0].left.args == [5]
        assert modified[0].right.args == [10]

    def test_different_opcodes_in_same_position(self):
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.set_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        assert not diff.is_identical
        lines = diff.functions[0].lines

        # The differing command should show up as MODIFIED or LEFT_ONLY/RIGHT_ONLY
        non_equal = [l for l in lines if l.status != DiffStatus.EQUAL]
        assert len(non_equal) >= 1


class TestMultipleFunctions:
    def test_different_functions_diffed_independently(self):
        """Startup identical, Activate differs."""
        startup = [EventCommand.return_cmd()]
        activate_left = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        activate_right = [EventCommand.script_speed(2), EventCommand.return_cmd()]

        left = _build_event(1, {(0, 0): startup, (0, 1): activate_left})
        right = _build_event(1, {(0, 0): startup, (0, 1): activate_right})

        diff = compute_location_diff(left, right, 0)

        startup_diffs = [f for f in diff.functions if f.function_name == "Startup / Idle"]
        activate_diffs = [f for f in diff.functions if f.function_name == "Activate"]

        assert len(startup_diffs) == 1
        assert startup_diffs[0].is_identical

        assert len(activate_diffs) == 1
        assert not activate_diffs[0].is_identical


class TestDiffLineAddresses:
    def test_addresses_preserved(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        lines = diff.functions[0].lines

        for line in lines:
            assert line.left_address is not None
            assert line.right_address is not None

    def test_left_only_has_no_right_address(self):
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        lines = diff.functions[0].lines

        left_only = [l for l in lines if l.status == DiffStatus.LEFT_ONLY]
        for line in left_only:
            assert line.left is not None
            assert line.right is None


class TestFunctionDiffProperties:
    def test_is_identical_true_when_all_equal(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        assert diff.functions[0].is_identical

    def test_is_identical_false_when_any_differ(self):
        left = _build_event(1, {(0, 0): [EventCommand.script_speed(1), EventCommand.return_cmd()]})
        right = _build_event(1, {(0, 0): [EventCommand.script_speed(2), EventCommand.return_cmd()]})

        diff = compute_location_diff(left, right, 0)
        assert not diff.functions[0].is_identical


class TestLocationDiffProperties:
    def test_location_id_stored(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 42)
        assert diff.location_id == 42

    def test_num_objects_stored(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(3, {(0, 0): cmds, (1, 0): cmds, (2, 0): cmds})
        right = _build_event(2, {(0, 0): cmds, (1, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        assert diff.left_num_objects == 3
        assert diff.right_num_objects == 2


# ---------------------------------------------------------------------------
# Step 2: Copy eligibility
# ---------------------------------------------------------------------------

def _make_cmd(opcode: int, args: list[int] | None = None) -> EventCommand:
    """Create a minimal EventCommand with the given opcode and args."""
    cmd = EventCommand(opcode, len(args) if args else 0, [1] * (len(args) if args else 0),
                       [], "test", "test")
    cmd.args = args if args else []
    return cmd


class TestGetCopyEligibility:
    def test_same_platform_always_allowed(self):
        cmd = _make_cmd(0xBB, [0x01])  # textbox — in overrides
        assert get_copy_eligibility(cmd, Platform.SNES, Platform.SNES, False) == CopyEligibility.ALLOWED
        assert get_copy_eligibility(cmd, Platform.PC, Platform.PC, False) == CopyEligibility.ALLOWED

    def test_read_only_target_blocked(self):
        cmd = EventCommand.return_cmd()
        assert get_copy_eligibility(cmd, Platform.SNES, Platform.SNES, True) == CopyEligibility.BLOCKED_READ_ONLY

    def test_read_only_takes_precedence(self):
        cmd = _make_cmd(0x3A, [1, 2])  # PC-only
        assert get_copy_eligibility(cmd, Platform.PC, Platform.SNES, True) == CopyEligibility.BLOCKED_READ_ONLY

    def test_pc_only_to_snes_blocked(self):
        for opcode in PC_ONLY_OPCODES:
            cmd = _make_cmd(opcode, [1, 1])
            result = get_copy_eligibility(cmd, Platform.PC, Platform.SNES, False)
            assert result == CopyEligibility.BLOCKED_PC_ONLY, f"opcode 0x{opcode:02X}"

    def test_pc_only_to_pc_allowed(self):
        for opcode in PC_ONLY_OPCODES:
            cmd = _make_cmd(opcode, [1, 1])
            result = get_copy_eligibility(cmd, Platform.PC, Platform.PC, False)
            assert result == CopyEligibility.ALLOWED

    def test_cross_platform_incompatible_blocked(self):
        for opcode in CROSS_PLATFORM_INCOMPATIBLE_OPCODES:
            cmd = _make_cmd(opcode, [1])
            result = get_copy_eligibility(cmd, Platform.SNES, Platform.PC, False)
            assert result == CopyEligibility.BLOCKED_CROSS_PLATFORM, f"opcode 0x{opcode:02X}"
            result = get_copy_eligibility(cmd, Platform.PC, Platform.SNES, False)
            assert result == CopyEligibility.BLOCKED_CROSS_PLATFORM, f"opcode 0x{opcode:02X}"

    def test_platform_neutral_cross_platform_allowed(self):
        # Return (0x00) has no PC override — should be allowed cross-platform
        cmd = EventCommand.return_cmd()
        assert get_copy_eligibility(cmd, Platform.SNES, Platform.PC, False) == CopyEligibility.ALLOWED
        assert get_copy_eligibility(cmd, Platform.PC, Platform.SNES, False) == CopyEligibility.ALLOWED

    def test_script_speed_cross_platform_allowed(self):
        # 0x87 is not in overrides — same encoding on both platforms
        cmd = EventCommand.script_speed(5)
        assert get_copy_eligibility(cmd, Platform.SNES, Platform.PC, False) == CopyEligibility.ALLOWED


class TestCopyEligibilityOnDiffLines:
    def test_same_platform_all_allowed(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0)
        for func in diff.functions:
            for line in func.lines:
                assert line.copy_left_to_right == CopyEligibility.ALLOWED
                assert line.copy_right_to_left == CopyEligibility.ALLOWED

    def test_read_only_right_blocks_left_to_right(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0, right_read_only=True)
        for func in diff.functions:
            for line in func.lines:
                assert line.copy_left_to_right == CopyEligibility.BLOCKED_READ_ONLY
                # Right to left should still be allowed
                assert line.copy_right_to_left == CopyEligibility.ALLOWED

    def test_read_only_left_blocks_right_to_left(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})

        diff = compute_location_diff(left, right, 0, left_read_only=True)
        for func in diff.functions:
            for line in func.lines:
                assert line.copy_left_to_right == CopyEligibility.ALLOWED
                assert line.copy_right_to_left == CopyEligibility.BLOCKED_READ_ONLY

    def test_cross_platform_textbox_blocked(self):
        """Textbox opcode 0xBB has different arg encoding — blocked cross-platform."""
        # Build a command with opcode 0xBB manually
        textbox_cmd = _make_cmd(0xBB, [0x01])
        neutral_cmd = EventCommand.return_cmd()

        left = _build_event(1, {(0, 0): [textbox_cmd, neutral_cmd]}, platform=Platform.SNES)
        right = _build_event(1, {(0, 0): [textbox_cmd, neutral_cmd]}, platform=Platform.PC)

        diff = compute_location_diff(left, right, 0)
        lines = diff.functions[0].lines

        # Find the textbox line
        textbox_lines = [l for l in lines if l.left is not None and l.left.command == 0xBB]
        assert len(textbox_lines) == 1
        assert textbox_lines[0].copy_left_to_right == CopyEligibility.BLOCKED_CROSS_PLATFORM
        assert textbox_lines[0].copy_right_to_left == CopyEligibility.BLOCKED_CROSS_PLATFORM

        # Return command should be allowed
        return_lines = [l for l in lines if l.left is not None and l.left.command == 0x00]
        assert len(return_lines) == 1
        assert return_lines[0].copy_left_to_right == CopyEligibility.ALLOWED
        assert return_lines[0].copy_right_to_left == CopyEligibility.ALLOWED


class TestOpcodeSetIntegrity:
    def test_pc_only_and_incompatible_are_disjoint(self):
        assert PC_ONLY_OPCODES.isdisjoint(CROSS_PLATFORM_INCOMPATIBLE_OPCODES)

    def test_pc_only_are_in_overrides(self):
        from jetsoftime.eventcommand import _PC_ARG_LENS_OVERRIDES
        for opcode in PC_ONLY_OPCODES:
            assert opcode in _PC_ARG_LENS_OVERRIDES, f"0x{opcode:02X} not in overrides"

    def test_incompatible_are_in_overrides(self):
        from jetsoftime.eventcommand import _PC_ARG_LENS_OVERRIDES
        for opcode in CROSS_PLATFORM_INCOMPATIBLE_OPCODES:
            assert opcode in _PC_ARG_LENS_OVERRIDES, f"0x{opcode:02X} not in overrides"

    def test_union_covers_all_overrides(self):
        from jetsoftime.eventcommand import _PC_ARG_LENS_OVERRIDES
        covered = PC_ONLY_OPCODES | CROSS_PLATFORM_INCOMPATIBLE_OPCODES
        for opcode in _PC_ARG_LENS_OVERRIDES:
            assert opcode in covered, f"0x{opcode:02X} not classified"


# ---------------------------------------------------------------------------
# Step 5: Copy operations (Event-level)
# ---------------------------------------------------------------------------

class TestCopyModifiedCommand:
    def test_replace_modified_command_in_target(self):
        """Copying a MODIFIED line replaces the target command bytes."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(10), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        modified = [l for l in diff.functions[0].lines if l.status == DiffStatus.MODIFIED]
        assert len(modified) == 1
        dl = modified[0]

        # Perform the replacement on the right event
        right.delete_commands(dl.right_address, 1)
        right.insert_commands(dl.left.to_bytearray(), dl.right_address)

        # Re-diff: should now be identical
        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical

    def test_replace_preserves_subsequent_commands(self):
        """After replacing a command, subsequent commands should still be parseable."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.set_speed(3), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(10), EventCommand.set_speed(3), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        modified = [l for l in diff.functions[0].lines if l.status == DiffStatus.MODIFIED]
        dl = modified[0]

        right.delete_commands(dl.right_address, 1)
        right.insert_commands(dl.left.to_bytearray(), dl.right_address)

        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical


class TestCopyInsertCommand:
    def test_insert_left_only_into_right(self):
        """Copying a LEFT_ONLY line inserts the command into the right event."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.set_speed(3), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        left_only = [l for l in diff.functions[0].lines if l.status == DiffStatus.LEFT_ONLY]
        assert len(left_only) == 1
        dl = left_only[0]

        # Find insertion point: look for preceding line with right_address
        lines = diff.functions[0].lines
        line_idx = lines.index(dl)
        insert_addr = None
        for i in range(line_idx - 1, -1, -1):
            prev = lines[i]
            if prev.right_address is not None and prev.right is not None:
                insert_addr = prev.right_address + len(prev.right)
                break
        if insert_addr is None:
            insert_addr = right.get_function_start(0, 0)

        right.insert_commands(dl.left.to_bytearray(), insert_addr)

        # Re-diff: should now be identical
        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical

    def test_insert_right_only_into_left(self):
        """Copying a RIGHT_ONLY line inserts the command into the left event."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(5), EventCommand.set_speed(3), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        right_only = [l for l in diff.functions[0].lines if l.status == DiffStatus.RIGHT_ONLY]
        assert len(right_only) == 1
        dl = right_only[0]

        # Find insertion point in left event (use identity, not equality)
        lines = diff.functions[0].lines
        line_idx = next(i for i, l in enumerate(lines) if l is dl)
        insert_addr = None
        for i in range(line_idx - 1, -1, -1):
            prev = lines[i]
            if prev.left_address is not None and prev.left is not None:
                insert_addr = prev.left_address + len(prev.left)
                break
        if insert_addr is None:
            insert_addr = left.get_function_start(0, 0)

        left.insert_commands(dl.right.to_bytearray(), insert_addr)

        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical


class TestCopyDeleteCommand:
    def test_delete_left_only_from_left(self):
        """Copying absence from right removes the LEFT_ONLY command from left."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.set_speed(3), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        left_only = [l for l in diff.functions[0].lines if l.status == DiffStatus.LEFT_ONLY]
        assert len(left_only) == 1
        dl = left_only[0]

        # Delete from left
        left.delete_commands(dl.left_address, 1)

        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical

    def test_delete_right_only_from_right(self):
        """Copying absence from left removes the RIGHT_ONLY command from right."""
        left_cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        right_cmds = [EventCommand.script_speed(5), EventCommand.set_speed(3), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): left_cmds})
        right = _build_event(1, {(0, 0): right_cmds})

        diff = compute_location_diff(left, right, 0)
        right_only = [l for l in diff.functions[0].lines if l.status == DiffStatus.RIGHT_ONLY]
        assert len(right_only) == 1
        dl = right_only[0]

        right.delete_commands(dl.right_address, 1)

        diff2 = compute_location_diff(left, right, 0)
        assert diff2.is_identical


class TestCopyBlocked:
    def test_blocked_command_not_allowed(self):
        """Verify that blocked commands have correct eligibility on diff lines."""
        textbox_cmd = _make_cmd(0xBB, [0x01])
        neutral_cmd = EventCommand.return_cmd()

        left = _build_event(1, {(0, 0): [textbox_cmd, neutral_cmd]}, platform=Platform.SNES)
        right = _build_event(1, {(0, 0): [textbox_cmd, neutral_cmd]}, platform=Platform.PC)

        diff = compute_location_diff(left, right, 0)
        for func in diff.functions:
            for line in func.lines:
                if line.left is not None and line.left.command == 0xBB:
                    assert line.copy_left_to_right != CopyEligibility.ALLOWED
                    assert line.copy_right_to_left != CopyEligibility.ALLOWED


# ---------------------------------------------------------------------------
# Step 6: Batch identical check
# ---------------------------------------------------------------------------

class TestComputeLocationIdentical:
    def test_identical_scripts(self):
        cmds = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})
        assert compute_location_identical(left, right) is True

    def test_different_commands(self):
        left = _build_event(1, {(0, 0): [EventCommand.script_speed(5), EventCommand.return_cmd()]})
        right = _build_event(1, {(0, 0): [EventCommand.script_speed(10), EventCommand.return_cmd()]})
        assert compute_location_identical(left, right) is False

    def test_different_num_objects(self):
        cmds = [EventCommand.return_cmd()]
        left = _build_event(2, {(0, 0): cmds, (1, 0): cmds})
        right = _build_event(1, {(0, 0): cmds})
        assert compute_location_identical(left, right) is False

    def test_extra_command_on_one_side(self):
        left = _build_event(1, {(0, 0): [EventCommand.return_cmd()]})
        right = _build_event(1, {(0, 0): [EventCommand.script_speed(5), EventCommand.return_cmd()]})
        assert compute_location_identical(left, right) is False

    def test_multiple_functions_identical(self):
        startup = [EventCommand.return_cmd()]
        activate = [EventCommand.script_speed(1), EventCommand.return_cmd()]
        left = _build_event(1, {(0, 0): startup, (0, 1): activate})
        right = _build_event(1, {(0, 0): startup, (0, 1): activate})
        assert compute_location_identical(left, right) is True

    def test_agrees_with_full_diff(self):
        """compute_location_identical should agree with LocationDiff.is_identical."""
        cmds_a = [EventCommand.script_speed(5), EventCommand.return_cmd()]
        cmds_b = [EventCommand.script_speed(10), EventCommand.return_cmd()]

        # Identical case
        left = _build_event(1, {(0, 0): cmds_a})
        right = _build_event(1, {(0, 0): cmds_a})
        diff = compute_location_diff(left, right, 0)
        assert compute_location_identical(left, right) == diff.is_identical

        # Different case
        left2 = _build_event(1, {(0, 0): cmds_a})
        right2 = _build_event(1, {(0, 0): cmds_b})
        diff2 = compute_location_diff(left2, right2, 0)
        assert compute_location_identical(left2, right2) == diff2.is_identical
