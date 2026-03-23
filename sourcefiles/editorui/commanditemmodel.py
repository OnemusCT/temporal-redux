from __future__ import annotations
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt, QMimeData
from PyQt6.QtGui import QBrush, QColor, QFont
from jetsoftime.eventcommand import EventCommand
import editorui.commandtotext as c2t
from editorui.commanditem import CommandItem, process_script
from editorui.activitylog import ActivityLog
from gamebackend import GameBackend
import difflib

def _get_all_commands(root: CommandItem) -> list[CommandItem]:
    commands = []
    def traverse(item: CommandItem):
        commands.append(item)
        for child in item.children:
            traverse(child)
    traverse(root)
    return commands

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
        parts = []
        node = item.parent
        while node is not None and node.parent is not None:
            parts.append(node.name)
            node = node.parent
        return " > ".join(reversed(parts))

    def _sync_all_from_backend(self):
        if self._backend is None:
            return
        new_items = process_script(self._backend.get_script(self._location_id))
        new_root = CommandItem(name="Root", children=new_items)
        self._sync_tree(QModelIndex(), self._root_item, new_root)

    def _sync_tree(self, old_parent_index: QModelIndex, old_parent_item: CommandItem, new_parent_item: CommandItem):
        old_list = old_parent_item.children
        new_list = new_parent_item.children
        
        class HashableItem:
            def __init__(self, item: CommandItem):
                self.item = item
            def __hash__(self):
                if self.item.command:
                    return hash(self.item.command.command)
                return hash(self.item.name)
            def __eq__(self, other):
                if self.item.is_section_label and other.item.is_section_label:
                    return self.item.name == other.item.name
                if self.item.is_section_label != other.item.is_section_label: return False
                
                if self.item.is_link and other.item.is_link:
                    return self.item.name == other.item.name
                if self.item.is_link != other.item.is_link: return False
                
                if self.item.command and other.item.command:
                    return self.item.command.command == other.item.command.command
                if self.item.command or other.item.command: return False
                return self.item.name == other.item.name

        sm = difflib.SequenceMatcher(None, [HashableItem(x) for x in old_list], [HashableItem(x) for x in new_list])
        
        for tag, i1, i2, j1, j2 in reversed(sm.get_opcodes()):
            if tag == 'delete':
                self.beginRemoveRows(old_parent_index, i1, i2 - 1)
                del old_list[i1:i2]
                self.endRemoveRows()
            elif tag == 'insert':
                self.beginInsertRows(old_parent_index, i1, i1 + (j2 - j1) - 1)
                for j in range(j1, j2):
                    new_item = new_list[j]
                    new_item.parent = old_parent_item
                    old_list.insert(i1 + (j - j1), new_item)
                self.endInsertRows()
            elif tag == 'replace':
                self.beginRemoveRows(old_parent_index, i1, i2 - 1)
                del old_list[i1:i2]
                self.endRemoveRows()
                self.beginInsertRows(old_parent_index, i1, i1 + (j2 - j1) - 1)
                for j in range(j1, j2):
                    new_item = new_list[j]
                    new_item.parent = old_parent_item
                    old_list.insert(i1 + (j - j1), new_item)
                self.endInsertRows()
            elif tag == 'equal':
                for k in range(i2 - i1):
                    old_child = old_list[i1 + k]
                    new_child = new_list[j1 + k]
                    
                    data_changed = False
                    if old_child.address != new_child.address:
                        old_child.address = new_child.address
                        data_changed = True
                    if old_child.name != new_child.name:
                        old_child.name = new_child.name
                        data_changed = True
                    if old_child.command != new_child.command:
                        old_child.command = new_child.command
                        data_changed = True
                        
                    if data_changed:
                        idx = self.index(i1 + k, 0, old_parent_index)
                        self.dataChanged.emit(idx, self.index(i1 + k, 1, old_parent_index), [Qt.ItemDataRole.DisplayRole])
                    
                    if old_child.children or new_child.children:
                        self._sync_tree(self.index(i1 + k, 0, old_parent_index), old_child, new_child)

    def _get_func_node(self, item: CommandItem) -> CommandItem | None:
        node = item
        while node is not None:
            if hasattr(node, 'func_id'):
                return node
            node = node.parent
        return None

    def _patch_ancestor_jumps(self, parent_item: CommandItem, size_change: int):
        if not self._backend: return
        script = self._backend.get_script(self._location_id)
        node = parent_item
        while node is not None and node != self._root_item:
            if node.command and node.command.command in EventCommand.conditional_commands:
                old_jump = sum(len(c.command) for c in _get_all_commands(node)[1:] if c.command)
                expected_jump = max(0, old_jump + size_change) + 1
                
                node_addr = node.address
                from jetsoftime.eventcommand import get_command
                cmd = get_command(script.data, node_addr, script.platform)
                arg_offset = len(cmd) - cmd.arg_lens[-1]
                script.data[node_addr + arg_offset] = expected_jump
            node = node.parent

    def update_command(self, item: CommandItem, new_command: EventCommand):
        if self._log is not None:
            self._log.log_command_update(
                self._location_id, item.address,
                item.command, new_command,
                self._item_context(item),
            )
        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            script.insert_commands(new_command.to_bytearray(), item.address)
            script.delete_commands(item.address + len(new_command), 1)
            
        size_change = len(new_command) - (len(item.command) if item.command else 0)
        if size_change != 0 and item.parent:
            self._patch_ancestor_jumps(item.parent, size_change)
            
        self._sync_all_from_backend()

    def insert_command(self, parent_index: QModelIndex, position: int, command: EventCommand, address: int) -> bool:
        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            script.insert_commands(command.to_bytearray(), address)
            
        parent_item = self._root_item if not parent_index.isValid() else parent_index.internalPointer()
        if self._log is not None and not self._suppress_log:
            _ctx_item = CommandItem("", command, address)
            _ctx_item.parent = parent_item
            self._log.log_command_insert(
                self._location_id, address, command, self._item_context(_ctx_item)
            )
            
        self._patch_ancestor_jumps(parent_item, len(command))
            
        self._sync_all_from_backend()
        return True

    def delete_command(self, index: QModelIndex) -> bool:
        if not index.isValid(): return False
        item = index.internalPointer()
        if item.is_section_label: return False
        parent_item = item.parent
        if parent_item is None: return False

        if self._log is not None and not self._suppress_log and item.command is not None:
            self._log.log_command_delete(
                self._location_id, item.address, item.command, self._item_context(item)
            )

        if item.command is None and parent_item == self._root_item:
            obj_id = index.row()
            if self._backend is not None:
                script = self._backend.get_script(self._location_id)
                script.delete_object(obj_id)
            self._sync_all_from_backend()
            return True

        if self._backend is not None:
            script = self._backend.get_script(self._location_id)
            script.delete_commands(item.address)

        size_change = -len(item.command) if item.command else 0
        self._patch_ancestor_jumps(parent_item, size_change)

        self._sync_all_from_backend()
        return True

    def _deep_copy_item(self, item: CommandItem) -> CommandItem:
        if item.command:
            new_command = item.command.copy()
        else:
            new_command = None
        new_item = CommandItem(name=item.name, command=new_command, address=item.address)
        for child in item.children:
            child_copy = self._deep_copy_item(child)
            child_copy.parent = new_item
            new_item.children.append(child_copy)
        return new_item

    def copy_items(self, indexes: list[QModelIndex]) -> list[tuple[CommandItem, int]]:
        if not indexes: return []
        col0 = [idx for idx in indexes if idx.column() == 0]
        selected_items = {idx.internalPointer() for idx in col0}
        root_indexes = [idx for idx in col0 if idx.internalPointer().parent not in selected_items]
        if not root_indexes: return []
        addrs = [idx.internalPointer().address for idx in root_indexes if idx.internalPointer().address is not None]
        base_addr = min(addrs) if addrs else 0
        copied_items = []
        for index in root_indexes:
            item = index.internalPointer()
            copied_item = self._deep_copy_item(item)
            addr_offset = (item.address - base_addr) if item.address is not None else 0
            copied_items.append((copied_item, addr_offset))
        return copied_items

    def cut_items(self, indexes: list[QModelIndex]) -> list[tuple[CommandItem, int]]:
        copied_items = self.copy_items(indexes)
        col0_indexes = [idx for idx in indexes if idx.column() == 0]
        
        def sort_key(idx):
            addr = idx.internalPointer().address
            return addr if addr is not None else float('inf')
            
        sorted_indexes = sorted(col0_indexes, key=sort_key, reverse=True)
        script = self._backend.get_script(self._location_id) if self._backend else None
        
        for index in sorted_indexes:
            item = index.internalPointer()
            if item.command is None and item.parent == self._root_item:
                script.delete_object(index.row()) if script else None
            elif script and item.command:
                script.delete_commands(item.address)
                
        self._sync_all_from_backend()
        return copied_items

    def _extract_bytes(self, item: CommandItem) -> bytearray:
        b = bytearray()
        if item.command:
            b.extend(item.command.to_bytearray())
        for child in item.children:
            b.extend(self._extract_bytes(child))
        return b

    def paste_items(self, items: list[tuple[CommandItem, int]], target_index: QModelIndex):
        if not items: return
        target_item = target_index.internalPointer() if target_index.isValid() else self._root_item

        if target_item.command and target_item.command.command in EventCommand.conditional_commands:
            target_parent = target_item
            insert_address = target_item.address + len(target_item.command)
        elif target_item.command is None:
            target_parent = target_item
            insert_address = target_item.children[0].address if target_item.children else target_item.address
        else:
            target_parent = target_item.parent if target_item.parent else self._root_item
            # If the target is the last child of a non-conditional parent (e.g. the
            # Return at the end of a function), inserting after it would overflow into
            # the next function's address space.  Insert before it instead.
            parent_is_noncond = target_parent.command is None
            is_last_child = bool(target_parent.children) and target_parent.children[-1] == target_item
            if parent_is_noncond and is_last_child:
                insert_address = target_item.address
            else:
                insert_address = target_item.address + len(target_item.command)
            
        script = self._backend.get_script(self._location_id) if self._backend else None
        if script:
            current_address = insert_address
            total_inserted = 0
            for item, offset in items:
                bytes_to_insert = self._extract_bytes(item)
                script.insert_commands(bytes_to_insert, current_address)
                current_address += len(bytes_to_insert)
                total_inserted += len(bytes_to_insert)
                
            self._patch_ancestor_jumps(target_parent, total_inserted)

        self._sync_all_from_backend()

    def get_all_items_after(self, start_item: CommandItem) -> list[CommandItem]:
        items = []
        found_start = False
        def traverse(item: CommandItem):
            nonlocal found_start, items
            if item == start_item:
                found_start = True
                return
            if found_start:
                items.append(item)
            for child in item.children:
                traverse(child)
        def traverse_from_root():
            nonlocal found_start, items
            for root_child in self._root_item.children:
                if found_start:
                    items.append(root_child)
                    for child in root_child.children:
                        traverse(child)
                else:
                    if root_child == start_item:
                        found_start = True
                        continue
                    traverse(root_child)
        traverse_from_root()
        return items

    def _collect_all_children(self, item: CommandItem, items: list[CommandItem]):
        for child in item.children:
            items.append(child)
            self._collect_all_children(child, items)

    def get_index_for_item(self, item: CommandItem) -> QModelIndex:
        if item == self._root_item or item is None:
            return QModelIndex()
        if item.parent == self._root_item:
            try:
                row = self._root_item.children.index(item)
                return self.createIndex(row, 0, item)
            except ValueError:
                return QModelIndex()
        else:
            parent = item.parent
            try:
                row = parent.children.index(item)
                parent_index = self.get_index_for_item(parent)
                return self.index(row, 0, parent_index)
            except ValueError:
                return QModelIndex()

    def rowCount(self, parent: QModelIndex) -> int:
        if parent.isValid() and parent.column() != 0: return 0
        if not parent.isValid(): return len(self._root_item.children)
        parent_item: CommandItem = parent.internalPointer()
        return len(parent_item.children)

    def columnCount(self, parent: QModelIndex) -> int: return 2

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        if not index.isValid(): return None
        item: CommandItem = index.internalPointer()
        if item.is_section_label:
            if role == Qt.ItemDataRole.DisplayRole: return item.name if index.column() == 1 else ""
            if role == Qt.ItemDataRole.ForegroundRole: return QBrush(QColor("#888888"))
            if role == Qt.ItemDataRole.FontRole:
                font = QFont(); font.setItalic(True); return font
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 1: return item.name
            elif index.column() == 0: return "0x{:02X}".format(item.address) if item.address is not None else ""
        if role == Qt.ItemDataRole.ForegroundRole and item.is_link: return QBrush(QColor("#888888"))
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
        if not index.isValid(): return Qt.ItemFlag.NoItemFlags
        if index.internalPointer().is_section_label: return Qt.ItemFlag.ItemIsEnabled
        default_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        return default_flags

    def index(self, row: int, column: int, parent: QModelIndex) -> QModelIndex:
        if not self.hasIndex(row, column, parent): return QModelIndex()
        parent_item = self._root_item if not parent.isValid() else parent.internalPointer()
        child_item = parent_item.get_child(row)
        if child_item: return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid(): return QModelIndex()
        child_item: CommandItem = index.internalPointer()
        parent_item = child_item.parent
        if parent_item is None or parent_item == self._root_item: return QModelIndex()
        row = parent_item.parent.children.index(parent_item) if parent_item.parent is not None else 0
        return self.createIndex(row, 0, parent_item)

    def replace_items(self, new_root_item: CommandItem):
        self.beginResetModel()
        def setup_parents(item: CommandItem, parent: CommandItem):
            item.parent = parent
            for child in item.children: setup_parents(child, item)
        for child in new_root_item.children: setup_parents(child, new_root_item)
        self._root_item = new_root_item
        self.endResetModel()

    def supportedDropActions(self) -> Qt.DropAction: return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]: return ['application/x-commanditem']

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        mime_data = QMimeData()
        selected_items = []
        for index in indexes:
            if index.column() == 0:
                selected_items.append((index.internalPointer(), index))
        mime_data.setData('application/x-commanditem', bytes(str(id(selected_items)), 'utf-8'))
        self._drag_items = selected_items
        return mime_data

    def canDropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not data.hasFormat('application/x-commanditem'): return False
        if not hasattr(self, '_drag_items'): return False
        target_item = parent.internalPointer() if parent.isValid() else self._root_item
        if getattr(target_item, 'is_section_label', False): return False
        for (item, _) in self._drag_items:
            current = target_item
            while current is not None:
                if current == item: return False
                current = current.parent
        return True

    def dropMimeData(self, data: QMimeData, action: Qt.DropAction, row: int, column: int, parent: QModelIndex) -> bool:
        if not self.canDropMimeData(data, action, row, column, parent): return False
        if action == Qt.DropAction.IgnoreAction: return True

        target_item = parent.internalPointer() if parent.isValid() else self._root_item
        drag_item_set = {item for item, _ in self._drag_items}
        root_drag = [(item, idx) for item, idx in self._drag_items if item.parent and item.parent not in drag_item_set]

        script = self._backend.get_script(self._location_id) if self._backend else None
        if not script: return False

        deep_copies = [self._deep_copy_item(item) for item, _ in root_drag]
        
        for item, _ in sorted(root_drag, key=lambda x: x[0].address or 0, reverse=True):
            deleted_size = sum(len(c.command) for c in _get_all_commands(item) if c.command)
            script.delete_commands_range(item.address, item.address + deleted_size)
            self._patch_ancestor_jumps(item.parent, -deleted_size)
            
        target_addr = target_item.address if target_item.address is not None else 0
        for item, _ in root_drag:
            item_size = sum(len(c.command) for c in _get_all_commands(item) if c.command)
            if item.address and item.address < target_addr: target_addr -= item_size
            
        target_parent = target_item.parent
        if target_item.command and target_item.command.command in EventCommand.conditional_commands:
            target_parent = target_item
            insert_address = target_addr + len(target_item.command)
        elif target_item.command is None:
            target_parent = target_item
            insert_address = target_item.children[0].address if target_item.children else target_addr
        else:
            insert_address = target_addr + len(target_item.command) if target_item.command else target_addr

        current_address = insert_address
        total_inserted = 0
        for deep_copy in deep_copies:
            bytes_to_insert = self._extract_bytes(deep_copy)
            script.insert_commands(bytes_to_insert, current_address)
            current_address += len(bytes_to_insert)
            total_inserted += len(bytes_to_insert)
            
        self._patch_ancestor_jumps(target_parent, total_inserted)

        self._sync_all_from_backend()
        return True

    def change_location(self, location_id: int):
        self._location_id = location_id
        items = process_script(self._backend.get_script(location_id))
        new_root = CommandItem(name="Root", children=items)
        self.replace_items(new_root)

    def append_function(self, obj_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.append_function(obj_id)
        self._sync_all_from_backend()

    def remove_function(self, obj_id: int, func_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.remove_function(obj_id, func_id)
        self._sync_all_from_backend()

    def break_link(self, obj_id: int, func_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.break_function_link(obj_id, func_id)
        self._sync_all_from_backend()

    def convert_to_link(self, obj_id: int, func_id: int, target_obj_id: int, target_func_id: int) -> None:
        script = self._backend.get_script(self._location_id)
        script.set_function_link(obj_id, func_id, target_obj_id, target_func_id)
        self._sync_all_from_backend()

def print_command_tree(model: CommandModel):
    def _format_command(item: CommandItem) -> str:
        if not item.command: return f"{item.name}"
        args_str = ", ".join([f"0x{arg:X}" if isinstance(arg, int) else str(arg) for arg in item.command.args])
        return f"0x{item.command.command:02X} {item.name} @ 0x{item.address:02X} [{args_str}]"
    def _print_recursive(index: QModelIndex, depth: int, output_lines: list):
        if not index.isValid():
            for row in range(model.rowCount(QModelIndex())): _print_recursive(model.index(row, 0, QModelIndex()), depth, output_lines)
            return
        item = index.internalPointer()
        output_lines.append("  " * depth + _format_command(item))
        for row in range(model.rowCount(index)): _print_recursive(model.index(row, 0, index), depth + 1, output_lines)
    output_lines = []
    _print_recursive(QModelIndex(), 0, output_lines)
    for line in output_lines: print(line)
    print("\n")