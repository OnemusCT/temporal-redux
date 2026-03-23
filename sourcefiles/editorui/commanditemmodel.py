from __future__ import annotations
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData
from PyQt6.QtGui import QBrush, QColor, QFont
from jetsoftime.eventcommand import EventCommand
import editorui.commandtotext as c2t
from editorui.commanditem import CommandItem, process_script
from editorui.activitylog import ActivityLog
from gamebackend import GameBackend


def _delete_batch(model: 'CommandModel', indexes: list[QModelIndex]) -> None:
    """Delete a batch of items correctly when parent and child items may both be selected.

    Sorts all selected items by address descending so that children (which always have
    higher addresses than their parent's opcode) are deleted before their parents.
    By the time a conditional parent is processed its children are already gone from the
    tree, so no erroneous promotion occurs and all bytes are removed from the script.
    Object nodes (address=None) sort first so delete_object runs before any child commands.
    """
    def sort_key(idx):
        addr = idx.internalPointer().address
        return addr if addr is not None else float('inf')
    sorted_indexes = sorted(indexes, key=sort_key, reverse=True)
    for index in sorted_indexes:
        if index.isValid():
            model.delete_command(index)


class CommandModel(QAbstractItemModel):
    def __init__(self, root_item: CommandItem, parent=None, backend: GameBackend=None, location_id: int=None):
        super().__init__(parent)
        self._root_item = root_item
        self._backend = backend
        self._location_id = location_id
        self._log: ActivityLog | None = None
        self._suppress_log: bool = False
        self._suppress_idle_refresh: bool = False

    def set_backend(self, backend: GameBackend) -> None:
        self._backend = backend

    def set_log(self, log: ActivityLog | None) -> None:
        self._log = log

    @staticmethod
    def _item_context(item: CommandItem) -> str:
        """Return a breadcrumb path for the item's parent chain, e.g. 'Object 0C > Startup / Idle'."""
        parts = []
        node = item.parent
        while node is not None and node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return " > ".join(reversed(parts))

    def update_command(self, item: CommandItem, new_command: EventCommand):
        """Update an item's command and adjust subsequent addresses based on command size change"""
        if self._log is not None:
            self._log.log_command_update(
                self._location_id, item.address,
                item.command, new_command,
                self._item_context(item),
            )
        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            # Address-based replacement: insert new bytes then delete the old command.
            # Avoids the fragility of replace_command's byte-search approach, which
            # silently does nothing when item.command doesn't exactly match the script
            # bytes (e.g. platform-specific arg_lens differences).
            script.insert_commands(new_command.to_bytearray(), item.address)
            script.delete_commands(item.address + len(new_command), 1)
        # Calculate size difference
        old_size = len(item.command) if item.command else 0
        new_size = len(new_command)
        size_diff = new_size - old_size

        # Get the model index for this item
        item_index = self.get_index_for_item(item)
        
        # Handle promotion of children if changing from conditional to non-conditional command
        if item.command.command in EventCommand.conditional_commands and new_command.command not in EventCommand.conditional_commands:
            parent = item.parent
            children_to_promote = item.children[:]
            
            if not children_to_promote:
                # If no children, just update the command
                pass
            elif parent is not None:
                # Find index of current item in parent's children
                item_idx = parent.children.index(item)
                
                # Calculate the insert position (right after the current item)
                insert_position = item_idx + 1
                
                # Notify model about upcoming insertion
                parent_index = self.get_index_for_item(parent)
                self.beginInsertRows(parent_index, insert_position, 
                                insert_position + len(children_to_promote) - 1)
                
                # Update parent references and insert children
                for child in children_to_promote:
                    child.parent = parent
                parent.children[insert_position:insert_position] = children_to_promote
                
                # Clear original children list
                item.children = []
                
                self.endInsertRows()
                
            else:
                # Handle root level promotion
                item_idx = self._root_item.children.index(item)
                insert_position = item_idx + 1
                
                # Notify model about upcoming insertion at root level
                self.beginInsertRows(QModelIndex(), insert_position, 
                                insert_position + len(children_to_promote) - 1)
                
                # Update parent references and insert children
                for child in children_to_promote:
                    child.parent = self._root_item
                self._root_item.children[insert_position:insert_position] = children_to_promote
                
                # Clear original children list
                item.children = []
                
                self.endInsertRows()
        
        # Update the command and name
        item.command = new_command
        item.name = c2t.command_to_text(item.command, item.address, [])
        
        # Emit signal for possible command-related display changes
        self.dataChanged.emit(
            self.createIndex(item_index.row(), 0, item),
            self.createIndex(item_index.row(), 1, item),
            [Qt.ItemDataRole.DisplayRole]
        )

        self._recalculate_jump_bytes(item)
        self._recalculate_ancestor_jumps(item)

        if size_diff != 0:  # Only update addresses if size changed
            # Get all items that come after this one
            self._update_jump_parameters(item, size_diff)
            self._update_addresses(item, size_diff)
            
    def insert_command(self, parent_index: QModelIndex, position: int, command: EventCommand, address: int) -> bool:
        """
        Insert a new command at the specified position.
        
        Args:
            parent_index: Parent model index where command should be inserted
            position: Position in parent's children where command should be inserted
            command: The EventCommand to insert
            address: The hex address where the command will be inserted
            
        Returns:
            bool: True if insertion was successful
        """
        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            script.insert_commands(command.to_bytearray(), address)
        parent_item = self._root_item if not parent_index.isValid() else parent_index.internalPointer()
        if self._log is not None and not self._suppress_log:
            # Build a temporary item to get context; parent_item is the container.
            _ctx_item = CommandItem("", command, address)
            _ctx_item.parent = parent_item
            self._log.log_command_insert(
                self._location_id, address, command, self._item_context(_ctx_item)
            )
        
        # Create new command item
        new_item = CommandItem(
            c2t.command_to_text(command, address, []),
            command,
            address
        )
        
        # Notify model about upcoming insertion
        self.beginInsertRows(parent_index, position, position)
        
        # Insert the new item
        new_item.parent = parent_item
        parent_item.children.insert(position, new_item)
        
        # Update addresses of all subsequent commands
        command_size = len(command)
        self._update_jump_parameters(new_item, command_size, True)
        self._recalculate_ancestor_jumps(new_item)
        self._update_addresses(new_item, command_size, True)
        
        # End insertion process
        self.endInsertRows()
        if not self._suppress_idle_refresh:
            self._refresh_idle_label(self._get_func_node(parent_item))
        return True

    def delete_command(self, index: QModelIndex) -> bool:
        """
        Delete the command at the specified index.

        Args:
            index: Model index of command to delete

        Returns:
            bool: True if deletion was successful
        """
        if not index.isValid():
            return False

        item = index.internalPointer()
        if item.is_section_label:
            return False

        parent_item = item.parent
        if parent_item is None:
            return False

        if self._log is not None and not self._suppress_log and item.command is not None:
            self._log.log_command_delete(
                self._location_id, item.address, item.command, self._item_context(item)
            )

        func_node = self._get_func_node(item)

        # Handle object node deletion (command is None, parent is root)
        if item.command is None and parent_item == self._root_item:
            obj_id = index.row()
            obj_len = 0
            if self._backend is not None:
                script = self._backend.get_script(self._location_id)
                obj_start = script.get_object_start(obj_id)
                obj_end = script.get_object_end(obj_id)
                obj_len = obj_end - obj_start
                script.delete_object(obj_id)
            parent_index = self.parent(index)
            self.beginRemoveRows(parent_index, index.row(), index.row())
            parent_item.children.pop(index.row())
            self.endRemoveRows()
            # Adjust addresses of all remaining objects: objects that were before the
            # deleted one shift by -32 (pointer table removed); objects after shift by
            # -(32 + obj_len) (pointer table + bytecode removed).
            for i, object_node in enumerate(self._root_item.children):
                original_obj_id = i if i < obj_id else i + 1
                addr_shift = -32 if original_obj_id < obj_id else -(32 + obj_len)
                self._shift_subtree_addresses(object_node, addr_shift)
            return True

        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            script.delete_commands(index.internalPointer().address)

        command_size = len(item.command) if item.command else 0
        parent_index = self.parent(index)

        # Handle children of deleted item if it's a conditional command
        if item.command and item.command.command in EventCommand.conditional_commands and item.children:
            # Find position to promote children to
            item_pos = parent_item.children.index(item)

            # Remove the item itself
            self.beginRemoveRows(parent_index, index.row(), index.row())
            parent_item.children.pop(index.row())
            self.endRemoveRows()

            # Insert promoted children
            self.beginInsertRows(parent_index, item_pos,
                                 item_pos + len(item.children) - 1)
            for child in item.children:
                child.parent = parent_item
            parent_item.children[item_pos:item_pos] = item.children
            self.endInsertRows()
        else:
            # Simple removal without child promotion
            self.beginRemoveRows(parent_index, index.row(), index.row())
            parent_item.children.pop(index.row())
            self.endRemoveRows()

        item = index.internalPointer()
        self._update_jump_parameters(item, -command_size)
        self._recalculate_ancestor_jumps(item)
        self._update_addresses(item, -command_size)
        self._refresh_idle_label(func_node)
        return True

    def copy_items(self, indexes: list[QModelIndex]) -> list[tuple[CommandItem, int]]:
        """Copy selected items and return list of (item, address_offset) tuples"""
        if not indexes:
            return []

        col0 = [idx for idx in indexes if idx.column() == 0]
        selected_items = {idx.internalPointer() for idx in col0}

        # Only copy root-level selections — children of a selected conditional are
        # already included via the parent's deep copy; copying them separately would
        # produce duplicates and flatten the tree structure.
        root_indexes = [idx for idx in col0
                        if idx.internalPointer().parent not in selected_items]

        if not root_indexes:
            return []

        base_addr = min(idx.internalPointer().address for idx in root_indexes)

        copied_items = []
        for index in root_indexes:
            item = index.internalPointer()
            copied_item = self._deep_copy_item(item)
            addr_offset = item.address - base_addr
            copied_items.append((copied_item, addr_offset))

        return copied_items

    def cut_items(self, indexes: list[QModelIndex]) -> list[tuple[CommandItem, int]]:
        """Cut selected items - copy them and then delete them"""
        copied_items = self.copy_items(indexes)

        col0_indexes = [idx for idx in indexes if idx.column() == 0]
        _delete_batch(self, col0_indexes)

        return copied_items

    def paste_items(self, items: list[tuple[CommandItem, int]], target_index: QModelIndex):
        """Paste copied/cut items at the target location"""
        if not items:
            return

        target_item = target_index.internalPointer() if target_index.isValid() else self._root_item

        if target_item.command and target_item.command.command in EventCommand.conditional_commands:
            target_parent = target_item
            insert_pos = 0
            insert_address = target_item.address + len(target_item.command)
        else:
            target_parent = target_item.parent if target_item.parent else self._root_item
            insert_pos = target_parent.children.index(target_item) + 1
            insert_address = target_item.address + len(target_item.command)

        parent_index = self.get_index_for_item(target_parent)
        self._suppress_idle_refresh = True
        try:
            for item, offset in items:
                self._paste_recursive(item, parent_index, insert_pos, insert_address + offset)
                insert_pos += 1
        finally:
            self._suppress_idle_refresh = False
            self._refresh_idle_label(self._get_func_node(target_parent))

    def _paste_recursive(self, copied_item: CommandItem, parent_index: QModelIndex,
                         position: int, address: int) -> None:
        """Insert a copied item and recursively insert its children under it."""
        self.insert_command(parent_index, position, copied_item.command, address)
        if not copied_item.children:
            return
        parent_item = parent_index.internalPointer() if parent_index.isValid() else self._root_item
        new_item = parent_item.children[position]
        new_index = self.index(position, 0, parent_index)
        child_address = address + len(copied_item.command)
        for i, child in enumerate(copied_item.children):
            self._paste_recursive(child, new_index, i, child_address)
            child_address += self._subtree_size(child)

    def _subtree_size(self, item: CommandItem) -> int:
        """Total byte size of an item and all its descendants."""
        if item.command is None:
            return 0
        size = len(item.command)
        for child in item.children:
            size += self._subtree_size(child)
        return size

    def _delete_subtree(self, item: CommandItem) -> None:
        """Delete an item and all its descendants without promoting children.

        Deletes children deepest-first (highest address first) so that by the
        time a conditional parent is processed it has no children and
        delete_command will not trigger promotion.
        """
        for child in sorted(item.children, key=lambda c: c.address or 0, reverse=True):
            self._delete_subtree(child)
        idx = self.get_index_for_item(item)
        if idx.isValid():
            self.delete_command(idx)

    def _deep_copy_item(self, item: CommandItem) -> CommandItem:
        """Create a deep copy of a CommandItem and its children"""
        # Copy command
        if item.command:
            new_command = item.command.copy()
        else:
            new_command = None
            
        # Create new item
        new_item = CommandItem(
            name=item.name,
            command=new_command,
            address=item.address
        )
        
        # Recursively copy children
        for child in item.children:
            child_copy = self._deep_copy_item(child)
            child_copy.parent = new_item
            new_item.children.append(child_copy)
            
        return new_item

    def _get_func_node(self, item: CommandItem) -> CommandItem | None:
        """Walk up the tree to find the nearest ancestor that is a function node."""
        node = item
        while node is not None:
            if hasattr(node, 'func_id'):
                return node
            node = node.parent
        return None

    def _refresh_idle_label(self, func_node: CommandItem | None) -> None:
        """After any structural change to a Startup/Idle function, reposition the Idle label."""
        if func_node is None or not hasattr(func_node, 'func_id') or func_node.func_id != 0:
            return
        func_index = self.get_index_for_item(func_node)
        # Remove any existing section label
        for i, child in enumerate(func_node.children):
            if child.is_section_label:
                self.beginRemoveRows(func_index, i, i)
                func_node.children.pop(i)
                self.endRemoveRows()
                break
        # Find first top-level Return (0x00) and insert the label after it
        for idx, child in enumerate(func_node.children):
            if child.command is not None and child.command.command == 0x00:
                if idx + 1 < len(func_node.children):
                    sep = CommandItem("─── Idle ───")
                    sep.is_section_label = True
                    sep.parent = func_node
                    insert_pos = idx + 1
                    self.beginInsertRows(func_index, insert_pos, insert_pos)
                    func_node.children.insert(insert_pos, sep)
                    self.endInsertRows()
                break

    def _shift_subtree_addresses(self, node: CommandItem, shift: int) -> None:
        """Recursively shift the address of every item in a subtree by shift bytes.
        Regenerates display names for commands whose text embeds the item's address (0x10, 0x11)."""
        if node.address is not None:
            node.address += shift
            if node.command is not None and node.command.command in (0x10, 0x11):
                node.name = c2t.command_to_text(node.command, node.address, [])
        for child in node.children:
            self._shift_subtree_addresses(child, shift)

    def _update_addresses(self,  modified_item: CommandItem, size_change: int, insertion: bool = False):
        all_commands = _get_all_commands(self._root_item)
        # print("Modified address: 0x{:02X}".format(modified_item.address))
        seen_modified = False
        for command in all_commands:
            changed = False
            if command.address:
                # print("Checking 0x{:02X} - {}".format(command.address, command.command))
                if command.address > modified_item.address:
                    command.address += size_change
                    changed = True
                # If there is an insertion there are going to be two commands
                # with the same address, the original and the newly inserted.
                # We only want to update the second of the two.
                elif insertion and command.address == modified_item.address:
                    if not seen_modified:
                        seen_modified = True
                    else: 
                        command.address += size_change
                        changed = True
            if command.command and (command.command.command == 0x10 or command.command.command == 0x11):
                command.name = c2t.command_to_text(command.command, command.address, [])
                changed = True
            if changed:
                affected_index = self.get_index_for_item(command)
                self.dataChanged.emit(
                    self.createIndex(affected_index.row(), 0, affected_index.internalPointer()),
                    self.createIndex(affected_index.row(), 1, affected_index.internalPointer()),
                    [Qt.ItemDataRole.DisplayRole]
                )

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        return default_flags | Qt.ItemFlag.ItemIsDropEnabled

    def mimeTypes(self) -> list[str]:
        return ['application/x-commanditem']

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        mime_data = QMimeData()
        encoded_data = bytearray()
        
        # Store the row and parent information for each index
        selected_items = []
        for index in indexes:
            if index.column() == 0:  # Only process first column
                item = index.internalPointer()
                selected_items.append((item, index))
        
        # Store the selected items in mime data
        mime_data.setData('application/x-commanditem', bytes(str(id(selected_items)), 'utf-8'))
        # Store the actual items in a class variable for access during drop
        self._drag_items = selected_items
        return mime_data

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not data.hasFormat('application/x-commanditem'):
            return False
            
        if not hasattr(self, '_drag_items'):
            return False
            
        # Get target item
        target_item = parent.internalPointer() if parent.isValid() else self._root_item
        if getattr(target_item, 'is_section_label', False):
            return False
        
        # Check if any dragged item is an ancestor of the target
        for (item, _) in self._drag_items:
            current = target_item
            while current is not None:
                if current == item:
                    print("Error: Cannot drop an item onto its own descendant")
                    return False
                current = current.parent
                
        return True

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent):
            return False

        if action == Qt.DropAction.IgnoreAction:
            return True

        # Get target item and dragged items
        target_item = parent.internalPointer() if parent.isValid() else self._root_item
        
        # Filter to root-level items only (exclude children of selected parents)
        drag_item_set = {item for item, _ in self._drag_items}
        root_drag = [(item, idx) for item, idx in self._drag_items
                     if item.parent and item.parent not in drag_item_set]

        # Capture source info and deep-copy subtrees BEFORE any deletion
        move_sources = [(item.address, self._item_context(item)) for item, _ in root_drag]
        deep_copies = [self._deep_copy_item(item) for item, _ in root_drag]

        # Delete subtrees highest-address-first so address shifts don't invalidate
        # later deletions; suppress log and idle-label refresh during deletion phase
        self._suppress_log = True
        self._suppress_idle_refresh = True
        for item, _ in sorted(root_drag, key=lambda x: x[0].address or 0, reverse=True):
            self._delete_subtree(item)
        self._suppress_log = False
        self._suppress_idle_refresh = False

        items_to_move = list(zip(deep_copies, move_sources))
        # Determine insert position and parent
        if target_item.command and target_item.command.command in EventCommand.conditional_commands:
            # Case 1: Dropping onto a conditional command - insert at beginning of its children
            target_parent = target_item
            insert_pos = 0
            # Calculate insert address - should be right after the conditional command
            insert_address = target_item.address + len(target_item.command)
        elif target_item.command is None:
            # Case 2: Dropping onto a structural node (function/object header) with no command
            # Insert at the beginning of its children
            target_parent = target_item
            insert_pos = 0
            if target_item.children:
                insert_address = target_item.children[0].address
            else:
                insert_address = target_item.address
        else:
            # Case 3: Dropping after a command - insert after it in its parent
            target_parent = target_item.parent if target_item.parent else self._root_item
            insert_pos = target_parent.children.index(target_item) + 1
            # Calculate insert address - should be after the target item
            insert_address = target_item.address + len(target_item.command)

        # Insert subtrees at new position; suppress idle-label refresh until done
        parent_index = self.get_index_for_item(target_parent)
        self._suppress_log = True
        self._suppress_idle_refresh = True
        current_address = insert_address
        for deep_copy, (src_address, src_context) in items_to_move:
            self._paste_recursive(deep_copy, parent_index, insert_pos, current_address)
            insert_pos += 1
            current_address += self._subtree_size(deep_copy)
        self._suppress_log = False
        self._suppress_idle_refresh = False
        self._refresh_idle_label(self._get_func_node(target_parent))

        # Log one move entry per root item
        current_address = insert_address
        for deep_copy, (src_address, src_context) in items_to_move:
            if self._log is not None:
                self._log.log_command_move(
                    self._location_id, src_address, current_address,
                    deep_copy.command, src_context,
                )
            current_address += self._subtree_size(deep_copy)

        print_command_tree(self)
        return True

    def get_all_items_after(self, start_item: CommandItem) -> list[CommandItem]:
        """Get all items that come after the given item in a depth-first traversal of the entire tree"""
        items = []
        found_start = False
        
        def traverse(item: CommandItem):
            nonlocal found_start, items
            
            # Check if this is the start item
            if item == start_item:
                found_start = True
                return
                
            # If we've found the start item, add this item to our list
            if found_start:
                items.append(item)
                
            # Continue traversing children
            for child in item.children:
                traverse(child)
        
        def traverse_from_root():
            nonlocal found_start, items  # Add nonlocal declaration here
            
            # Start with root's children
            for root_child in self._root_item.children:
                # If we've found our start item, add all subsequent items
                if found_start:
                    items.append(root_child)
                    # Add all descendants of this item
                    for child in root_child.children:
                        traverse(child)
                else:
                    # If this is our start item, mark it and continue to next sibling
                    if root_child == start_item:
                        found_start = True
                        continue
                        
                    # Haven't found start item yet, traverse this subtree
                    traverse(root_child)
        
        # Start the traversal
        traverse_from_root()
        return items

    def _collect_all_children(self, item: CommandItem, items: list[CommandItem]):
        """Helper method to collect all children of an item"""
        for child in item.children:
            items.append(child)
            self._collect_all_children(child, items)

    def get_index_for_item(self, item: CommandItem) -> QModelIndex:
        """Find the model index for a given item"""
        if item == self._root_item or item is None:
            return QModelIndex()
            
        if item.parent == self._root_item:
            row = self._root_item.children.index(item)
            return self.createIndex(row, 0, item)
        else:
            parent = item.parent
            row = parent.children.index(item)
            parent_index = self.get_index_for_item(parent)
            return self.index(row, 0, parent_index)

    def rowCount(self, parent: QModelIndex) -> int:
        if parent.isValid() and parent.column() != 0:
            return 0
        if not parent.isValid():
            return len(self._root_item.children)
        parent_item: CommandItem = parent.internalPointer()
        return len(parent_item.children)

    def columnCount(self, parent: QModelIndex) -> int:
        return 2  # Two columns: name and address

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        if not index.isValid():
            return None

        item: CommandItem = index.internalPointer()

        if item.is_section_label:
            if role == Qt.ItemDataRole.DisplayRole:
                return item.name if index.column() == 1 else ""
            if role == Qt.ItemDataRole.ForegroundRole:
                return QBrush(QColor("#888888"))
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setItalic(True)
                return font
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 1:
                return item.name
            elif index.column() == 0:
                return "0x{:02X}".format(item.address) if item.address is not None else ""

        if role == Qt.ItemDataRole.ForegroundRole and item.is_link:
            return QBrush(QColor("#888888"))

        if role == Qt.ItemDataRole.ToolTipRole and item.is_link:
            if item.link_target is not None:
                from editorui.commanditem import _get_function_name
                tgt_obj, tgt_func = item.link_target
                return f"Shares bytecode with Obj {tgt_obj:02X} {_get_function_name(tgt_func)}"
            return "Unresolved link"

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Address", "Command"][section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        if index.internalPointer().is_section_label:
            return Qt.ItemFlag.ItemIsEnabled

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            # Getting a top-level item
            parent_item = self._root_item
        else:
            # Getting a child item
            parent_item = parent.internalPointer()

        child_item = parent_item.get_child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        child_item: CommandItem = index.internalPointer()
        parent_item = child_item.parent

        if parent_item is None or parent_item == self._root_item:
            return QModelIndex()

        # Find the row of the parent within its parent's children
        if parent_item.parent is not None:
            row = parent_item.parent.children.index(parent_item)
        else:
            row = 0

        return self.createIndex(row, 0, parent_item)

    def replace_items(self, new_root_item: CommandItem):
        # Tell views we're about to replace everything
        self.beginResetModel()
        
        # Ensure all items have proper parent references
        def setup_parents(item: CommandItem, parent: CommandItem):
            item.parent = parent
            for child in item.children:
                setup_parents(child, item)
        
        # Setup parent references for all items
        for child in new_root_item.children:
            setup_parents(child, new_root_item)
        
        # Replace the root item
        self._root_item = new_root_item
        
        # Tell views we're done
        self.endResetModel()

    def _update_jump_parameters(self, modified_item: CommandItem, size_change: int, insertion=False):
        all_commands = _get_all_commands(self._root_item)
        seen_modified = False
        for item in all_commands:
            if item.command and item.command.command in EventCommand.fwd_jump_commands and item.command.command not in EventCommand.conditional_commands:
                jump_target = item.address + len(item.command) + item.command.args[-1] - 1
                #print("FWD - Modified addr: {:02X}\nJump Start: {:02X}\nJump Target: {:02X}".format(modified_item.address, jump_start, jump_target))
                # If target is AT modified_item, we only push it if this is an insertion.
                # If it's a deletion/update, the target stays at this address.
                if insertion:
                    target_affected = jump_target >= modified_item.address
                else:
                    target_affected = jump_target > modified_item.address
                    
                if item.address < modified_item.address and target_affected:
                    item.command.args[-1] += size_change
                    
                    # Notify model of change
                    item_index = self.get_index_for_item(item)
                    self.dataChanged.emit(
                        self.createIndex(item_index.row(), 0, item),
                        self.createIndex(item_index.row(), 1, item),
                        [Qt.ItemDataRole.DisplayRole]
                    )
            elif item.command and item.command.command == 0x11:
                jump_target = item.address + len(item.command) - item.command.args[0] - 1
                
                if insertion:
                    target_affected = jump_target <= modified_item.address
                else:
                    target_affected = jump_target < modified_item.address
                    
                address_check = item.address > modified_item.address and target_affected
                # If this is an insertion there will be two items with the same address. The 
                # inserted item and the item that it was inserted before. We only want
                # to update the address for the item that was already there so we check
                # to see if this is the second time we've seen the "modified" address.
                if insertion and seen_modified:
                    address_check = item.address >= modified_item.address and target_affected
                # If jump crosses over our modified command, adjust it
                if address_check:
                    item.command.args[0] += size_change
                    
                    # Notify model of change
                    item_index = self.get_index_for_item(item)
                    self.dataChanged.emit(
                        self.createIndex(item_index.row(), 0, item),
                        self.createIndex(item_index.row(), 1, item),
                        [Qt.ItemDataRole.DisplayRole]
                    )
            if item.address == modified_item.address:
                seen_modified = True

    def _recalculate_jump_bytes(self, item: CommandItem) -> None:
        if item.command is None or item.command.command not in EventCommand.conditional_commands:
            return
        total = sum(
            len(d.command) for d in _get_all_commands(item)[1:]
            if d.command is not None
        )
        item.command.args[-1] = total + 1 if total > 0 else 0
        item_index = self.get_index_for_item(item)
        self.dataChanged.emit(
            self.createIndex(item_index.row(), 0, item),
            self.createIndex(item_index.row(), 1, item),
            [Qt.ItemDataRole.DisplayRole]
        )

    def _sync_conditional_to_script(self, item: CommandItem) -> None:
        """Write the tree's recalculated command bytes back to script.data."""
        if self._backend is None or item.command is None or item.address is None:
            return
        script = self._backend.get_script(self._location_id)
        cmd_bytes = item.command.to_bytearray()
        script.data[item.address:item.address + len(cmd_bytes)] = cmd_bytes

    def _recalculate_ancestor_jumps(self, item: CommandItem) -> None:
        current = item.parent
        while current is not None and current != self._root_item:
            if current.command is not None and current.command.command in EventCommand.conditional_commands:
                self._recalculate_jump_bytes(current)
                self._sync_conditional_to_script(current)
            current = current.parent

    def change_location(self, location_id: int):
        self._location_id = location_id
        items = process_script(self._backend.get_script(location_id))
        new_root = CommandItem(name="Root", children=items)
        self.replace_items(new_root)

    def append_function(self, obj_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.append_function(obj_id)
        new_root = CommandItem(name="Root", children=process_script(script))
        self.replace_items(new_root)

    def remove_function(self, obj_id: int, func_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.remove_function(obj_id, func_id)
        new_root = CommandItem(name="Root", children=process_script(script))
        self.replace_items(new_root)

    def break_link(self, obj_id: int, func_id: int) -> None:
        '''Turn a linked function slot into an empty (non-linked) slot.'''
        script = self._backend.get_script(self._location_id)
        script.break_function_link(obj_id, func_id)
        new_root = CommandItem(name="Root", children=process_script(script))
        self.replace_items(new_root)

    def convert_to_link(self, obj_id: int, func_id: int,
                        target_obj_id: int, target_func_id: int) -> None:
        '''Make a function slot a link to another function's bytecode.'''
        script = self._backend.get_script(self._location_id)
        script.set_function_link(obj_id, func_id, target_obj_id, target_func_id)
        new_root = CommandItem(name="Root", children=process_script(script))
        self.replace_items(new_root)

def print_command_tree(model: CommandModel):
    """
    Print a readable representation of all commands in the model.
    
    Args:
        model: The CommandModel to print
        output_file: Optional file path to write the output. If None, prints to console.
    """
    def _format_command(item: CommandItem) -> str:
        """Format a single command item into a readable string"""
        if not item.command:
            return f"{item.name}"
            
        # Get command details
        cmd_id = item.command.command
        args = [f"0x{arg:X}" if isinstance(arg, int) else str(arg) 
               for arg in item.command.args]
        args_str = ", ".join(args)
        
        return f"0x{cmd_id:02X} {item.name} @ 0x{item.address:02X} [{args_str}]"

    def _print_recursive(index: QModelIndex, depth: int, output_lines: list):
        """Recursively print command items with proper indentation"""
        if not index.isValid():
            # Handle root level items
            for row in range(model.rowCount(QModelIndex())):
                child_index = model.index(row, 0, QModelIndex())
                _print_recursive(child_index, depth, output_lines)
            return

        # Get item at this index
        item = index.internalPointer()
        indent = "  " * depth
        line = indent + _format_command(item)
        output_lines.append(line)
        
        # Process children
        for row in range(model.rowCount(index)):
            child_index = model.index(row, 0, index)
            _print_recursive(child_index, depth + 1, output_lines)

    # Generate all lines
    output_lines = []
    _print_recursive(QModelIndex(), 0, output_lines)
    
    # Write output
    for line in output_lines:
        print(line)
    print("\n")

def _get_all_commands(root: CommandItem) -> list[CommandItem]:
    """Get all commands in the tree in depth-first order"""
    commands = []
    def traverse(item: CommandItem):
        commands.append(item)
        for child in item.children:
            traverse(child)
    traverse(root)
    return commands