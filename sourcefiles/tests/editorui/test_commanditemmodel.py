import unittest
from PyQt6.QtCore import QModelIndex, Qt
from editorui.commanditem import CommandItem
from editorui.commanditemmodel import CommandModel
from jetsoftime.eventcommand import EventCommand, FuncSync
from jetsoftime.ctevent import Event

class _MockBackend:
    """Minimal read/write backend for testing script.data synchronisation."""
    def __init__(self, event: Event):
        self._event = event

    def get_script(self, location_id: int) -> Event:
        return self._event

def _build_minimal_event() -> Event:
    event = Event()
    event.num_objects = 1
    # 32 bytes for pointer table. We'll start Function 0 at offset 32.
    data = bytearray(32)
    # Give all 16 slots the same starting address (32) initially
    for i in range(16):
        data[2 * i] = 32
        data[2 * i + 1] = 0
        
    # Put a Return (0x0F) command at offset 32 to complete the function.
    data.extend(bytearray([0x0F]))
    event.data = data
    return event

def _model_with_backend():
    event = _build_minimal_event()
    root = CommandItem("Root")
    backend = _MockBackend(event)
    model = CommandModel(root, backend=backend, location_id=0)
    model.change_location(0) # Triggers a full parse
    return model, event

class TestCommandModel(unittest.TestCase):
    def setUp(self):
        self.model, self.event = _model_with_backend()
        # Function 0 should be at Object 0 (row 0) -> Function 0 (row 0)
        self.obj_index = self.model.index(0, 0, QModelIndex())
        self.func_index = self.model.index(0, 0, self.obj_index)
        
    def test_basic_insertion(self):
        command = EventCommand.pause(1) # 1 byte command
        # Insert before the Return command
        success = self.model.insert_command(self.func_index, 0, command, 32)
        self.assertTrue(success)
        
        # Function 0 should now have 2 children: Pause and Return
        self.assertEqual(self.model.rowCount(self.func_index), 2)
        child0 = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(child0.command.command, command.command)
        self.assertEqual(child0.address, 32)
        
        child1 = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(child1.command.command, 0x0F) # Return
        self.assertEqual(child1.address, 33)

    def test_update_command(self):
        command = EventCommand.script_speed(1) # 2 byte command
        self.model.insert_command(self.func_index, 0, command, 32)
        
        child0 = self.model.index(0, 0, self.func_index).internalPointer()
        new_command = EventCommand.pause(1) # 1 byte command
        
        self.model.update_command(child0, new_command)
        
        child0 = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(child0.command.command, new_command.command)
        
        # The return command should have shifted backward
        child1 = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(child1.address, 33)

    def test_delete_command(self):
        command = EventCommand.pause(1)
        self.model.insert_command(self.func_index, 0, command, 32)
        
        self.assertEqual(self.model.rowCount(self.func_index), 2)
        child0_idx = self.model.index(0, 0, self.func_index)
        
        self.model.delete_command(child0_idx)
        
        # Should be back to just the return command
        self.assertEqual(self.model.rowCount(self.func_index), 1)
        child0 = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(child0.command.command, 0x0F)
        self.assertEqual(child0.address, 32)

    def test_conditional_insertion_and_deletion(self):
        if_cmd = EventCommand.if_has_item(1, 0) # 3 bytes + 1 byte return
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        
        # Re-fetch the index after tree rebuilt
        child_index = self.model.index(0, 0, self.func_index)
        if_item = child_index.internalPointer()
        
        child_cmd = EventCommand.end_cmd()
        self.model.insert_command(child_index, 0, child_cmd, 32 + len(if_cmd))
        
        # Grab updated tree
        child_index = self.model.index(0, 0, self.func_index)
        if_item = child_index.internalPointer()
        self.assertEqual(if_item.command.args[-1], 2) # Jump bypasses the 1 byte end_cmd + 1

    def test_cut_and_paste(self):
        cmd1 = EventCommand.pause(1)
        cmd2 = EventCommand.end_cmd()
        
        self.model.insert_command(self.func_index, 0, cmd1, 32)
        self.model.insert_command(self.func_index, 1, cmd2, 33)
        
        # Select cmd1
        idx0 = self.model.index(0, 0, self.func_index)
        copied = self.model.cut_items([idx0])
        self.assertEqual(len(copied), 1)
        
        # Now cmd2 should be the first child
        idx_target = self.model.index(0, 0, self.func_index)
        self.assertEqual(idx_target.internalPointer().command.command, cmd2.command)
        
        # Paste cmd1 after cmd2
        self.model.paste_items(copied, idx_target)
        
        child0 = self.model.index(0, 0, self.func_index).internalPointer()
        child1 = self.model.index(1, 0, self.func_index).internalPointer()
        
        self.assertEqual(child0.command.command, cmd2.command)
        self.assertEqual(child1.command.command, cmd1.command)

    def test_drag_drop_moves_commands(self):
        cmd1 = EventCommand.pause(1)
        cmd2 = EventCommand.end_cmd()
        
        self.model.insert_command(self.func_index, 0, cmd1, 32)
        self.model.insert_command(self.func_index, 1, cmd2, 33)
        
        # drag cmd1
        drag_idx = self.model.index(0, 0, self.func_index)
        mime = self.model.mimeData([drag_idx])
        
        # drop onto cmd2
        drop_idx = self.model.index(1, 0, self.func_index)
        success = self.model.dropMimeData(mime, Qt.DropAction.MoveAction, -1, 0, drop_idx)
        self.assertTrue(success)
        
        # they should be swapped now
        new_child0 = self.model.index(0, 0, self.func_index).internalPointer()
        new_child1 = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(new_child0.command.command, cmd2.command)
        self.assertEqual(new_child1.command.command, cmd1.command)

    # ------------------------------------------------------------------ #
    # Group A: Address correctness after size-changing mutations           #
    # ------------------------------------------------------------------ #

    def test_update_command_size_increase_shifts_addresses(self):
        small = EventCommand.pause(1)       # 1 byte
        big = EventCommand.script_speed(1)  # 2 bytes
        follower = EventCommand.end_cmd()   # 1 byte

        self.model.insert_command(self.func_index, 0, small, 32)
        self.model.insert_command(self.func_index, 1, follower, 33)

        small_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.model.update_command(small_item, big)

        follower_item = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(follower_item.address, 34)

    def test_update_command_size_decrease_shifts_addresses(self):
        big = EventCommand.script_speed(1)  # 2 bytes
        small = EventCommand.pause(1)       # 1 byte
        follower = EventCommand.end_cmd()   # 1 byte

        self.model.insert_command(self.func_index, 0, big, 32)
        self.model.insert_command(self.func_index, 1, follower, 34)

        big_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.model.update_command(big_item, small)

        follower_item = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(follower_item.address, 33)

    def test_insert_at_position_zero_shifts_existing(self):
        existing = EventCommand.end_cmd()      # 1 byte
        self.model.insert_command(self.func_index, 0, existing, 32)

        new_cmd = EventCommand.script_speed(1)  # 2 bytes
        self.model.insert_command(self.func_index, 0, new_cmd, 32)

        first = self.model.index(0, 0, self.func_index).internalPointer()
        second = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(first.command.command, new_cmd.command)
        self.assertEqual(first.address, 32)
        self.assertEqual(second.address, 34)

    # ------------------------------------------------------------------ #
    # Group B: Copy / cut / paste correctness                             #
    # ------------------------------------------------------------------ #

    def test_copy_produces_independent_command(self):
        cmd = EventCommand.script_speed(1)
        self.model.insert_command(self.func_index, 0, cmd, 32)
        index = self.model.index(0, 0, self.func_index)

        copied_items = self.model.copy_items([index])
        self.assertEqual(len(copied_items), 1)
        copied_item, _ = copied_items[0]
        original_opcode = copied_item.command.command

        original_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.model.update_command(original_item, EventCommand.end_cmd())

        self.assertEqual(copied_item.command.command, original_opcode)

    def test_copy_conditional_includes_children(self):
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        child = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child, 32 + len(if_cmd))

        if_index = self.model.index(0, 0, self.func_index)
        copied_items = self.model.copy_items([if_index])
        copied_item, _ = copied_items[0]

        self.assertEqual(copied_item.command.command, if_cmd.command)
        self.assertEqual(len(copied_item.children), 1)
        self.assertEqual(copied_item.children[0].command.command, child.command)

    def test_copy_children_are_independent_of_originals(self):
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        child = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child, 32 + len(if_cmd))

        if_index = self.model.index(0, 0, self.func_index)
        if_item = if_index.internalPointer()
        copied_items = self.model.copy_items([if_index])
        copied_item, _ = copied_items[0]

        copied_item.children[0].command.args = [0xFF]
        original_child = if_item.children[0]
        self.assertNotEqual(original_child.command.args, [0xFF])

    def test_cut_removes_source_item(self):
        cmd1 = EventCommand.end_cmd()
        cmd2 = EventCommand.pause(1)
        self.model.insert_command(self.func_index, 0, cmd1, 32)
        self.model.insert_command(self.func_index, 1, cmd2, 33)

        cut = self.model.cut_items([self.model.index(0, 0, self.func_index)])

        self.assertEqual(len(cut), 1)
        remaining = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(remaining.command.command, cmd2.command)

    def test_paste_inserts_after_target(self):
        cmd1 = EventCommand.script_speed(1)  # 2 bytes
        cmd2 = EventCommand.end_cmd()        # 1 byte
        self.model.insert_command(self.func_index, 0, cmd1, 32)
        self.model.insert_command(self.func_index, 1, cmd2, 34)

        idx0 = self.model.index(0, 0, self.func_index)
        idx1 = self.model.index(1, 0, self.func_index)

        copied = self.model.copy_items([idx0])
        self.model.paste_items(copied, idx1)

        # [cmd1@32, cmd2@34, copy_of_cmd1@35, Return@37]
        pasted = self.model.index(2, 0, self.func_index).internalPointer()
        self.assertEqual(pasted.command.command, cmd1.command)

        cmd2_item = self.model.index(1, 0, self.func_index).internalPointer()
        self.assertEqual(pasted.address, cmd2_item.address + len(cmd2_item.command))

    def test_paste_onto_conditional_inserts_as_first_child(self):
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        existing_child = EventCommand.end_cmd()
        child_addr = 32 + len(if_cmd)
        self.model.insert_command(if_index, 0, existing_child, child_addr)

        # Insert a dummy sibling of if_cmd, then copy it to paste onto the conditional
        dummy = EventCommand.pause(1)
        dummy_addr = child_addr + len(existing_child)
        self.model.insert_command(self.func_index, 1, dummy, dummy_addr)
        dummy_index = self.model.index(1, 0, self.func_index)
        copied = self.model.copy_items([dummy_index])

        if_index = self.model.index(0, 0, self.func_index)
        self.model.paste_items(copied, if_index)

        if_index = self.model.index(0, 0, self.func_index)
        self.assertEqual(self.model.rowCount(if_index), 2)
        first_child = self.model.index(0, 0, if_index).internalPointer()
        self.assertEqual(first_child.command.command, dummy.command)

    # ------------------------------------------------------------------ #
    # Group C: Ancestor conditional jump byte correctness                 #
    # ------------------------------------------------------------------ #

    def test_delete_child_from_conditional_updates_jump_byte(self):
        if_cmd = EventCommand.if_has_item(1, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        child_cmd = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child_cmd, 32 + len(if_cmd))

        if_index = self.model.index(0, 0, self.func_index)
        if_item = if_index.internalPointer()
        self.assertEqual(if_item.command.args[-1], 2)

        child_index = self.model.index(0, 0, if_index)
        self.model.delete_command(child_index)

        if_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(if_item.command.args[-1], 1)

    def test_nested_conditional_outer_jump_updated(self):
        outer_cmd = EventCommand.if_has_item(1, 0)
        inner_cmd = EventCommand.if_storyline_counter_lt(5, 0)
        leaf_cmd = EventCommand.end_cmd()

        outer_addr = 32
        inner_addr = outer_addr + len(outer_cmd)
        leaf_addr = inner_addr + len(inner_cmd)

        self.model.insert_command(self.func_index, 0, outer_cmd, outer_addr)
        outer_index = self.model.index(0, 0, self.func_index)
        self.model.insert_command(outer_index, 0, inner_cmd, inner_addr)
        outer_index = self.model.index(0, 0, self.func_index)
        inner_index = self.model.index(0, 0, outer_index)
        self.model.insert_command(inner_index, 0, leaf_cmd, leaf_addr)

        outer_index = self.model.index(0, 0, self.func_index)
        inner_index = self.model.index(0, 0, outer_index)
        outer_item = outer_index.internalPointer()
        inner_item = inner_index.internalPointer()

        self.assertEqual(inner_item.command.args[-1], 2)
        self.assertEqual(outer_item.command.args[-1], len(inner_cmd) + 2)

    # ------------------------------------------------------------------ #
    # Group D: script.data sync — tree and raw bytes must agree           #
    # ------------------------------------------------------------------ #

    def _jump_byte_in_data(self, item) -> int:
        cmd = item.command
        arg_offset = len(cmd) - cmd.arg_lens[-1]
        return self.event.data[item.address + arg_offset]

    def test_insert_syncs_script_data(self):
        if_cmd = EventCommand.if_has_item(1, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        child_cmd = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child_cmd, 32 + len(if_cmd))

        if_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(if_item.command.args[-1], 2)
        self.assertEqual(self._jump_byte_in_data(if_item), 2)

    def test_delete_syncs_script_data(self):
        if_cmd = EventCommand.if_has_item(1, 0)
        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        if_index = self.model.index(0, 0, self.func_index)

        child_cmd = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child_cmd, 32 + len(if_cmd))

        if_index = self.model.index(0, 0, self.func_index)
        child_index = self.model.index(0, 0, if_index)
        self.model.delete_command(child_index)

        if_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(if_item.command.args[-1], 1)
        self.assertEqual(self._jump_byte_in_data(if_item), 1)

    def test_drop_syncs_script_data(self):
        if_cmd = EventCommand.if_has_item(1, 0)
        to_drop = EventCommand.end_cmd()

        self.model.insert_command(self.func_index, 0, if_cmd, 32)
        self.model.insert_command(self.func_index, 1, to_drop, 32 + len(if_cmd))

        if_index = self.model.index(0, 0, self.func_index)
        drop_index = self.model.index(1, 0, self.func_index)

        mime = self.model.mimeData([drop_index])
        self.model.dropMimeData(mime, Qt.DropAction.MoveAction, -1, 0, if_index)

        if_item = self.model.index(0, 0, self.func_index).internalPointer()
        self.assertEqual(if_item.command.args[-1], len(to_drop) + 1)
        self.assertEqual(self._jump_byte_in_data(if_item), len(to_drop) + 1)