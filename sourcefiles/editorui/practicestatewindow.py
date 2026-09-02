"""Window for editing Chrono Trigger Practice ROM save-state values.

"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from editorui.inventoryeditor import InventoryEditorWidget
from editorui.unsavedchanges import UnsavedChangesChoice, prompt_unsaved_changes
from practice.memorylocationdefs import MEMORY_FIELD_DEFS
from practice.fields import (
    FieldKind, ResolvedField, apply_field_value, merge_consecutive_raw_fields,
    resolve_displayable_and_disabled_fields,
)
from practice.memorymap import build_address_index
from practice.scanner import (
    PracticeSaveState, SaveStateKey, refresh_save_state, scan_backend_for_save_states,
)

if TYPE_CHECKING:
    from editorui.activitylog import ActivityLog
    from gamebackend import GameBackend

_LOCATION_ITEM_ROLE = Qt.ItemDataRole.UserRole
_ADDRESS_INDEX = build_address_index(MEMORY_FIELD_DEFS)


class PracticeSaveStateWindow(QMainWindow):
    """Lists practice-hack-editable locations and edits their save-state values."""

    def __init__(self, backend: 'GameBackend', activity_log: 'ActivityLog', file_path: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Practice Save States")
        self.resize(900, 650)

        self._activity_log = activity_log
        self._save_states: dict[SaveStateKey, PracticeSaveState] = {}
        self._states_per_location: Counter[int] = Counter()
        self._address_index = _ADDRESS_INDEX
        self._backend: Optional['GameBackend'] = None
        self._file_path: Optional[Path] = None
        self._needs_rescan = False
        # Identifies the save state on screen: a location can hold more than
        # one, so a bare location id is ambiguous.
        self._current_key: Optional[SaveStateKey] = None
        self._current_disabled_fields: list[ResolvedField] = []
        self._field_widgets: list[tuple[ResolvedField, object]] = []

        self._setup_ui()
        self.set_backend(backend, file_path)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        splitter.addWidget(self._build_location_panel())
        splitter.addWidget(self._build_field_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self._status_label = QLabel()
        root_layout.addWidget(self._status_label)

    def _build_location_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Locations with a save state:"), 1)
        rescan_button = QPushButton("Rescan")
        rescan_button.clicked.connect(self._rescan)
        header_row.addWidget(rescan_button)
        layout.addLayout(header_row)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Filter locations…")
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        self._location_list = QListWidget()
        self._location_list.currentItemChanged.connect(self._on_location_selected)
        layout.addWidget(self._location_list, 1)

        self._location_count_label = QLabel()
        layout.addWidget(self._location_count_label)

        panel.setMinimumWidth(260)
        return panel

    def _build_field_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._location_title_label = QLabel("Select a location on the left.")
        layout.addWidget(self._location_title_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._field_form_widget = QWidget()
        self._field_form_layout = QVBoxLayout(self._field_form_widget)
        self._field_form_layout.addStretch(1)
        self._scroll_area.setWidget(self._field_form_widget)
        layout.addWidget(self._scroll_area, 1)

        bottom_row = QHBoxLayout()
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._on_save)
        self._save_button.setEnabled(False)
        bottom_row.addWidget(QLabel(
            "Saving writes this location into the rom and writes the rom "
            "to disk immediately."
        ), 1)
        bottom_row.addWidget(self._save_button)
        layout.addLayout(bottom_row)

        return panel

    def set_backend(self, backend: 'GameBackend', file_path: Path) -> None:
        """Point this window at a (possibly newly-opened) backend, rescanning
        if it is on screen and otherwise deferring that to showEvent().
        """
        if backend is self._backend and file_path == self._file_path:
            return

        self._backend = backend
        self._file_path = file_path
        self._needs_rescan = True
        if self.isVisible():
            self._rescan()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._needs_rescan:
            self._rescan()

    def _rescan(self) -> None:
        self._status_label.setText("Scanning…")
        self.setEnabled(False)
        try:
            self._save_states = scan_backend_for_save_states(self._backend)
        finally:
            self.setEnabled(True)

        self._needs_rescan = False
        self._current_key = None
        self._populate_location_list()
        self._clear_field_panel()
        self._status_label.setText(f"{len(self._save_states)} save state(s) found.")

    def _populate_location_list(self, filter_text: str = '') -> None:
        self._location_list.blockSignals(True)
        self._location_list.clear()

        # Derived once per repopulate rather than once per row, and here
        # rather than in _rescan() so it stays correct however _save_states
        # was populated.
        self._states_per_location = Counter(
            location_id for location_id, _ in self._save_states)

        filter_lower = filter_text.lower()
        shown = 0
        for key in sorted(self._save_states):
            location_id, _ = key
            save_state = self._save_states[key]
            if filter_lower and filter_lower not in save_state.location_name.lower():
                continue
            segment_count = len(save_state.segments)
            item = QListWidgetItem(
                f"{save_state.location_name}  [0x{location_id:03X}]{self._slot_label(key)}  "
                f"({segment_count} segment{'s' if segment_count != 1 else ''})"
            )
            item.setData(_LOCATION_ITEM_ROLE, key)
            self._location_list.addItem(item)
            shown += 1

        self._location_list.blockSignals(False)
        self._location_count_label.setText(f"Showing {shown} of {len(self._save_states)}")

    def _on_search_changed(self, text: str) -> None:
        self._populate_location_list(text)

    def _on_location_selected(
            self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]) -> None:
        if previous is not None and self._has_pending_changes():
            location_name = self._save_states[self._current_key].location_name
            choice = prompt_unsaved_changes(self, location_name)
            if choice == UnsavedChangesChoice.CANCEL:
                self._location_list.blockSignals(True)
                self._location_list.setCurrentItem(previous)
                self._location_list.blockSignals(False)
                return
            if choice == UnsavedChangesChoice.SAVE:
                self._on_save()

        if current is None:
            self._current_key = None
            self._clear_field_panel()
            return
        self._show_location(current.data(_LOCATION_ITEM_ROLE))

    def _show_location(self, key: SaveStateKey) -> None:
        self._current_key = key
        location_id, guard_value = key
        save_state = self._save_states[key]

        self._location_title_label.setText(
            f"{save_state.location_name}  [0x{location_id:03X}]{self._slot_label(key)}"
        )

        resolved_fields, disabled_fields = resolve_displayable_and_disabled_fields(
            save_state, self._address_index)
        self._current_disabled_fields = disabled_fields
        self._rebuild_field_panel(resolved_fields)

        read_only = self._backend.is_read_only
        self._save_button.setEnabled(not read_only)
        if read_only:
            self._status_label.setText("This file is read-only; edits cannot be saved.")
        else:
            self._status_label.setText('')

    def _slot_label(self, key: SaveStateKey) -> str:
        """The "  slot N" suffix, but only for locations that actually hold
        more than one save state -- so the overwhelming majority of rooms (a
        single save state) read exactly as they did before slots existed."""
        location_id, guard_value = key
        if self._states_per_location[location_id] <= 1:
            return ""
        return f"  slot {guard_value}"

    def _clear_field_panel(self) -> None:
        self._current_disabled_fields = []
        self._location_title_label.setText("Select a location on the left.")
        self._save_button.setEnabled(False)
        self._rebuild_field_panel([])

    def _rebuild_field_panel(self, resolved_fields: list[ResolvedField]) -> None:
        # Everything except the trailing stretch item added in _build_field_panel.
        while self._field_form_layout.count() > 1:
            item = self._field_form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._field_widgets = []

        groups: dict[str, list[ResolvedField]] = {}
        for resolved_field in resolved_fields:
            groups.setdefault(resolved_field.group, []).append(resolved_field)

        insert_at = self._field_form_layout.count() - 1
        for group_name, group_fields in groups.items():
            group_box = QGroupBox(group_name)
            form = QFormLayout(group_box)
            # Merge within this group only, so a Mem Copy that happens to
            # span two curated groups (e.g. Crono's block into Marle's)
            # never combines undocumented bytes from different groups into
            # one row.
            for resolved_field in merge_consecutive_raw_fields(group_fields):
                if resolved_field.kind == FieldKind.BITMASK:
                    self._add_bitmask_rows(form, resolved_field)
                elif resolved_field.kind == FieldKind.INVENTORY_ITEMS:
                    self._add_inventory_widget(form, group_fields)
                elif resolved_field.kind == FieldKind.INVENTORY_QUANTITIES:
                    pass  # rendered together with its paired items field above
                else:
                    widget = self._build_field_widget(resolved_field)
                    self._field_widgets.append((resolved_field, widget))
                    form.addRow(self._field_row_label(resolved_field), widget)
            self._field_form_layout.insertWidget(insert_at, group_box)
            insert_at += 1

    def _add_bitmask_rows(self, form: QFormLayout, resolved_field: ResolvedField) -> None:
        """Add one row per documented bit, rather than one row for the whole
        byte: each row's label is that bit's own description (not repeated
        on the checkbox/spin box itself, which carries no text of its own).

        Apply still needs every bit's widget together as one unit (to OR
        them back into a single byte), so they're also recorded on an
        untracked, never-displayed QWidget stored in _field_widgets
        """
        option_widgets = self._build_bitmask_option_widgets(resolved_field)

        tracker = QWidget()
        tracker.setProperty('bit_option_widgets', option_widgets)
        self._field_widgets.append((resolved_field, tracker))

        for option, widget in option_widgets:
            label = QLabel(option.description)
            label.setToolTip(f"${resolved_field.address:06X}  mask 0x{option.mask:02X}")
            form.addRow(label, widget)

    def _add_inventory_widget(self, form: QFormLayout, group_fields: list[ResolvedField]) -> None:
        """The paired item-ID/quantity arrays render as one slot-list widget
        instead of two rows."""
        items_field = next(f for f in group_fields if f.kind == FieldKind.INVENTORY_ITEMS)
        quantities_field = next(f for f in group_fields if f.kind == FieldKind.INVENTORY_QUANTITIES)
        widget = InventoryEditorWidget(items_field.current_bytes, quantities_field.current_bytes)
        self._field_widgets.append((items_field, widget))
        self._field_widgets.append((quantities_field, widget))
        form.addRow(widget)

    @staticmethod
    def _field_row_label(resolved_field: ResolvedField) -> QLabel:
        label = QLabel(resolved_field.label)
        label.setToolTip(f"${resolved_field.address:06X}  ({resolved_field.length} byte(s))")
        return label

    def _build_field_widget(self, resolved_field: ResolvedField) -> QWidget:
        if resolved_field.kind == FieldKind.RAW:
            return self._build_raw_widget(resolved_field)
        return self._build_numeric_widget(resolved_field)

    def _build_numeric_widget(self, resolved_field: ResolvedField) -> QSpinBox:
        spin_box = QSpinBox()
        spin_box.setRange(0, (256 ** resolved_field.length) - 1)
        spin_box.setValue(int.from_bytes(resolved_field.current_bytes, 'little'))
        return spin_box

    def _build_raw_widget(self, resolved_field: ResolvedField) -> QLineEdit:
        # RAW spans can be arbitrarily long (a merged run of undocumented
        # bytes), so this is edited as hex text rather than a bounded integer.
        line_edit = QLineEdit(resolved_field.current_bytes.hex())
        line_edit.setToolTip(f"{resolved_field.length} byte(s) of hex, no separators")
        return line_edit

    @staticmethod
    def _build_bitmask_option_widgets(resolved_field: ResolvedField) -> list[tuple]:
        """One bare widget per documented bit. Single-bit masks are true booleans
        and round-trip exactly through a checkbox. Multi-bit masks (e.g. a 3-bit 
        sub-field, mask 0x07) are small enumerations"""
        current_value = resolved_field.current_bytes[0]
        option_widgets: list[tuple] = []
        for option in resolved_field.bit_options:
            if option.is_single_bit:
                checkbox = QCheckBox()
                checkbox.setChecked(option.extract(current_value) == 1)
                option_widgets.append((option, checkbox))
            else:
                spin_box = QSpinBox()
                spin_box.setRange(0, option.extract(option.mask))
                spin_box.setValue(option.extract(current_value))
                option_widgets.append((option, spin_box))
        return option_widgets

    def _pending_changes(self) -> list[tuple[ResolvedField, bytes]]:
        """Fields whose widget value currently differs from what's on
        record (what Save would write if clicked right now). Also
        used to detect unsaved edits when the user tries to navigate away"""
        changes: list[tuple[ResolvedField, bytes]] = []
        for resolved_field, widget in self._field_widgets:
            new_bytes = self._read_widget_value(resolved_field, widget)
            if new_bytes is None or new_bytes == resolved_field.current_bytes:
                continue
            changes.append((resolved_field, new_bytes))
        return changes

    def _has_pending_changes(self) -> bool:
        return bool(self._pending_changes())

    def _on_save(self) -> None:
        if self._current_key is None:
            return

        location_id, _ = self._current_key
        event = self._backend.get_script(location_id)
        changes = self._pending_changes()

        change_log_entries = [
            {
                "address": f"0x{resolved_field.address:06X}",
                "label": resolved_field.label,
                "old": resolved_field.current_bytes.hex(),
                "new": new_bytes.hex(),
            }
            for resolved_field, new_bytes in changes
        ]

        for resolved_field, new_bytes in changes:
            apply_field_value(event, resolved_field, new_bytes)

        # These should never be edited, but just in case revert them to
        # their original values
        for disabled_field in self._current_disabled_fields:
            apply_field_value(event, disabled_field, disabled_field.current_bytes)

        if changes:
            self._backend.write_script(location_id)
            self._backend.save_to_file(self._file_path)
            self._activity_log.log_save_state_edit(location_id, change_log_entries)
            self._activity_log.log_file_save(str(self._file_path))
            self._rescan_current_location()

        # Refresh so the next Save diffs against the values just written.
        self._show_location(self._current_key)

        if changes:
            self._status_label.setText(f"Saved {len(changes)} change(s) to {self._file_path.name}.")
        else:
            self._status_label.setText("No changes to save.")

    def _rescan_current_location(self) -> None:
        """Refresh the Mem Copy EventCommand objects cached in
        _save_states[_current_key] from the just-edited event.data."""
        event = self._backend.get_script(self._current_key[0])
        refresh_save_state(event, self._save_states[self._current_key])

    def _read_widget_value(self, resolved_field: ResolvedField, widget: QWidget) -> Optional[bytes]:
        if resolved_field.kind == FieldKind.BITMASK:
            option_widgets = widget.property('bit_option_widgets')
            # Every documented option's bits are cleared before any is written
            # back, so two options sharing a bit combine rather than the last
            # one silently winning.
            new_value = resolved_field.current_bytes[0]
            for option, _option_widget in option_widgets:
                new_value = option.clear_from(new_value)
            for option, option_widget in option_widgets:
                option_value = (
                    int(option_widget.isChecked()) if isinstance(option_widget, QCheckBox)
                    else option_widget.value()
                )
                new_value |= option.shifted_into_place(option_value)
            return bytes([new_value])

        if resolved_field.kind == FieldKind.INVENTORY_ITEMS:
            return widget.item_bytes()
        if resolved_field.kind == FieldKind.INVENTORY_QUANTITIES:
            return widget.quantity_bytes()

        if isinstance(widget, QSpinBox):
            return widget.value().to_bytes(resolved_field.length, 'little')

        if isinstance(widget, QLineEdit):
            try:
                new_bytes = bytes.fromhex(widget.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Invalid Value", f"{resolved_field.label}: not valid hex.")
                return None
            if len(new_bytes) != resolved_field.length:
                QMessageBox.warning(
                    self, "Invalid Value",
                    f"{resolved_field.label}: expected {resolved_field.length} byte(s), "
                    f"got {len(new_bytes)}."
                )
                return None
            return new_bytes

        return None
