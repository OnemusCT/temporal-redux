"""Widget for editing the general inventory arrays ($7E2400 item IDs /
$7E2500 quantities) as a single-column list of slots, matching the in-game
item menu, instead of two raw hex strings.

Domain logic (decoding/encoding the fixed-length arrays, which items stack,
reordering) lives in practice/inventory.py and is Qt-free; this module is
just the widget wrapped around it. Every structural change (add, remove,
reorder) goes through a full row rebuild rather than trying to patch
individual widgets in place, so a row's widget can never end up bound to a
stale slot index.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QMimeData, QPoint, Qt
from PyQt6.QtGui import QDrag, QDragEnterEvent, QDropEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from editorui import lookups
from practice.inventory import (
    InventorySlot, decode_slots, encode_slots, is_stackable, real_slot_count, reorder,
    selectable_items,
)

_DRAG_MIME_TYPE = 'application/x-ct-inventory-slot'

# The item picker's contents, built once rather than per row
_ITEMS: list[tuple[str, int]] = [
    (lookups.items.get(int(item), str(item)), int(item))
    for item in selectable_items()
]
_ITEM_NAMES: list[str] = [name for name, _item_id in _ITEMS]
_ITEM_IDS: list[int] = [item_id for _name, item_id in _ITEMS]
_COMBO_INDEX_BY_ITEM_ID: dict[int, int] = {
    item_id: index for index, item_id in enumerate(_ITEM_IDS)
}


class _DragHandle(QLabel):
    """Small drag grip; press-and-drag on this (not the whole row) starts a move."""

    def __init__(self, row: '_InventoryRow'):
        super().__init__('⋮⋮')
        self._row = row
        self._press_position: Optional[QPoint] = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip('Drag to reorder')
        self.setFixedWidth(16)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._press_position is None:
            return
        moved = (event.position().toPoint() - self._press_position).manhattanLength()
        if moved < QApplication.startDragDistance():
            return

        mime_data = QMimeData()
        mime_data.setData(_DRAG_MIME_TYPE, str(self._row.index).encode('ascii'))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)
        self._press_position = None


class _InventoryRow(QFrame):
    """One editable slot: drag handle, item picker, quantity, remove button.

    Also the drop target for reordering -- dropping on the top or bottom
    half decides whether the dragged slot lands before or after this row.
    """

    def __init__(self, owner: 'InventoryEditorWidget', index: int, slot: InventorySlot):
        super().__init__()
        self.index = index
        self._owner = owner
        self.setAcceptDrops(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(_DragHandle(self))

        self.combo = QComboBox()
        self.combo.addItems(_ITEM_NAMES)
        self._item_ids = _ITEM_IDS
        combo_index = _COMBO_INDEX_BY_ITEM_ID.get(slot.item_id)
        if combo_index is None:
            # Not a real item (leftover garbage bytes). Add it as its
            # own entry rather than silently swapping in whatever sorts
            # first, so an untouched row still round-trips exactly.
            self.combo.insertItem(0, f"Unknown (0x{slot.item_id:02X})")
            self._item_ids = [slot.item_id] + _ITEM_IDS
            combo_index = 0
        self.combo.setCurrentIndex(combo_index)
        layout.addWidget(self.combo, 1)

        self.quantity = QSpinBox()
        self.quantity.setSpecialValueText('—')
        self._apply_quantity_range(slot)
        layout.addWidget(self.quantity)

        # Connected after the initial range/value is set, so constructing a
        # row from existing data never itself counts as an edit.
        self.combo.currentIndexChanged.connect(self._on_item_changed)
        self.quantity.valueChanged.connect(self._on_quantity_changed)

        remove_button = QPushButton('×')
        remove_button.setFixedWidth(24)
        remove_button.setToolTip('Remove this item')
        remove_button.clicked.connect(self._on_remove_clicked)
        layout.addWidget(remove_button)

    def _on_remove_clicked(self) -> None:
        self._owner.remove_slot(self.index)

    @property
    def current_item_id(self) -> int:
        """The item id this row's picker currently shows. Read through here
        rather than QComboBox.currentData(): the ids live in a parallel list
        (see __init__) instead of as per-entry Qt user data."""
        return self._item_ids[self.combo.currentIndex()]

    def set_current_item_id(self, item_id: int) -> None:
        """Select `item_id` in this row's picker, as a user click would."""
        self.combo.setCurrentIndex(self._item_ids.index(item_id))

    def _apply_quantity_range(self, slot: InventorySlot) -> None:
        if is_stackable(slot.item_id):
            self.quantity.setRange(1, 99)
            self.quantity.setValue(max(1, slot.quantity))
            self.quantity.setEnabled(True)
        else:
            self.quantity.setRange(0, 0)
            self.quantity.setValue(0)
            self.quantity.setEnabled(False)

    def _on_item_changed(self, combo_index: int) -> None:
        item_id = self._item_ids[combo_index]
        self._owner.set_slot_item(self.index, item_id)
        self._apply_quantity_range(self._owner.slot_at(self.index))

    def _on_quantity_changed(self, value: int) -> None:
        self._owner.set_slot_quantity(self.index, value)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(_DRAG_MIME_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        source_index = int(bytes(event.mimeData().data(_DRAG_MIME_TYPE)).decode('ascii'))
        insert_after = event.position().y() > self.height() / 2
        self._owner.move_slot(source_index, self.index, insert_after)
        event.acceptProposedAction()


class InventoryEditorWidget(QWidget):
    """Single-column, in-game-order list editor for the paired inventory
    item-ID and quantity arrays."""

    def __init__(self, item_bytes: bytes, quantity_bytes: bytes, parent=None):
        super().__init__(parent)
        self._original_item_bytes = bytes(item_bytes)
        self._original_quantity_bytes = bytes(quantity_bytes)
        self._real_slot_count = real_slot_count(item_bytes)
        self._slots: list[InventorySlot] = decode_slots(item_bytes, quantity_bytes)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(1)
        outer_layout.addLayout(self._rows_layout)

        self._add_button = QPushButton('+ Add Item')
        self._add_button.clicked.connect(self._on_add_clicked)
        outer_layout.addWidget(self._add_button)

        self._capacity_label = QLabel()
        self._capacity_label.setEnabled(False)
        outer_layout.addWidget(self._capacity_label)

        self._rebuild_rows()

    def item_bytes(self) -> bytes:
        return encode_slots(self._slots, self._original_item_bytes, self._original_quantity_bytes)[0]

    def quantity_bytes(self) -> bytes:
        return encode_slots(self._slots, self._original_item_bytes, self._original_quantity_bytes)[1]

    def slot_at(self, index: int) -> InventorySlot:
        return self._slots[index]

    def set_slot_item(self, index: int, item_id: int) -> None:
        self._slots[index].item_id = item_id

    def set_slot_quantity(self, index: int, quantity: int) -> None:
        self._slots[index].quantity = quantity

    def remove_slot(self, index: int) -> None:
        del self._slots[index]
        self._rebuild_rows()

    def move_slot(self, source_index: int, target_index: int, insert_after: bool) -> None:
        if source_index == target_index:
            return
        destination = target_index + 1 if insert_after else target_index
        if source_index < destination:
            destination -= 1
        destination = max(0, min(destination, len(self._slots) - 1))
        self._slots = reorder(self._slots, source_index, destination)
        self._rebuild_rows()

    def _on_add_clicked(self) -> None:
        if len(self._slots) >= self._real_slot_count:
            return
        self._slots.append(InventorySlot(_ITEM_IDS[0], 1))
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for index, slot in enumerate(self._slots):
            self._rows_layout.addWidget(_InventoryRow(self, index, slot))

        at_capacity = len(self._slots) >= self._real_slot_count
        self._add_button.setEnabled(not at_capacity)
        self._capacity_label.setText(f"{len(self._slots)} / {self._real_slot_count} slots used")
