import unittest
from PyQt6.QtCore import QModelIndex, Qt
from editorui.commanditem import CommandItem
from editorui.commanditemmodel import CommandModel, print_command_tree
from jetsoftime.eventcommand import EventCommand, event_commands, FuncSync

class TestCommandModel(unittest.TestCase):
    def setUp(self):
        # Create a root item with some test commands
        self.root = CommandItem("Root")
        self.model = CommandModel(self.root)

    # Append a command and return the next address
    def append_command(self, command: EventCommand, address: int) -> tuple[int, CommandItem]:
        i = self.model.rowCount(QModelIndex())
        self.model.insert_command(QModelIndex(), i, command, address)
        inserted = self.model.index(i, 0, QModelIndex()).internalPointer()
        self.assertEqual(inserted.address, address)
        self.assertEqual(inserted.command, command)
        return (address + len(command), inserted)


    def test_basic_insertion(self):
        """Test basic command insertion functionality"""
        # Create a call PC function command
        command = EventCommand.call_pc_function(0, 1, 2, FuncSync.HALT)
        
        # Insert at root level
        success = self.model.insert_command(QModelIndex(), 0, command, 0x100)
        
        # Verify insertion
        self.assertTrue(success)
        self.assertEqual(self.model.rowCount(QModelIndex()), 1)
        
        # Verify command properties
        index = self.model.index(0, 0, QModelIndex())
        item = index.internalPointer()
        self.assertEqual(item.address, 0x100)
        self.assertEqual(item.command, command)

    def test_nested_insertion(self):
        """Test insertion of commands under conditional commands"""
        # Create an IF command (conditional)
        if_command = EventCommand.if_has_item(1, 8)  # Jump 8 bytes if item 1 not present
        
        # Insert conditional command
        self.model.insert_command(QModelIndex(), 0, if_command, 0x100)
        parent_index = self.model.index(0, 0, QModelIndex())
        
        # Insert a return command under conditional
        child_command = EventCommand.return_cmd()
        success = self.model.insert_command(parent_index, 0, child_command, 0x104)
        
        # Verify nested structure
        self.assertTrue(success)
        self.assertEqual(self.model.rowCount(parent_index), 1)
        
        # Verify addresses are correct
        child_index = self.model.index(0, 0, parent_index)
        child_item = child_index.internalPointer()
        self.assertEqual(child_item.address, 0x104)

    def test_command_deletion(self):
        """Test command deletion and address updating"""
        # Insert two commands
        cmd1 = EventCommand.script_speed(1)  # Single byte command
        cmd2 = EventCommand.set_speed(2)     # Another single byte command
        
        self.model.insert_command(QModelIndex(), 0, cmd1, 0x100)
        self.model.insert_command(QModelIndex(), 1, cmd2, 0x102)
        
        # Delete first command
        index_to_delete = self.model.index(0, 0, QModelIndex())
        success = self.model.delete_command(index_to_delete)
        
        # Verify deletion
        self.assertTrue(success)
        self.assertEqual(self.model.rowCount(QModelIndex()), 1)
        
        # Verify address of remaining command was updated
        remaining_index = self.model.index(0, 0, QModelIndex())
        remaining_item = remaining_index.internalPointer()
        self.assertEqual(remaining_item.command.command, cmd2.command)
        self.assertEqual(remaining_item.address, 0x100)  # Should have moved up

    def test_forward_jump_command_updates(self):
        """Test that jump commands are properly updated when commands are inserted/deleted/updated"""
        # Create a forward jump command (jump 8 bytes forward)
        jump_cmd = EventCommand.jump_forward(8)
        self.model.insert_command(QModelIndex(), 0, jump_cmd, 0x100)
        
        # Insert a pause command after the jump but before its target
        new_cmd = EventCommand.pause(1)  # 1 second pause
        self.model.insert_command(QModelIndex(), 1, new_cmd, 0x102)
        
        # Verify jump offset was updated
        jump_index = self.model.index(0, 0, QModelIndex())
        jump_item = jump_index.internalPointer()
        self.assertEqual(jump_item.command.args[0], 8+len(new_cmd))  # Jump should be increased

        to_change = self.model.index(1,0,QModelIndex()).internalPointer()
        end_cmd = EventCommand.end_cmd()
        self.model.update_command(to_change, end_cmd)
        jump_item = jump_index.internalPointer()
        self.assertEqual(jump_item.command.args[0], 8+len(end_cmd)) # Should reflect the updated value
    
        self.model.delete_command(self.model.index(1,0, QModelIndex()))
        jump_item = jump_index.internalPointer()
        self.assertEqual(jump_item.command.args[0], 8) # Back to the original value

    def test_back_jump_command_updates(self):
        """Test that jump commands are properly updated when commands are inserted/deleted/updated"""
        base_address = 0x100
        current_address = base_address
        # Insert a pause command that the back jump will point to
        current_address, pause_cmd = self.append_command(EventCommand.pause(1), current_address)
        # Add a jump to the pause
        first_bytes_to_jump = current_address-base_address + 1
        first_jump_cmd_index = self.model.rowCount(QModelIndex())
        first_jump_address = current_address
        current_address, first_jump_cmd = self.append_command(EventCommand.jump_back(first_bytes_to_jump), current_address)
        
        # Add some additional commands and a back jump that isn't directly affected
        current_address, end1 = self.append_command(EventCommand.end_cmd(), current_address)
        current_address, end2 = self.append_command(EventCommand.end_cmd(), current_address)

        second_bytes_to_jump = current_address-end2.address + 1
        second_jump_cmd_index = self.model.rowCount(QModelIndex())
        second_jump_address = current_address
        current_address, second_jump_cmd = self.append_command(EventCommand.jump_back(second_bytes_to_jump), current_address)

        print_command_tree(self.model)
        # The setup is complete, now insert a command prior to the first jump.
        inserted_cmd = EventCommand.end_cmd()
        inserted_len = len(inserted_cmd)
        self.model.insert_command(QModelIndex(), 1, inserted_cmd, pause_cmd.address)

        # An additional command was inserted before both jumps
        first_jump_cmd_index+=1
        second_jump_cmd_index+=1

        # Verify that the command matches, the arg has been updated, and the address has shifted.
        new_j1 = self.model.index(first_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j1.command.command, first_jump_cmd.command.command)
        self.assertEqual(new_j1.command.args[0], first_bytes_to_jump+inserted_len)
        self.assertEqual(new_j1.address, first_jump_address + inserted_len)

        # Verify that the command matches, the arg has NOT been updated, and the address has shifted.
        new_j2 = self.model.index(second_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j2.command.command, second_jump_cmd.command.command)
        self.assertEqual(new_j2.command.args[0], second_bytes_to_jump)
        self.assertEqual(new_j2.address, second_jump_address + inserted_len)
    
        updated_cmd = EventCommand.add_gold(1)
        updated_cmd_length = len(updated_cmd)
        self.model.update_command(self.model.index(1,0,QModelIndex()).internalPointer(), updated_cmd)

        # Validate that the address and args have changed
        new_j1 = self.model.index(first_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j1.command.command, first_jump_cmd.command.command)
        self.assertEqual(new_j1.command.args[0], first_bytes_to_jump+updated_cmd_length)
        self.assertEqual(new_j1.address, first_jump_address + updated_cmd_length)

        # Validate that only the address has changed
        new_j2 = self.model.index(second_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j2.command.command, second_jump_cmd.command.command)
        self.assertEqual(new_j2.command.args[0], second_bytes_to_jump)
        self.assertEqual(new_j2.address, second_jump_address + updated_cmd_length)

        # Now delete the inserted item and verify that things have returned to their
        # original state
        self.model.delete_command(self.model.index(1,0,QModelIndex()))
        first_jump_cmd_index -= 1
        second_jump_cmd_index -= 1

        new_j1 = self.model.index(first_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j1.command.command, first_jump_cmd.command.command)
        self.assertEqual(new_j1.command.args[0], first_bytes_to_jump)
        self.assertEqual(new_j1.address, first_jump_address)

        # Validate that only the address has changed
        new_j2 = self.model.index(second_jump_cmd_index, 0, QModelIndex()).internalPointer()
        self.assertEqual(new_j2.command.command, second_jump_cmd.command.command)
        self.assertEqual(new_j2.command.args[0], second_bytes_to_jump)
        self.assertEqual(new_j2.address, second_jump_address)


    def test_drag_drop(self):
        """Test drag and drop functionality"""
        # Insert two commands
        cmd1 = EventCommand.script_speed(1)
        cmd2 = EventCommand.set_speed(2)
        
        self.model.insert_command(QModelIndex(), 0, cmd1, 0x100)
        self.model.insert_command(QModelIndex(), 1, cmd2, 0x102)
        
        # Create mime data for drag operation
        indexes = [self.model.index(0, 0, QModelIndex())]
        mime_data = self.model.mimeData(indexes)
        
        # Verify drop is allowed
        self.assertTrue(self.model.canDropMimeData(
            mime_data, 
            Qt.DropAction.MoveAction,
            1, 0, 
            self.model.index(1, 0, QModelIndex())
        ))
        
        # Perform drop
        success = self.model.dropMimeData(
            mime_data,
            Qt.DropAction.MoveAction,
            1, 0,
            self.model.index(1, 0, QModelIndex())
        )
        
        self.assertTrue(success)
        # Verify order of items after drop
        first_item = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.assertEqual(first_item.command, cmd2)

    def test_multi_byte_command_addressing(self):
        """Test address handling with variable-length commands"""
        # Create a complex command that takes multiple bytes
        battle_cmd = EventCommand.battle(no_win_pose=True, bottom_menu=True)
        self.model.insert_command(QModelIndex(), 0, battle_cmd, 0x100)
        
        # Add a simple command after it
        pause_cmd = EventCommand.pause(1)
        self.model.insert_command(QModelIndex(), 1, pause_cmd, 0x103)  # Should be 3 bytes later
        
        # Verify correct address calculation
        pause_index = self.model.index(1, 0, QModelIndex())
        pause_item = pause_index.internalPointer()
        self.assertEqual(pause_item.address, 0x103)


    def test_jump_bytes_auto_calculated_on_child_insert(self):
        """Inserting a child under a conditional updates args[-1] to the child's byte size."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        child_cmd = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child_cmd, 0x100 + len(if_cmd))

        self.assertEqual(if_item.command.args[-1], len(child_cmd))

    def test_jump_bytes_accumulates_across_multiple_children(self):
        """args[-1] equals the total byte size of all children."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        addr = 0x100 + len(if_cmd)
        children = [
            EventCommand.end_cmd(),        # 1 byte (0 args)
            EventCommand.return_cmd(),     # 1 byte (0 args)
            EventCommand.script_speed(1),  # 2 bytes (1 arg)
        ]
        for i, c in enumerate(children):
            self.model.insert_command(if_index, i, c, addr)
            addr += len(c)

        self.assertEqual(if_item.command.args[-1], sum(len(c) for c in children))

    def test_jump_bytes_decreases_on_child_delete(self):
        """Deleting a child decreases args[-1] by that command's size."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        child_base = 0x100 + len(if_cmd)
        child1 = EventCommand.end_cmd()
        child2 = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child1, child_base)
        self.model.insert_command(if_index, 1, child2, child_base + len(child1))

        self.assertEqual(if_item.command.args[-1], len(child1) + len(child2))

        self.model.delete_command(self.model.index(0, 0, if_index))

        self.assertEqual(if_item.command.args[-1], len(child2))

    def test_jump_bytes_updated_when_child_replaced_with_larger_command(self):
        """Replacing a child with a larger command increases args[-1]."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        small = EventCommand.end_cmd()      # 1 byte
        self.model.insert_command(if_index, 0, small, 0x100 + len(if_cmd))
        self.assertEqual(if_item.command.args[-1], len(small))

        bigger = EventCommand.script_speed(1)  # 2 bytes
        child_item = self.model.index(0, 0, if_index).internalPointer()
        self.model.update_command(child_item, bigger)

        self.assertEqual(if_item.command.args[-1], len(bigger))

    def test_jump_bytes_zero_with_no_children(self):
        """A freshly inserted conditional with no children has args[-1] == 0."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_item = self.model.index(0, 0, QModelIndex()).internalPointer()

        self.assertEqual(if_item.command.args[-1], 0)

    def test_jump_bytes_nested_conditional_cascade(self):
        """Inserting a grandchild updates both the inner and outer conditional."""
        outer_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, outer_cmd, 0x100)
        outer_index = self.model.index(0, 0, QModelIndex())
        outer_item = outer_index.internalPointer()

        inner_cmd = EventCommand.if_storyline_counter_lt(5, 0)
        inner_addr = 0x100 + len(outer_cmd)
        self.model.insert_command(outer_index, 0, inner_cmd, inner_addr)
        inner_index = self.model.index(0, 0, outer_index)
        inner_item = inner_index.internalPointer()

        grandchild = EventCommand.end_cmd()
        self.model.insert_command(inner_index, 0, grandchild, inner_addr + len(inner_cmd))

        self.assertEqual(inner_item.command.args[-1], len(grandchild))
        self.assertEqual(outer_item.command.args[-1], len(inner_cmd) + len(grandchild))

    def test_jump_bytes_nested_cascade_on_grandchild_delete(self):
        """Deleting a grandchild cascades the update up through both ancestors."""
        outer_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, outer_cmd, 0x100)
        outer_index = self.model.index(0, 0, QModelIndex())
        outer_item = outer_index.internalPointer()

        inner_cmd = EventCommand.if_storyline_counter_lt(5, 0)
        inner_addr = 0x100 + len(outer_cmd)
        self.model.insert_command(outer_index, 0, inner_cmd, inner_addr)
        inner_index = self.model.index(0, 0, outer_index)
        inner_item = inner_index.internalPointer()

        grandchild = EventCommand.end_cmd()
        self.model.insert_command(inner_index, 0, grandchild, inner_addr + len(inner_cmd))

        gc_index = self.model.index(0, 0, inner_index)
        self.model.delete_command(gc_index)

        self.assertEqual(inner_item.command.args[-1], 0)
        self.assertEqual(outer_item.command.args[-1], len(inner_cmd))

    def test_sibling_conditionals_have_independent_jump_bytes(self):
        """Inserting a child under one conditional does not alter its sibling."""
        if1 = EventCommand.if_has_item(5, 0)
        if2 = EventCommand.if_storyline_counter_lt(3, 0)
        self.model.insert_command(QModelIndex(), 0, if1, 0x100)
        self.model.insert_command(QModelIndex(), 1, if2, 0x100 + len(if1))

        if1_index = self.model.index(0, 0, QModelIndex())
        if1_item = if1_index.internalPointer()
        if2_item = self.model.index(1, 0, QModelIndex()).internalPointer()

        child = EventCommand.end_cmd()
        self.model.insert_command(if1_index, 0, child, 0x100 + len(if1))

        self.assertEqual(if1_item.command.args[-1], len(child))
        self.assertEqual(if2_item.command.args[-1], 0)

    def test_update_conditional_to_noncond_promotes_children(self):
        """Replacing a conditional with a non-conditional promotes its children as siblings."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        child_base = 0x100 + len(if_cmd)
        child1 = EventCommand.end_cmd()
        child2 = EventCommand.return_cmd()
        self.model.insert_command(if_index, 0, child1, child_base)
        self.model.insert_command(if_index, 1, child2, child_base + len(child1))

        replacement = EventCommand.pause(1)
        self.model.update_command(if_item, replacement)

        # Replaced command at row 0, promoted children at rows 1 and 2
        self.assertEqual(self.model.rowCount(QModelIndex()), 3)

        item0 = self.model.index(0, 0, QModelIndex()).internalPointer()
        item1 = self.model.index(1, 0, QModelIndex()).internalPointer()
        item2 = self.model.index(2, 0, QModelIndex()).internalPointer()

        self.assertEqual(item0.command.command, replacement.command)
        self.assertEqual(item1.command.command, child1.command)
        self.assertEqual(item2.command.command, child2.command)

        # Parent pointers updated to root level
        self.assertIs(item1.parent, item0.parent)
        self.assertIs(item2.parent, item0.parent)

    def test_update_conditional_to_noncond_no_children(self):
        """Replacing a childless conditional causes no promotion and no crash."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_item = self.model.index(0, 0, QModelIndex()).internalPointer()

        replacement = EventCommand.end_cmd()
        self.model.update_command(if_item, replacement)

        self.assertEqual(self.model.rowCount(QModelIndex()), 1)
        self.assertEqual(if_item.command.command, replacement.command)

    def test_delete_conditional_promotes_children(self):
        """Deleting a conditional promotes its children to the parent level."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())

        child_base = 0x100 + len(if_cmd)
        child1 = EventCommand.end_cmd()
        child2 = EventCommand.return_cmd()
        self.model.insert_command(if_index, 0, child1, child_base)
        self.model.insert_command(if_index, 1, child2, child_base + len(child1))

        self.model.delete_command(self.model.index(0, 0, QModelIndex()))

        self.assertEqual(self.model.rowCount(QModelIndex()), 2)
        item0 = self.model.index(0, 0, QModelIndex()).internalPointer()
        item1 = self.model.index(1, 0, QModelIndex()).internalPointer()
        self.assertEqual(item0.command.command, child1.command)
        self.assertEqual(item1.command.command, child2.command)

    def test_delete_conditional_with_nested_conditional_child(self):
        """Deleting an outer conditional promotes the inner conditional with its subtree intact."""
        outer = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, outer, 0x100)
        outer_index = self.model.index(0, 0, QModelIndex())

        inner = EventCommand.if_storyline_counter_lt(3, 0)
        inner_addr = 0x100 + len(outer)
        self.model.insert_command(outer_index, 0, inner, inner_addr)
        inner_index = self.model.index(0, 0, outer_index)

        grandchild = EventCommand.end_cmd()
        self.model.insert_command(inner_index, 0, grandchild, inner_addr + len(inner))

        self.model.delete_command(self.model.index(0, 0, QModelIndex()))

        # Inner conditional promoted to root
        self.assertEqual(self.model.rowCount(QModelIndex()), 1)
        promoted = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.assertEqual(promoted.command.command, inner.command)

        # Inner conditional retains its grandchild
        self.assertEqual(len(promoted.children), 1)
        self.assertEqual(promoted.children[0].command.command, grandchild.command)

    def test_update_command_size_increase_shifts_addresses(self):
        """Replacing a command with a larger one shifts subsequent addresses forward."""
        small = EventCommand.end_cmd()         # 1 byte
        big = EventCommand.script_speed(1)     # 2 bytes
        follower = EventCommand.return_cmd()   # 1 byte

        self.model.insert_command(QModelIndex(), 0, small, 0x100)
        self.model.insert_command(QModelIndex(), 1, follower, 0x100 + len(small))

        follower_item = self.model.index(1, 0, QModelIndex()).internalPointer()
        original_addr = follower_item.address

        small_item = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.model.update_command(small_item, big)

        self.assertEqual(follower_item.address, original_addr + (len(big) - len(small)))

    def test_update_command_size_decrease_shifts_addresses(self):
        """Replacing a command with a smaller one shifts subsequent addresses backward."""
        big = EventCommand.script_speed(1)     # 2 bytes
        small = EventCommand.end_cmd()         # 1 byte
        follower = EventCommand.return_cmd()   # 1 byte

        self.model.insert_command(QModelIndex(), 0, big, 0x100)
        self.model.insert_command(QModelIndex(), 1, follower, 0x100 + len(big))

        follower_item = self.model.index(1, 0, QModelIndex()).internalPointer()
        original_addr = follower_item.address

        big_item = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.model.update_command(big_item, small)

        self.assertEqual(follower_item.address, original_addr + (len(small) - len(big)))

    def test_insert_at_position_zero_shifts_existing(self):
        """Inserting at position 0 pushes existing commands' addresses forward."""
        existing = EventCommand.end_cmd()      # 1 byte
        self.model.insert_command(QModelIndex(), 0, existing, 0x100)

        new_cmd = EventCommand.script_speed(1)  # 2 bytes
        self.model.insert_command(QModelIndex(), 0, new_cmd, 0x100)

        self.assertEqual(self.model.rowCount(QModelIndex()), 2)
        first = self.model.index(0, 0, QModelIndex()).internalPointer()
        second = self.model.index(1, 0, QModelIndex()).internalPointer()

        self.assertEqual(first.command.command, new_cmd.command)
        self.assertEqual(first.address, 0x100)
        self.assertEqual(second.address, 0x100 + len(new_cmd))

    def test_forward_jump_not_updated_when_insertion_after_target(self):
        """A bare forward jump is not adjusted when a command is inserted after its target."""
        jump_dist = 4
        jump = EventCommand.jump_forward(jump_dist)
        self.model.insert_command(QModelIndex(), 0, jump, 0x100)

        # Jump target = 0x100 + jump_dist = 0x104.  Insert after the target.
        after_target_addr = 0x100 + jump_dist + len(jump)
        filler = EventCommand.end_cmd()
        self.model.insert_command(QModelIndex(), 1, filler, after_target_addr)

        jump_item = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.assertEqual(jump_item.command.args[-1], jump_dist)

    def test_copy_produces_independent_command(self):
        """Modifying the original after copying does not affect the copy."""
        cmd = EventCommand.script_speed(1)
        self.model.insert_command(QModelIndex(), 0, cmd, 0x100)
        index = self.model.index(0, 0, QModelIndex())

        copied_items = self.model.copy_items([index])
        self.assertEqual(len(copied_items), 1)
        copied_item, _ = copied_items[0]
        original_cmd_id = copied_item.command.command

        # Replace the original with a different command
        original_item = index.internalPointer()
        self.model.update_command(original_item, EventCommand.end_cmd())

        self.assertEqual(copied_item.command.command, original_cmd_id)

    def test_copy_conditional_includes_children(self):
        """A deep copy of a conditional item includes its children."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())

        child = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child, 0x100 + len(if_cmd))

        copied_items = self.model.copy_items([if_index])
        copied_item, _ = copied_items[0]

        self.assertEqual(copied_item.command.command, if_cmd.command)
        self.assertEqual(len(copied_item.children), 1)
        self.assertEqual(copied_item.children[0].command.command, child.command)

    def test_copy_children_are_independent_of_originals(self):
        """Copied children share no references with the original tree."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())
        if_item = if_index.internalPointer()

        child = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, child, 0x100 + len(if_cmd))

        copied_items = self.model.copy_items([if_index])
        copied_item, _ = copied_items[0]

        # Modify the copy's child args directly; original must be unaffected
        copied_item.children[0].command.args = [0xFF]
        original_child = if_item.children[0]
        self.assertNotEqual(original_child.command.args, [0xFF])

    def test_cut_removes_source_item(self):
        """Cutting an item removes it from the model and returns its data."""
        cmd1 = EventCommand.end_cmd()
        cmd2 = EventCommand.return_cmd()
        self.model.insert_command(QModelIndex(), 0, cmd1, 0x100)
        self.model.insert_command(QModelIndex(), 1, cmd2, 0x100 + len(cmd1))

        cut = self.model.cut_items([self.model.index(0, 0, QModelIndex())])

        self.assertEqual(len(cut), 1)
        self.assertEqual(self.model.rowCount(QModelIndex()), 1)
        remaining = self.model.index(0, 0, QModelIndex()).internalPointer()
        self.assertEqual(remaining.command.command, cmd2.command)

    def test_paste_inserts_after_target(self):
        """Pasting after a target item places the copy at the correct position and address."""
        cmd1 = EventCommand.script_speed(1)   # 2 bytes
        cmd2 = EventCommand.end_cmd()         # 1 byte
        self.model.insert_command(QModelIndex(), 0, cmd1, 0x100)
        self.model.insert_command(QModelIndex(), 1, cmd2, 0x100 + len(cmd1))

        idx0 = self.model.index(0, 0, QModelIndex())
        idx1 = self.model.index(1, 0, QModelIndex())

        copied = self.model.copy_items([idx0])
        self.model.paste_items(copied, idx1)

        self.assertEqual(self.model.rowCount(QModelIndex()), 3)
        pasted = self.model.index(2, 0, QModelIndex()).internalPointer()
        self.assertEqual(pasted.command.command, cmd1.command)

        cmd2_item = self.model.index(1, 0, QModelIndex()).internalPointer()
        self.assertEqual(pasted.address, cmd2_item.address + len(cmd2_item.command))

    def test_paste_onto_conditional_inserts_as_first_child(self):
        """Pasting onto a conditional that already has children inserts at position 0."""
        if_cmd = EventCommand.if_has_item(5, 0)
        self.model.insert_command(QModelIndex(), 0, if_cmd, 0x100)
        if_index = self.model.index(0, 0, QModelIndex())

        child_base = 0x100 + len(if_cmd)
        existing_child = EventCommand.end_cmd()
        self.model.insert_command(if_index, 0, existing_child, child_base)

        # Copy a command and paste it onto the conditional
        dummy = EventCommand.return_cmd()
        self.model.insert_command(QModelIndex(), 1, dummy, child_base + len(existing_child))
        dummy_index = self.model.index(1, 0, QModelIndex())
        copied = self.model.copy_items([dummy_index])

        if_index = self.model.index(0, 0, QModelIndex())
        self.model.paste_items(copied, if_index)

        self.assertEqual(self.model.rowCount(if_index), 2)
        first_child = self.model.index(0, 0, if_index).internalPointer()
        self.assertEqual(first_child.command.command, dummy.command)


if __name__ == '__main__':
    unittest.main()