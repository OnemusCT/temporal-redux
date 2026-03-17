from __future__ import annotations
import sys
from pathlib import Path
# Ensure sourcefiles/ is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Optional
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QComboBox, QCompleter, QPushButton, QLabel, QGridLayout,
    QVBoxLayout, QHBoxLayout, QFileDialog, QDialog, QLineEdit, QMenu,
    QListWidget, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QModelIndex, QPoint, pyqtSlot
from PyQt6.QtGui import QShortcut, QKeySequence

from gamebackend import GameBackend, SnesBackend
from pcbackend import PcBackend
from jetsoftime.eventcommand import EventCommand, event_commands
from editorui.commandgroups import event_command_groupings, EventCommandType, EventCommandSubtype
import editorui.commandmenus as cm
from editorui.commanditemmodel import CommandModel
from editorui.commandtreeview import CommandTreeView
from editorui.commanditem import CommandItem, process_script
from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.UnassignedMenu import UnassignedMenu


class _LinkTargetDialog(QDialog):
    '''Dialog for selecting a link target function from the current script.'''

    def __init__(self, script, source_obj_id: int, source_func_id: int, parent=None):
        super().__init__(parent)
        from editorui.commanditem import _get_function_name
        self.setWindowTitle("Select Link Target")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Link to which function?"))

        self._list = QListWidget()
        self._targets: list[tuple[int, int]] = []

        for obj_id in range(script.num_objects):
            for func_id in range(16):
                if (obj_id, func_id) == (source_obj_id, source_func_id):
                    continue
                if not script._function_is_real(obj_id, func_id):
                    continue
                label = f"Obj {obj_id:02X} {_get_function_name(func_id)}"
                self._list.addItem(label)
                self._targets.append((obj_id, func_id))

        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_target(self) -> tuple[int, int] | None:
        row = self._list.currentRow()
        if row < 0 or row >= len(self._targets):
            return None
        return self._targets[row]


