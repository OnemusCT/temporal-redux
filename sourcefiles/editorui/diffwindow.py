"""Side-by-side event differ window."""
from __future__ import annotations

from enum import auto, Enum
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QComboBox, QTreeView, QCompleter,
    QHeaderView, QStatusBar, QMenu,
    QDockWidget, QTableWidget, QTableWidgetItem, QApplication,
    QProgressDialog, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QPoint

from editorui.diffmodel import DiffModel, DiffColumn
from editorui.eventdiff import (
    compute_location_diff,
    compute_location_identical,
    CopyEligibility,
    DiffLine,
    DiffStatus,
    eligibility_reason,
    FunctionDiff,
    LocationDiff,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gamebackend import GameBackend


class _Direction(Enum):
    LEFT_TO_RIGHT = auto()
    RIGHT_TO_LEFT = auto()

class DiffFilterMode:
    ALL = "Show All"
    DIFFERENCES = "Differences Only"
    LEFT_ONLY = "Left-Only"
    RIGHT_ONLY = "Right-Only"


class DiffWindow(QMainWindow):
    """Window for comparing event scripts between two backends."""

    def __init__(self, open_callback, parent=None):
        """
        Args:
            open_callback: callable() -> Optional[GameBackend]
                Called when the user clicks an Open button; should show a file
                dialog, build a backend, and return it (or None on cancel).
            parent: parent QWidget
        """
        super().__init__(parent)
        self._open_callback = open_callback
        self._left_backend: Optional[GameBackend] = None
        self._right_backend: Optional[GameBackend] = None
        self._left_path: Optional[Path] = None
        self._right_path: Optional[Path] = None

        self._diff_model = DiffModel(self)
        self._full_diff: Optional[LocationDiff] = None

        self._setup_ui()
        self.setWindowTitle("Event Differ")
        self.resize(1100, 700)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        file_menu = self.menuBar().addMenu("File")
        self._save_left_action = QAction("Save Left", self)
        self._save_left_action.triggered.connect(self._on_save_left)
        self._save_left_action.setEnabled(False)
        file_menu.addAction(self._save_left_action)

        self._save_right_action = QAction("Save Right", self)
        self._save_right_action.triggered.connect(self._on_save_right)
        self._save_right_action.setEnabled(False)
        file_menu.addAction(self._save_right_action)

        self._save_all_action = QAction("Save All", self)
        self._save_all_action.triggered.connect(self._on_save_all)
        self._save_all_action.setEnabled(False)
        file_menu.addAction(self._save_all_action)

        top_row = QHBoxLayout()

        self._left_open_button = QPushButton("Open Left...")
        self._left_open_button.clicked.connect(self._on_open_left)
        self._left_label = QLabel("(none)")
        self._left_label.setMinimumWidth(200)

        self._right_open_button = QPushButton("Open Right...")
        self._right_open_button.clicked.connect(self._on_open_right)
        self._right_label = QLabel("(none)")
        self._right_label.setMinimumWidth(200)

        top_row.addWidget(self._left_open_button)
        top_row.addWidget(self._left_label, 1)
        top_row.addWidget(self._right_open_button)
        top_row.addWidget(self._right_label, 1)
        root_layout.addLayout(top_row)

        selector_row = QHBoxLayout()

        selector_row.addWidget(QLabel("Location:"))
        self._location_selector = QComboBox()
        self._location_selector.setEditable(True)
        self._location_selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._location_selector.setMinimumWidth(300)
        self._location_selector.currentIndexChanged.connect(self._on_location_changed)
        selector_row.addWidget(self._location_selector, 1)

        selector_row.addWidget(QLabel("Filter:"))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            DiffFilterMode.ALL,
            DiffFilterMode.DIFFERENCES,
            DiffFilterMode.LEFT_ONLY,
            DiffFilterMode.RIGHT_ONLY,
        ])
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        selector_row.addWidget(self._filter_combo)

        self._scan_button = QPushButton("Scan All Locations")
        self._scan_button.clicked.connect(self._on_scan_all)
        selector_row.addWidget(self._scan_button)

        root_layout.addLayout(selector_row)

        copy_row = QHBoxLayout()
        self._copy_left_to_right_button = QPushButton("Copy Left -> Right")
        self._copy_left_to_right_button.clicked.connect(self._on_copy_left_to_right)
        self._copy_right_to_left_button = QPushButton("Copy Right -> Left")
        self._copy_right_to_left_button.clicked.connect(self._on_copy_right_to_left)
        copy_row.addStretch()
        copy_row.addWidget(self._copy_left_to_right_button)
        copy_row.addWidget(self._copy_right_to_left_button)
        copy_row.addStretch()
        root_layout.addLayout(copy_row)

        self._tree = QTreeView()
        self._tree.setModel(self._diff_model)
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(False)
        self._tree.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        header = self._tree.header()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(DiffColumn.LEFT_ADDRESS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(DiffColumn.STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(DiffColumn.RIGHT_ADDRESS, QHeaderView.ResizeMode.ResizeToContents)
        root_layout.addWidget(self._tree, 1)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Open two files to begin comparing.")

        self._summary_dock = QDockWidget("Batch Summary", self)
        self._summary_table = QTableWidget()
        self._summary_table.setColumnCount(2)
        self._summary_table.setHorizontalHeaderLabels(["Location", "Status"])
        self._summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._summary_table.horizontalHeader().setStretchLastSection(True)
        self._summary_table.cellDoubleClicked.connect(self._on_summary_row_double_clicked)
        self._summary_dock.setWidget(self._summary_table)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._summary_dock)
        self._summary_dock.hide()

    def load_left(self, backend: GameBackend, path: Path) -> None:
        """Pre-populate the left side without showing a file dialog."""
        self._left_backend = backend
        self._left_path = path
        self._left_label.setText(str(path))
        self._update_save_actions()
        self._refresh_location_list()

    def _on_open_left(self) -> None:
        result = self._open_callback()
        if result is None:
            return
        backend, path = result
        self._left_backend = backend
        self._left_path = path
        self._left_label.setText(str(path))
        self._update_save_actions()
        self._refresh_location_list()

    def _on_open_right(self) -> None:
        result = self._open_callback()
        if result is None:
            return
        backend, path = result
        self._right_backend = backend
        self._right_path = path
        self._right_label.setText(str(path))
        self._update_save_actions()
        self._refresh_location_list()

    def _update_save_actions(self) -> None:
        left_ok = self._left_backend is not None and not self._left_backend.is_read_only
        right_ok = self._right_backend is not None and not self._right_backend.is_read_only
        self._save_left_action.setEnabled(left_ok)
        self._save_right_action.setEnabled(right_ok)
        self._save_all_action.setEnabled(left_ok or right_ok)

    def _on_save_left(self) -> None:
        if self._left_backend is None or self._left_path is None:
            return
        self._left_backend.save_to_file(self._left_path)
        self._status_bar.showMessage(f"Saved left: {self._left_path}")

    def _on_save_right(self) -> None:
        if self._right_backend is None or self._right_path is None:
            return
        self._right_backend.save_to_file(self._right_path)
        self._status_bar.showMessage(f"Saved right: {self._right_path}")

    def _on_save_all(self) -> None:
        saved = []
        if self._left_backend is not None and self._left_path is not None and not self._left_backend.is_read_only:
            self._left_backend.save_to_file(self._left_path)
            saved.append(f"left ({self._left_path.name})")
        if self._right_backend is not None and self._right_path is not None and not self._right_backend.is_read_only:
            self._right_backend.save_to_file(self._right_path)
            saved.append(f"right ({self._right_path.name})")
        if saved:
            self._status_bar.showMessage(f"Saved: {', '.join(saved)}")

    def _get_common_locations(self) -> tuple[list[int], dict[int, str], dict[int, str]]:
        """Return (sorted common ids, left locs dict, right locs dict)."""
        left_locs = {lid: name for lid, name in self._left_backend.get_location_list()}
        right_locs = {lid: name for lid, name in self._right_backend.get_location_list()}
        common_ids = sorted(set(left_locs.keys()) & set(right_locs.keys()))
        return common_ids, left_locs, right_locs

    def _refresh_location_list(self) -> None:
        """Populate the location selector with the intersection of both backends."""
        self._location_selector.blockSignals(True)
        self._location_selector.clear()

        if self._left_backend is None or self._right_backend is None:
            self._location_selector.blockSignals(False)
            return

        common_ids, left_locs, right_locs = self._get_common_locations()

        for lid in common_ids:
            # Prefer left name, fall back to right
            name = left_locs.get(lid, right_locs.get(lid, f"Location {lid:03X}"))
            self._location_selector.addItem(name, lid)

        self._location_selector.blockSignals(False)

        # Setup substring completer
        names = [self._location_selector.itemText(i)
                 for i in range(self._location_selector.count())]
        completer = QCompleter(names, self._location_selector)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._location_selector.setCompleter(None)
        self._location_selector.lineEdit().setCompleter(completer)
        completer.activated[str].connect(self._on_location_completion_selected)

        if common_ids:
            self._location_selector.setCurrentIndex(0)
            self._on_location_changed(0)
        else:
            self._status_bar.showMessage("No common locations found between the two files.")

    def _on_location_completion_selected(self, text: str) -> None:
        index = self._location_selector.findText(text)
        if index >= 0:
            self._location_selector.setCurrentIndex(index)

    def _on_location_changed(self, index: int) -> None:
        if self._left_backend is None or self._right_backend is None:
            return
        loc_id = self._location_selector.itemData(index)
        if loc_id is None:
            return
        self._compute_and_display(loc_id)

    def _compute_and_display(self, loc_id: int) -> None:
        left_event = self._left_backend.get_script(loc_id)
        right_event = self._right_backend.get_script(loc_id)

        self._full_diff = compute_location_diff(
            left_event, right_event, loc_id,
            left_read_only=self._left_backend.is_read_only,
            right_read_only=self._right_backend.is_read_only,
        )

        self._apply_filter(self._full_diff)

    def _on_filter_changed(self, text: str) -> None:
        if self._full_diff is not None:
            self._apply_filter(self._full_diff)

    def _apply_filter(self, diff: LocationDiff) -> None:
        filter_mode = self._filter_combo.currentText()

        if filter_mode == DiffFilterMode.ALL:
            filtered = diff
        else:
            filtered_funcs = []
            for fd in diff.functions:
                if filter_mode == DiffFilterMode.DIFFERENCES:
                    lines = [l for l in fd.lines if l.status != DiffStatus.EQUAL]
                elif filter_mode == DiffFilterMode.LEFT_ONLY:
                    lines = [l for l in fd.lines if l.status == DiffStatus.LEFT_ONLY]
                elif filter_mode == DiffFilterMode.RIGHT_ONLY:
                    lines = [l for l in fd.lines if l.status == DiffStatus.RIGHT_ONLY]
                else:
                    lines = fd.lines

                if lines:
                    filtered_funcs.append(FunctionDiff(
                        object_index=fd.object_index,
                        function_index=fd.function_index,
                        function_name=fd.function_name,
                        lines=lines,
                    ))
            filtered = LocationDiff(
                location_id=diff.location_id,
                functions=filtered_funcs,
                left_num_objects=diff.left_num_objects,
                right_num_objects=diff.right_num_objects,
            )

        self._diff_model.set_diff(filtered)
        self._tree.expandAll()
        self._update_status(filtered)

    def _update_status(self, diff: LocationDiff) -> None:
        """Update status bar with diff summary counts."""
        equal = modified = left_only = right_only = 0
        for fd in diff.functions:
            for line in fd.lines:
                if line.status == DiffStatus.EQUAL:
                    equal += 1
                elif line.status == DiffStatus.MODIFIED:
                    modified += 1
                elif line.status == DiffStatus.LEFT_ONLY:
                    left_only += 1
                elif line.status == DiffStatus.RIGHT_ONLY:
                    right_only += 1
        total = equal + modified + left_only + right_only
        self._status_bar.showMessage(
            f"{total} commands: {equal} identical, {modified} modified, "
            f"{left_only} left-only, {right_only} right-only"
        )

    def _get_selected_diff_lines(self) -> list[DiffLine]:
        """Return the DiffLines for all selected child rows (skipping headers)."""
        lines = []
        seen = set()
        for index in self._tree.selectionModel().selectedIndexes():
            if index.column() != 0:
                continue
            dl = self._diff_model.get_diff_line(index)
            if dl is not None and id(dl) not in seen:
                seen.add(id(dl))
                lines.append(dl)
        return lines

    def _find_function_diff_for_line(self, target: DiffLine) -> Optional[FunctionDiff]:
        """Find which FunctionDiff contains the given DiffLine."""
        diff = self._diff_model.location_diff
        if diff is None:
            return None
        for fd in diff.functions:
            for line in fd.lines:
                if line is target:
                    return fd
        return None

    def _can_copy_all(self, lines: list[DiffLine], direction: _Direction) -> tuple[bool, str]:
        """Check if all lines can be copied in the given direction.

        Returns (ok, reason).  direction is 'left_to_right' or 'right_to_left'.
        """
        if not lines:
            return False, "No lines selected"
        for dl in lines:
            eligibility = (dl.copy_left_to_right if direction == _Direction.LEFT_TO_RIGHT
                           else dl.copy_right_to_left)
            if eligibility != CopyEligibility.ALLOWED:
                return False, eligibility_reason(eligibility)
            # Must have a source command
            source = dl.left if direction == _Direction.LEFT_TO_RIGHT else dl.right
            if source is None:
                return False, "No source command on selected line"
        return True, ""

    def _on_copy_left_to_right(self) -> None:
        lines = self._get_selected_diff_lines()
        self._do_copy(lines, _Direction.LEFT_TO_RIGHT)

    def _on_copy_right_to_left(self) -> None:
        lines = self._get_selected_diff_lines()
        self._do_copy(lines, _Direction.RIGHT_TO_LEFT)

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._tree.indexAt(pos)
        if not index.isValid():
            return
        lines = self._get_selected_diff_lines()
        if not lines:
            return

        menu = QMenu(self)

        can_l2r, reason_l2r = self._can_copy_all(lines, _Direction.LEFT_TO_RIGHT)
        act_l2r = menu.addAction(f"Copy Left -> Right ({len(lines)})")
        act_l2r.setEnabled(can_l2r)
        if not can_l2r:
            act_l2r.setToolTip(reason_l2r)
        act_l2r.triggered.connect(lambda: self._do_copy(lines, _Direction.LEFT_TO_RIGHT))

        can_r2l, reason_r2l = self._can_copy_all(lines, _Direction.RIGHT_TO_LEFT)
        act_r2l = menu.addAction(f"Copy Right -> Left ({len(lines)})")
        act_r2l.setEnabled(can_r2l)
        if not can_r2l:
            act_r2l.setToolTip(reason_r2l)
        act_r2l.triggered.connect(lambda: self._do_copy(lines, _Direction.RIGHT_TO_LEFT))

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _do_copy(self, lines: list[DiffLine], direction: _Direction) -> None:
        """Execute the copy operation for the given lines and direction."""
        ok, reason = self._can_copy_all(lines, direction)
        if not ok:
            self._status_bar.showMessage(f"Cannot copy: {reason}")
            return

        loc_id = self._location_selector.currentData()
        if loc_id is None:
            return

        if direction == _Direction.LEFT_TO_RIGHT:
            target_backend = self._right_backend
        else:
            target_backend = self._left_backend

        target_event = target_backend.get_script(loc_id)

        # Sort lines by target address descending so insertions don't shift
        # addresses of subsequent operations.
        def sort_key(dl: DiffLine) -> int:
            if direction == _Direction.LEFT_TO_RIGHT:
                addr = dl.right_address
            else:
                addr = dl.left_address
            # One-sided lines have no target address; use a context-derived one.
            # Assign -1 so they sort last (processed first in reverse).
            return addr if addr is not None else -1

        sorted_lines = sorted(lines, key=sort_key, reverse=True)

        for dl in sorted_lines:
            self._copy_single_line(dl, direction, target_event)

        target_backend.write_script(loc_id)
        self._compute_and_display(loc_id)

    def _copy_single_line(self, dl: DiffLine, direction: _Direction, target_event) -> None:
        """Copy a single DiffLine's command into the target Event."""
        if direction == _Direction.LEFT_TO_RIGHT:
            source_cmd = dl.left
            target_address = dl.right_address
        else:
            source_cmd = dl.right
            target_address = dl.left_address

        source_bytes = source_cmd.to_bytearray()

        if dl.status == DiffStatus.MODIFIED:
            target_event.delete_commands(target_address, 1)
            target_event.insert_commands(source_bytes, target_address)

        elif dl.status == DiffStatus.LEFT_ONLY and direction == _Direction.LEFT_TO_RIGHT:
            insert_addr = self._find_insertion_address(dl, direction, target_event)
            if insert_addr is not None:
                target_event.insert_commands(source_bytes, insert_addr)

        elif dl.status == DiffStatus.RIGHT_ONLY and direction == _Direction.RIGHT_TO_LEFT:
            insert_addr = self._find_insertion_address(dl, direction, target_event)
            if insert_addr is not None:
                target_event.insert_commands(source_bytes, insert_addr)

        elif dl.status == DiffStatus.LEFT_ONLY and direction == _Direction.RIGHT_TO_LEFT:
            if target_address is not None:
                target_event.delete_commands(target_address, 1)

        elif dl.status == DiffStatus.RIGHT_ONLY and direction == _Direction.LEFT_TO_RIGHT:
            if target_address is not None:
                target_event.delete_commands(target_address, 1)

    def _find_insertion_address(self, dl: DiffLine, direction: _Direction, target_event) -> Optional[int]:
        """Find where to insert a one-sided command in the target event.

        Walks backwards through the parent FunctionDiff's lines to find the
        nearest preceding line with a target-side address, then inserts after it.
        Falls back to the function start if no preceding line is found.
        """
        func_diff = self._find_function_diff_for_line(dl)
        if func_diff is None:
            return None

        line_index = None
        for i, line in enumerate(func_diff.lines):
            if line is dl:
                line_index = i
                break
        if line_index is None:
            return None

        # Walk backwards to find a line with a target-side address
        for i in range(line_index - 1, -1, -1):
            prev = func_diff.lines[i]
            if direction == _Direction.LEFT_TO_RIGHT:
                if prev.right_address is not None and prev.right is not None:
                    return prev.right_address + len(prev.right)
            else:
                if prev.left_address is not None and prev.left is not None:
                    return prev.left_address + len(prev.left)

        # No preceding line found — insert at function start
        return target_event.get_function_start(func_diff.object_index, func_diff.function_index)

    def _on_scan_all(self) -> None:
        """Scan all common locations and show which ones differ."""
        if self._left_backend is None or self._right_backend is None:
            self._status_bar.showMessage("Open both files before scanning.")
            return

        common_ids, left_locs, right_locs = self._get_common_locations()

        if not common_ids:
            self._status_bar.showMessage("No common locations to scan.")
            return

        progress = QProgressDialog("Scanning locations...", "Cancel", 0, len(common_ids), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        different_locations: list[tuple[int, str]] = []
        identical_count = 0
        error_count = 0

        for i, lid in enumerate(common_ids):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            QApplication.processEvents()

            try:
                left_event = self._left_backend.get_script(lid)
                right_event = self._right_backend.get_script(lid)
                if not compute_location_identical(left_event, right_event):
                    name = left_locs.get(lid, right_locs.get(lid, f"Location {lid:03X}"))
                    different_locations.append((lid, name))
                else:
                    identical_count += 1
            except Exception:
                error_count += 1

        progress.setValue(len(common_ids))

        # Populate summary table
        self._summary_table.setRowCount(len(different_locations))
        for row, (lid, name) in enumerate(different_locations):
            loc_item = QTableWidgetItem(name)
            loc_item.setData(Qt.ItemDataRole.UserRole, lid)
            self._summary_table.setItem(row, 0, loc_item)
            self._summary_table.setItem(row, 1, QTableWidgetItem("Different"))

        self._summary_table.resizeColumnsToContents()
        self._summary_dock.show()

        msg = (f"Scan complete: {len(different_locations)} different, "
               f"{identical_count} identical")
        if error_count:
            msg += f", {error_count} errors"
        self._status_bar.showMessage(msg)

    def _on_summary_row_double_clicked(self, row: int, column: int) -> None:
        """Navigate to the location from the summary table."""
        item = self._summary_table.item(row, 0)
        if item is None:
            return
        lid = item.data(Qt.ItemDataRole.UserRole)
        if lid is None:
            return
        # Find and select this location in the combo
        for i in range(self._location_selector.count()):
            if self._location_selector.itemData(i) == lid:
                self._location_selector.setCurrentIndex(i)
                break

    @property
    def left_backend(self) -> Optional[GameBackend]:
        return self._left_backend

    @property
    def right_backend(self) -> Optional[GameBackend]:
        return self._right_backend

    @property
    def diff_model(self) -> DiffModel:
        return self._diff_model