def _open_file_or_directory(parent=None) -> Optional[Path]:
    """
    Show a small dialog letting the user pick either a file (SNES ROM /
    resources.bin) or an extracted PC data directory.  Returns the chosen
    Path, or None if the dialog was canceled.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle("Open")
    dialog.setMinimumWidth(340)
    result: Optional[Path] = None

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Open a Chrono Trigger file or extracted PC data directory:"))

    btn_file = QPushButton("Open File  (ROM / resources.bin)…")
    btn_dir  = QPushButton("Open Directory  (extracted PC data)…")
    btn_cancel = QPushButton("Cancel")

    layout.addWidget(btn_file)
    layout.addWidget(btn_dir)
    layout.addWidget(btn_cancel)

    def pick_file():
        nonlocal result
        filename, _ = QFileDialog.getOpenFileName(
            dialog,
            "Open File",
            "",
            "Chrono Trigger Files (*.smc *.sfc *.bin)"
            ";;SNES ROM Files (*.smc *.sfc)"
            ";;PC Archive (*.bin)"
            ";;All Files (*.*)",
        )
        if filename:
            result = Path(filename)
            dialog.accept()

    def pick_dir():
        nonlocal result
        directory = QFileDialog.getExistingDirectory(dialog, "Open PC Data Directory")
        if directory:
            result = Path(directory)
            dialog.accept()

    btn_file.clicked.connect(pick_file)
    btn_dir.clicked.connect(pick_dir)
    btn_cancel.clicked.connect(dialog.reject)

    dialog.exec()
    return result


def detect_backend(path: Path) -> GameBackend:
    """
    Detect the correct backend for a given path.

    - .smc / .sfc  -> SnesBackend
    - .bin         -> PcBackend (resources.bin archive)
    - directory    -> PcBackend (extracted PC data directory)
    """
    if path.is_dir():
        return PcBackend(path)
    suffix = path.suffix.lower()
    if suffix in ('.smc', '.sfc'):
        return SnesBackend.from_path(path)
    if suffix == '.bin':
        return PcBackend(path)
    raise ValueError(f"Unrecognised file type: {path}")


@dataclass
class ViewerState:
    """Holds the current state of the viewer"""
    current_command: Optional[EventCommand] = None
    current_address: Optional[int] = None
    backend: Optional[GameBackend] = None
    selected_items: list[CommandItem] = None
    file: Path = None

    def __post_init__(self):
        self.selected_items = []

class EventViewer(QMainWindow):
    def __init__(self, rom_path: Path):
        super().__init__()
        backend = detect_backend(rom_path)

        self.state = ViewerState(
            file=rom_path,
            backend=backend,
        )
        self.setWindowFlags(Qt.WindowType.Window)
        self.setup_ui()
        self.on_location_changed(0)
        self._clipboard_data = None
        self._differ_window = None

    def load_state(self, rom_path: Path):
        try:
            backend = detect_backend(rom_path)
        except ValueError as e:
            print(f"Error loading file: {e}")
            return

        self.state = ViewerState(
            file=rom_path,
            backend=backend,
        )
        self.model.set_backend(backend)
        self._populate_location_selector()
        self.on_location_changed(0)

    def create_menu_bar(self):
        """Create the main menu bar with File and Edit menus"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        open_action = file_menu.addAction("Open…")
        open_action.triggered.connect(self.on_open)

        save_action = file_menu.addAction("Save")
        save_action.triggered.connect(self.on_save)

        save_as_action = file_menu.addAction("Save As")
        save_as_action.triggered.connect(self.on_save_as)

        edit_menu = menubar.addMenu("Edit")

        cut_action = edit_menu.addAction("Cut")
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(self.on_cut)

        copy_action = edit_menu.addAction("Copy")
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self.on_copy)

        paste_action = edit_menu.addAction("Paste")
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(self.on_paste)

        tools_menu = menubar.addMenu("Tools")

        differ_action = tools_menu.addAction("Event Differ…")
        differ_action.triggered.connect(self.on_open_differ)

    def on_open(self):
        """Handle Open menu action (SNES ROM, resources.bin, or extracted directory)"""
        path = _open_file_or_directory(self)
        if path:
            self.load_state(path)

    def on_open_differ(self):
        """Open the Event Differ window."""
        from editorui.diffwindow import DiffWindow

        def open_callback():
            path = _open_file_or_directory(self._differ_window)
            if path is None:
                return None
            try:
                backend = detect_backend(path)
            except ValueError as e:
                print(f"Error loading file: {e}")
                return None
            return backend, path

        if self._differ_window is None:
            self._differ_window = DiffWindow(open_callback, self)
            self._differ_window.load_left(self.state.backend, self.state.file)
        self._differ_window.show()
        self._differ_window.raise_()
        self._differ_window.activateWindow()

    def on_save(self):
        """Handle Save menu action"""
        if self.state.backend.is_read_only:
            print("Save not supported for this file type.")
            return
        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")
            print("Save cancelled")
            return
        location_id = self.location_selector.currentData()
        self.state.backend.write_script(location_id)
        self.model.change_location(location_id)
        self.tree.expandAll()
        self.state.backend.save_to_file(self.state.file)

    def on_save_as(self):
        """Handle Save As menu action"""
        if self.state.backend.is_read_only:
            print("Save not supported for this file type.")
            return
        if self.state.backend.platform == 'pc':
            dest = QFileDialog.getExistingDirectory(self, "Save As (choose destination directory)")
        else:
            dest, _ = QFileDialog.getSaveFileName(
                self,
                "Save As",
                "",
                "SNES ROM Files (*.smc *.sfc);;All Files (*.*)"
            )
        if dest:
            is_match, discrepancies = self.compare_tree_with_script()
            if not is_match:
                print("Tree discrepancies found:")
                for d in discrepancies:
                    print(f"- {d}")
                print("Save cancelled")
                return
            location_id = self.location_selector.currentData()
            self.state.backend.write_script(location_id)
            self.model.change_location(location_id)
            self.tree.expandAll()
            self.state.backend.save_to_file(Path(dest))

    def on_copy(self):
        """Handle Copy menu action"""
        selected_indexes = self.tree.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
            
        self._clipboard_data = self.model.copy_items(selected_indexes)
        
        # Validate tree state after copy
        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")

    def on_cut(self):
        """Handle Cut menu action"""
        selected_indexes = self.tree.selectionModel().selectedIndexes()
        if not selected_indexes:
            return
            
        self._clipboard_data = self.model.cut_items(selected_indexes)
        
        # Validate tree state after cut
        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")

    def on_paste(self):
        """Handle Paste menu action"""
        if not self._clipboard_data:
            return
            
        # Get current selection as paste target
        current_index = self.tree.currentIndex()
        if not current_index.isValid():
            return
            
        self.model.paste_items(self._clipboard_data, current_index)
        
        # Validate tree state after paste
        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")

    def setup_ui(self):
        """Initialize the UI components"""
        self.setWindowTitle("Chrono Trigger Event Editor")
        self.create_menu_bar()

        # Main layout
        central_widget = QWidget()
        self.main_layout = QGridLayout(central_widget)
        self.setCentralWidget(central_widget)
        
        # Create UI components
        self.create_location_selector()
        self.create_command_tree() 
        self.create_command_editor()
        
        # Layout setup
        self.main_layout.addWidget(self.location_selector, 0, 0, 1, 2)
        tree_container = self._create_tree_with_search()
        self.main_layout.addWidget(tree_container, 1, 1)
        self.main_layout.addWidget(self.command_label, 2, 0, 1, 2)
        
        command_widget = QWidget()
        command_widget.setLayout(self.command_layout)
        self.main_layout.addWidget(command_widget, 1, 0, 1, 1, Qt.AlignmentFlag.AlignTop)
        
        # Layout configuration
        self.main_layout.setColumnStretch(0, 0)
        self.main_layout.setColumnStretch(1, 2)
        self.main_layout.setColumnMinimumWidth(1, 300)
    
    def setup_script_buttons(self):
        """Create New Object and New Command buttons."""
        layout = QHBoxLayout()

        self.new_object_button = QPushButton("New Object")
        self.new_object_button.clicked.connect(self.on_new_object_pressed)

        self.new_command_button = QPushButton("New Command")
        self.new_command_button.clicked.connect(self.on_new_command_pressed)
        self.new_command_button.setEnabled(False)

        layout.addWidget(self.new_object_button)
        layout.addWidget(self.new_command_button)
        return layout

    def on_new_object_pressed(self):
        """Append a new empty object to the current script."""
        loc_id = self.location_selector.currentData()
        script = self.state.backend.get_script(loc_id)
        if script.num_objects >= 0x40:
            self.command_label.setText("Error: cannot have more than 0x40 objects")
            return
        script.append_empty_object()
        self.model.change_location(loc_id)
        self.tree.expandAll()
        last_row = self.model.rowCount(QModelIndex()) - 1
        if last_row >= 0:
            self.tree.setCurrentIndex(self.model.index(last_row, 0, QModelIndex()))

    def on_new_command_pressed(self):
        """Insert a Return command into the selected function or after the selected command."""
        selected_rows = set(
            index for index in self.tree.selectionModel().selectedIndexes()
            if index.column() == 0
        )
        if len(selected_rows) != 1:
            return

        current_index = next(iter(selected_rows))
        current_item = current_index.internalPointer()

        if current_item.command is not None:
            self.on_insert_pressed()
            return

        func_item = current_item
        object_item = func_item.parent
        if object_item is None or object_item.parent is None:
            return

        obj_id = self.model._root_item.children.index(object_item)
        func_id = object_item.children.index(func_item)

        loc_id = self.location_selector.currentData()
        script = self.state.backend.get_script(loc_id)
        address = script.get_function_start(obj_id, func_id)

        return_cmd = event_commands[0].copy()
        self.model.insert_command(current_index, 0, return_cmd, address)

    def setup_command_buttons(self):
        """Create and configure the command manipulation buttons"""
        button_layout = QHBoxLayout()
        
        self.update_button = QPushButton(text="Update")
        self.update_button.clicked.connect(self.on_update_command)
        
        self.delete_button = QPushButton(text="Delete")
        self.delete_button.clicked.connect(self.on_delete_pressed)
        
        self.insert_button = QPushButton(text="Insert")
        self.insert_button.clicked.connect(self.on_insert_pressed)
        
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.insert_button)
        
        # Set initial button states
        self.delete_button.setEnabled(False)
        self.update_button.setEnabled(False)
        self.insert_button.setEnabled(False)
        
        return button_layout

    def on_delete_pressed(self):
        """Delete all currently selected commands"""
        selected_rows = [index for index in self.tree.selectionModel().selectedIndexes()
                         if index.column() == 0]
        if not selected_rows:
            return

        from editorui.commanditemmodel import _delete_batch
        _delete_batch(self.model, selected_rows)

        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")
        else:
            print("No discrepancies found")
            
    def on_insert_pressed(self):
        """Insert a new command after the currently selected one"""
        # Get unique rows by filtering for column 0
        selected_rows = set(index for index in self.tree.selectionModel().selectedIndexes() 
                          if index.column() == 0)
        if not selected_rows:
            return
            
        # Only allow insert when a single item is selected
        if len(selected_rows) > 1:
            return
            
        current_index = next(iter(selected_rows))
        if not current_index.isValid():
            return
            
        # Get current item's info
        current_item = current_index.internalPointer()
        parent_item = current_item.parent
        
        if parent_item is None:
            return
            
        # Get insert position (after current item)
        insert_pos = parent_item.children.index(current_item) + 1
        
        # Create default command (Return - 0x00)
        default_command = event_commands[0].copy()
        
        # Calculate address for new command
        current_addr = current_item.address  if current_item.address else 0
        new_addr = current_addr + len(current_item.command)
        
        # Get parent index for model
        parent_index = self.model.parent(current_index)
        
        # Insert the new command
        self.model.insert_command(parent_index, insert_pos, default_command, new_addr)

        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            print("Tree discrepancies found:")
            for d in discrepancies:
                print(f"- {d}")

    def _create_tree_with_search(self) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(2)

        search_row = QHBoxLayout()
        search_row.setSpacing(4)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search commands or addresses…")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.returnPressed.connect(self._on_search_next)

        self.search_label = QLabel("0 / 0")
        self.search_label.setMinimumWidth(50)

        btn_prev = QPushButton("↑")
        btn_prev.setFixedWidth(28)
        btn_prev.setToolTip("Previous match  (Shift+Enter)")
        btn_prev.clicked.connect(self._on_search_prev)

        btn_next = QPushButton("↓")
        btn_next.setFixedWidth(28)
        btn_next.setToolTip("Next match  (Enter)")
        btn_next.clicked.connect(self._on_search_next)

        search_row.addWidget(self.search_box)
        search_row.addWidget(self.search_label)
        search_row.addWidget(btn_prev)
        search_row.addWidget(btn_next)

        QShortcut(QKeySequence("Ctrl+F"), container).activated.connect(self.search_box.setFocus)
        QShortcut(QKeySequence("Shift+Return"), container).activated.connect(self._on_search_prev)

        vbox.addLayout(search_row)
        vbox.addWidget(self.tree)
        return container

    def _collect_search_matches(self, query: str) -> list[QModelIndex]:
        if not query:
            return []
        q = query.lower()
        matches: list[QModelIndex] = []

        def walk(parent: QModelIndex) -> None:
            for row in range(self.model.rowCount(parent)):
                idx = self.model.index(row, 0, parent)
                item = idx.internalPointer()
                if item and item.command is not None:
                    hit = (item.address is not None and q in f"0x{item.address:02x}")
                    if not hit:
                        hit = q in (item.name or '').lower()
                    if hit:
                        matches.append(idx)
                walk(idx)

        walk(QModelIndex())
        return matches

    def _navigate_to_match(self, idx: QModelIndex) -> None:
        ancestors: list[QModelIndex] = []
        p = idx.parent()
        while p.isValid():
            ancestors.append(p)
            p = p.parent()
        for anc in reversed(ancestors):
            self.tree.expand(anc)
        self.tree.setCurrentIndex(idx)
        self.tree.scrollTo(idx)

    def _on_search_changed(self, text: str) -> None:
        self._search_results = self._collect_search_matches(text)
        self._search_index = 0
        total = len(self._search_results)
        if total:
            self.search_label.setText(f"1 / {total}")
            self._navigate_to_match(self._search_results[0])
        else:
            self.search_label.setText("0 / 0")

    def _on_search_next(self) -> None:
        if not self._search_results:
            return
        self._search_index = (self._search_index + 1) % len(self._search_results)
        self.search_label.setText(f"{self._search_index + 1} / {len(self._search_results)}")
        self._navigate_to_match(self._search_results[self._search_index])

    def _on_search_prev(self) -> None:
        if not self._search_results:
            return
        self._search_index = (self._search_index - 1) % len(self._search_results)
        self.search_label.setText(f"{self._search_index + 1} / {len(self._search_results)}")
        self._navigate_to_match(self._search_results[self._search_index])

    def create_location_selector(self):
        """Create the location selection dropdown with substring search."""
        self.location_selector = QComboBox()
        self.location_selector.setEditable(True)
        self.location_selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._populate_location_selector()
        self.location_selector.currentIndexChanged.connect(self.on_location_changed)

    def _populate_location_selector(self):
        """Populate the location selector from the current backend's location list."""
        self.location_selector.blockSignals(True)
        self.location_selector.clear()
        for loc_id, name in self.state.backend.get_location_list():
            self.location_selector.addItem(name, loc_id)
        self.location_selector.blockSignals(False)

        names = [self.location_selector.itemText(i) for i in range(self.location_selector.count())]
        completer = QCompleter(names, self.location_selector)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.location_selector.setCompleter(None)
        self.location_selector.lineEdit().setCompleter(completer)
        completer.activated[str].connect(self._on_location_completion_selected)

    def _on_location_completion_selected(self, text: str) -> None:
        """Navigate to the location chosen via the completer popup."""
        index = self.location_selector.findText(text)
        if index >= 0:
            self.location_selector.setCurrentIndex(index)

    def create_command_tree(self):
        """Create the command tree view"""
        self.tree = CommandTreeView()
        self.tree.setMinimumSize(750, 750)
        self.tree.setColumnWidth(0, 70)
        self.tree.setTreePosition(1)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)

        self._search_results: list[QModelIndex] = []
        self._search_index: int = 0

        root = CommandItem("Root")
        self.model = CommandModel(root_item=root, backend=self.state.backend, location_id=0x10F)
        self.tree.setModel(self.model)
        self.tree.selectionModel().selectionChanged.connect(self.on_command_selected)

    def create_command_editor(self):
        """Create the command editing panel"""
        self.command_layout = QVBoxLayout()
        
        # Command group selector
        self.command_group_selector = QComboBox()
        self.command_subgroup_selector = QComboBox()
        
        for cmd_type in EventCommandType:
            self.command_group_selector.addItem(cmd_type.value, cmd_type)
            
        self.command_group_selector.currentIndexChanged.connect(self.on_command_group_changed)
        
        # Command menu
        self.command_menu = UnassignedMenu()
        self.command_menu_widget = self.command_menu.command_widget()
        
        # New Object / New Command buttons (above the type dropdowns)
        script_buttons = self.setup_script_buttons()

        # Update/Insert/Delete buttons
        command_buttons = self.setup_command_buttons()

        # Command label
        self.command_label = QLabel()

        # Add widgets to layout
        self.command_layout.addLayout(script_buttons)
        self.command_layout.addWidget(self.command_group_selector)
        self.command_layout.addWidget(self.command_subgroup_selector)
        self.command_layout.addWidget(self.command_menu_widget)
        self.command_layout.addLayout(command_buttons)

    @pyqtSlot("QItemSelection", "QItemSelection")
    def on_command_selected(self, selected, deselected):
        """Handle command selection changes"""
        # Get unique rows by filtering for column 0
        selected_rows = set(index for index in self.tree.selectionModel().selectedIndexes() 
                          if index.column() == 0)
        
        # Clear the state's selected items
        self.state.selected_items = []
        
        # Update button states based on selection
        has_selection = len(selected_rows) > 0
        self.delete_button.setEnabled(has_selection)
        
        # If no selection, disable all buttons and clear display
        if not has_selection:
            self.update_button.setEnabled(False)
            self.insert_button.setEnabled(False)
            self.new_command_button.setEnabled(False)
            self.command_label.setText("")
            return

        # Multiple selection handling
        if len(selected_rows) > 1:
            # Disable update and insert for multiple selection
            self.update_button.setEnabled(False)
            self.insert_button.setEnabled(False)
            self.new_command_button.setEnabled(False)
            
            # Use unassigned menu for multiple selection
            self.update_command_menu(cm.menu_mapping[EventCommandType.UNASSIGNED][EventCommandSubtype.UNASSIGNED])
            
            # Update command info display for multiple selection
            selected_commands = []
            for index in selected_rows:
                item = index.internalPointer()
                if item.command:
                    selected_commands.append(str(item.command))
                    self.state.selected_items.append(item)
                    
            self.command_label.setText(f"Multiple commands selected:\n" + "\n".join(selected_commands))
            return
            
        # Single selection handling
        item = next(iter(selected_rows)).internalPointer()
        if not item.command:
            # Enable New Command for function nodes (depth 2: parent=object, grandparent=root)
            is_function_node = (item.parent is not None and item.parent.parent is not None)
            self.new_command_button.setEnabled(is_function_node)
            return

        self.state.selected_items = [item]
        
        # Update command info display
        command_info = [
            str(item.command),
            item.command.desc,
            str(item.command.args),
            str(item.command.arg_descs)
        ]
        self.command_label.setText('\n'.join(command_info))
        
        # Enable buttons for single command selection
        self.update_button.setEnabled(True)
        self.insert_button.setEnabled(True)
        self.new_command_button.setEnabled(True)
        
        # Update command type selectors
        if item.command.command_type:
            type_index = self.command_group_selector.findText(item.command.command_type.value)
            if type_index != -1:
                self.command_group_selector.setCurrentIndex(type_index)
                self.command_subgroup_selector.clear()
                
                for subtype in event_command_groupings[item.command.command_type]:
                    self.command_subgroup_selector.addItem(subtype.value)
                    
                subtype_index = self.command_subgroup_selector.findText(
                    item.command.command_subtype.value
                )
                if subtype_index != -1:
                    self.command_subgroup_selector.setCurrentIndex(subtype_index)

                # Update command menu
                command_type = item.command.command_type
                command_subtype = item.command.command_subtype
                menu = (cm.menu_mapping.get(command_type, {})
                       .get(command_subtype, cm.menu_mapping[EventCommandType.UNASSIGNED][EventCommandSubtype.UNASSIGNED]))
                
                self.update_command_menu(menu)
                self.command_menu.set_platform(self.state.backend.platform)
                self.command_menu.apply_arguments(item.command.command, item.command.args)

                if item.command.args:
                    string_idx = item.command.args[0]
                    loc_id = self.location_selector.currentData()
                    event = self.state.backend.get_script(loc_id)
                    if string_idx < len(event.strings):
                        from jetsoftime.ctstrings import CTString
                        text = CTString.ct_bytes_to_ascii(bytes(event.strings[string_idx]))
                        self.command_menu.apply_string(text)


    @pyqtSlot(int)
    def on_location_changed(self, index: int):
        """Handle location selection changes"""
        location_id = self.location_selector.itemData(index)
        if location_id is None:
            return
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self._search_results = []
        self._search_index = 0
        self.search_label.setText("0 / 0")
        self.model.change_location(location_id)
        self.tree.expandAll()

    def _on_tree_context_menu(self, pos: QPoint) -> None:
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        item = index.internalPointer()
        is_object_node = (item.parent is not None and
                          item.parent == self.model._root_item)
        is_function_node = (item.parent is not None and
                            item.parent.parent == self.model._root_item)
        menu = QMenu(self)

        if is_object_node:
            obj_id = self.model._root_item.children.index(item)
            loc_id = self.location_selector.currentData()
            script = self.state.backend.get_script(loc_id)
            has_empty_arb = any(script._function_is_empty(obj_id, f) for f in range(3, 16))
            if has_empty_arb:
                act = menu.addAction("Add Function")
                act.triggered.connect(
                    lambda checked, oid=obj_id: self.on_add_function_pressed(oid)
                )

        if is_function_node:
            object_item = item.parent
            obj_id = self.model._root_item.children.index(object_item)
            func_id = getattr(item, 'func_id', None)
            if func_id is not None and func_id >= 3:
                act = menu.addAction("Remove Function")
                act.triggered.connect(
                    lambda checked, oid=obj_id, fid=func_id: self.on_remove_function_pressed(oid, fid)
                )
            if func_id is not None and item.is_link and item.link_target is not None:
                act = menu.addAction("Break Link")
                act.triggered.connect(
                    lambda checked, oid=obj_id, fid=func_id: self.on_break_link_pressed(oid, fid)
                )
            if func_id is not None and not item.is_link and func_id != 0:
                act = menu.addAction("Convert to Link\u2026")
                act.triggered.connect(
                    lambda checked, oid=obj_id, fid=func_id: self.on_convert_to_link_pressed(oid, fid)
                )

        if not menu.isEmpty():
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def on_add_function_pressed(self, obj_id: int) -> None:
        try:
            self.model.append_function(obj_id)
        except IndexError as e:
            self.command_label.setText(str(e))
            return
        self.tree.expandAll()
        obj_index = self.model.index(obj_id, 0, QModelIndex())
        obj_item = obj_index.internalPointer()
        if obj_item and obj_item.children:
            new_func_row = len(obj_item.children) - 1
            self.tree.setCurrentIndex(self.model.index(new_func_row, 0, obj_index))

    def on_remove_function_pressed(self, obj_id: int, func_id: int) -> None:
        try:
            self.model.remove_function(obj_id, func_id)
        except ValueError as e:
            self.command_label.setText(str(e))
            return
        self.tree.expandAll()

    def on_break_link_pressed(self, obj_id: int, func_id: int) -> None:
        try:
            self.model.break_link(obj_id, func_id)
        except ValueError as e:
            self.command_label.setText(str(e))
            return
        self.tree.expandAll()

    def on_convert_to_link_pressed(self, obj_id: int, func_id: int) -> None:
        loc_id = self.location_selector.currentData()
        script = self.state.backend.get_script(loc_id)
        dialog = _LinkTargetDialog(script, obj_id, func_id, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        target = dialog.selected_target()
        if target is None:
            return
        tgt_obj, tgt_func = target
        try:
            self.model.convert_to_link(obj_id, func_id, tgt_obj, tgt_func)
        except ValueError as e:
            self.command_label.setText(str(e))
            return
        self.tree.expandAll()

    def update_command_tree(self, items: list[CommandItem]):
        """Update the command tree with new items"""
        new_root = CommandItem(name="Root", children=items)
        self.model.replace_items(new_root)

    @pyqtSlot()
    def on_update_command(self):
        """Handle command updates"""
        try:
            self.command_menu.set_platform(self.state.backend.platform)
            new_command = self.command_menu.get_command()
            if new_command.command == 0x1:
                return
                
            current_item = self.tree.currentIndex().internalPointer()
            self.model.update_command(current_item, new_command)

            modified_str = self.command_menu.get_modified_string()
            if modified_str is not None and new_command.args:
                loc_id = self.location_selector.currentData()
                string_idx = new_command.args[0]
                try:
                    self.state.backend.modify_string(loc_id, string_idx, modified_str)
                    expanded = self._save_expansion_state()
                    self.model.change_location(loc_id)
                    self._restore_expansion_state(expanded)
                except Exception as e:
                    print(f"String update failed: {e}")

            self.tree.viewport().update()

            is_match, discrepancies = self.compare_tree_with_script()
            if not is_match:
                print("Tree discrepancies found:")
                for d in discrepancies:
                    print(f"- {d}")
        except Exception as e:
            print(e)

    @pyqtSlot(int)
    def on_command_group_changed(self, index: int):
        """Handle command group selection changes"""
        self.command_subgroup_selector.clear()
        command_type = self.command_group_selector.itemData(index)
        
        if command_type in event_command_groupings:
            for subtype in event_command_groupings[command_type]:
                self.command_subgroup_selector.addItem(subtype.value, subtype)
                
        if self.command_subgroup_selector.count() > 0:
            self.command_subgroup_selector.currentIndexChanged.connect(
                self.on_command_subgroup_changed
            )
            self.on_command_subgroup_changed(0)

    @pyqtSlot(int)
    def on_command_subgroup_changed(self, index: int):
        """Handle command subgroup selection changes"""
        if index < 0:
            return
            
        command_type = self.command_group_selector.currentData()
        command_subtype = self.command_subgroup_selector.itemData(index)
        
        if command_type in cm.menu_mapping and command_subtype in cm.menu_mapping[command_type]:
            self.update_command_menu(cm.menu_mapping[command_type][command_subtype])

    def _save_expansion_state(self) -> list[list[int]]:
        """Return row-path lists for every currently expanded tree node."""
        paths: list[list[int]] = []

        def recurse(parent: QModelIndex, path: list[int]) -> None:
            for row in range(self.model.rowCount(parent)):
                idx = self.model.index(row, 0, parent)
                child_path = path + [row]
                if self.tree.isExpanded(idx):
                    paths.append(child_path)
                recurse(idx, child_path)

        recurse(QModelIndex(), [])
        return paths

    def _restore_expansion_state(self, paths: list[list[int]]) -> None:
        """Re-expand nodes identified by their row paths."""
        for path in paths:
            idx = QModelIndex()
            for row in path:
                idx = self.model.index(row, 0, idx)
                if not idx.isValid():
                    break
            else:
                self.tree.setExpanded(idx, True)

    def update_command_menu(self, new_menu: BaseCommandMenu):
        """Update the command menu widget"""
        self.command_layout.removeWidget(self.command_menu_widget)
        self.command_menu_widget.setParent(None)
        
        self.command_menu = new_menu
        self.command_menu_widget = self.command_menu.command_widget()
        self.command_layout.insertWidget(2, self.command_menu_widget)

    def _compare_items(self, current_items: list[CommandItem], 
                    processed_items: list[CommandItem], 
                    path: list[str],
                    discrepancies: list[str]) -> bool:
        """
        Recursively compare two lists of CommandItems.
        
        Args:
            current_items: List of CommandItems from the current tree view
            processed_items: List of CommandItems from the processed script
            path: Current path in the tree for error reporting
            discrepancies: List to collect discrepancy descriptions
            
        Returns:
            bool: True if the items match, False otherwise
        """
        if len(current_items) != len(processed_items):
            discrepancies.append(
                f"Length mismatch at {' > '.join(path)}: "
                f"expected {len(processed_items)}, got {len(current_items)}"
            )
            return False
        
        is_match = True
        for i, (current, processed) in enumerate(zip(current_items, processed_items)):
            current_path = path + [current.name]
            #print("Curr: {} Expected: {}".format(current.command, processed.command))
            # Compare basic properties
            if current.name != processed.name:
                discrepancies.append(
                    f"Name mismatch at {' > '.join(current_path)}: "
                    f"expected '{processed.name}', got '{current.name}'"
                )
                is_match = False
                
            if current.command != processed.command:
                discrepancies.append(
                    f"Command mismatch at {' > '.join(current_path)}: "
                    f"expected {processed.command}, got {current.command}"
                )
                is_match = False
                
            if current.address != processed.address:
                discrepancies.append(
                    f"Address mismatch at {' > '.join(current_path)}: "
                    f"expected 0x{processed.address:02X}, got 0x{current.address:02X}"
                )
                is_match = False
                return False
            
            # Recursively compare children
            if not self._compare_items(
                current.children, 
                processed.children, 
                current_path,
                discrepancies
            ):
                is_match = False
        
        return is_match

    def validate_tree_state(self) -> None:
        """
        Validate the current tree state against the script data.
        Raises AssertionError with details if the trees don't match.
        """
        is_match, discrepancies = self.compare_tree_with_script()
        if not is_match:
            raise AssertionError(
                "Tree view does not match script data:\n" + 
                "\n".join(f"- {d}" for d in discrepancies)
            )

    def compare_tree_with_script(self) -> tuple[bool, list[str]]:
        """
        Compare the current tree view state with the processed script data.
        
        Returns:
            tuple[bool, list[str]]: A tuple containing:
                - bool: True if trees match, False otherwise
                - list[str]: List of discrepancy descriptions if trees don't match
        """
        current_tree_root = self.model._root_item
        
        processed_items = process_script(self.state.backend.get_script(self.location_selector.currentData()))
        
        discrepancies = []
        is_match = self._compare_items(current_tree_root.children, processed_items, [], discrepancies)
        
        return is_match, discrepancies

def main():
    app = QApplication(sys.argv)

    input_file = None
    if len(sys.argv) > 1 and sys.argv[1] == "--input-file":
        if len(sys.argv) != 3:
            print("Usage: temporalredux.py --input-file <path>")
            sys.exit(1)
        input_file = Path(sys.argv[2])
    else:
        input_file = _open_file_or_directory()
        if input_file is None:
            sys.exit()

    if not input_file.exists():
        raise FileNotFoundError(f"Path not found: {input_file}")

    try:
        window = EventViewer(input_file)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    window.show()
    app.exec()

if __name__ == "__main__":
    main()