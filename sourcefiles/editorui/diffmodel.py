"""Qt model for displaying a side-by-side event diff."""
from __future__ import annotations

from enum import IntEnum
from typing import Any, Optional

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from editorui.eventdiff import (
    CopyEligibility,
    DiffLine,
    DiffStatus,
    eligibility_reason,
    FunctionDiff,
    LocationDiff,
)


class DiffColumn(IntEnum):
    LEFT_ADDRESS = 0
    LEFT_COMMAND = 1
    STATUS = 2
    RIGHT_ADDRESS = 3
    RIGHT_COMMAND = 4


_COLUMN_HEADERS = ["Address", "Left Command", "", "Address", "Right Command"]

# Background colors
_COLOR_EQUAL = QColor(240, 255, 240)         # light green
_COLOR_MODIFIED = QColor(255, 255, 220)      # light yellow
_COLOR_LEFT_ONLY = QColor(255, 230, 230)     # light pink
_COLOR_RIGHT_ONLY = QColor(230, 230, 255)    # light blue
_COLOR_NON_COPYABLE = QColor(230, 230, 230)  # light gray
_COLOR_TEXT = QColor(0, 0, 0)                # black text for readability


_STATUS_BACKGROUND: dict[DiffStatus, QColor] = {
    DiffStatus.EQUAL: _COLOR_EQUAL,
    DiffStatus.MODIFIED: _COLOR_MODIFIED,
    DiffStatus.LEFT_ONLY: _COLOR_LEFT_ONLY,
    DiffStatus.RIGHT_ONLY: _COLOR_RIGHT_ONLY,
}

_STATUS_SYMBOL: dict[DiffStatus, str] = {
    DiffStatus.EQUAL: "=",
    DiffStatus.MODIFIED: "~",
    DiffStatus.LEFT_ONLY: "<",
    DiffStatus.RIGHT_ONLY: ">",
}


class _InternalNode:
    """Wrapper stored as internalPointer for QModelIndex."""
    pass


class _FunctionNode(_InternalNode):
    """Top-level row: one per FunctionDiff."""
    __slots__ = ("func_diff", "row", "line_nodes")

    def __init__(self, func_diff: FunctionDiff, row: int):
        self.func_diff = func_diff
        self.row = row
        self.line_nodes: list[_LineNode] = []


class _LineNode(_InternalNode):
    """Child row: one per DiffLine within a FunctionDiff."""
    __slots__ = ("diff_line", "parent", "row")

    def __init__(self, diff_line: DiffLine, parent: _FunctionNode, row: int):
        self.diff_line = diff_line
        self.parent = parent
        self.row = row


class DiffModel(QAbstractItemModel):
    """Two-level tree model: FunctionDiff headers -> DiffLine rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diff: Optional[LocationDiff] = None
        self._func_nodes: list[_FunctionNode] = []

    def set_diff(self, diff: LocationDiff) -> None:
        """Replace the displayed diff and refresh views."""
        self.beginResetModel()
        self._diff = diff
        self._build_nodes()
        self.endResetModel()

    @property
    def location_diff(self) -> Optional[LocationDiff]:
        return self._diff

    def get_diff_line(self, index: QModelIndex) -> Optional[DiffLine]:
        """Return the DiffLine for a child index, or None for headers."""
        if not index.isValid():
            return None
        node = index.internalPointer()
        if isinstance(node, _LineNode):
            return node.diff_line
        return None

    def get_function_diff(self, index: QModelIndex) -> Optional[FunctionDiff]:
        """Return the FunctionDiff for a header index."""
        if not index.isValid():
            return None
        node = index.internalPointer()
        if isinstance(node, _FunctionNode):
            return node.func_diff
        return None

    def _build_nodes(self) -> None:
        self._func_nodes = []
        if self._diff is None:
            return
        for i, fd in enumerate(self._diff.functions):
            fn = _FunctionNode(func_diff=fd, row=i)
            fn.line_nodes = []
            for j, dl in enumerate(fd.lines):
                fn.line_nodes.append(_LineNode(diff_line=dl, parent=fn, row=j))
            self._func_nodes.append(fn)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() != 0:
            return 0
        if not parent.isValid():
            return len(self._func_nodes)
        node = parent.internalPointer()
        if isinstance(node, _FunctionNode):
            return len(node.line_nodes)
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_COLUMN_HEADERS)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            if row < len(self._func_nodes):
                return self.createIndex(row, column, self._func_nodes[row])
            return QModelIndex()
        node = parent.internalPointer()
        if isinstance(node, _FunctionNode) and row < len(node.line_nodes):
            return self.createIndex(row, column, node.line_nodes[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        if isinstance(node, _LineNode):
            return self.createIndex(node.parent.row, 0, node.parent)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        node = index.internalPointer()
        col = index.column()

        if isinstance(node, _FunctionNode):
            fd = node.func_diff
            if role == Qt.ItemDataRole.DisplayRole:
                if col == DiffColumn.LEFT_COMMAND:
                    return f"Object {fd.object_index:02X} / {fd.function_name}"
                return None
            if role == Qt.ItemDataRole.BackgroundRole:
                if fd.is_identical:
                    return _COLOR_EQUAL
                return _COLOR_MODIFIED
            if role == Qt.ItemDataRole.ForegroundRole:
                return _COLOR_TEXT
            return None

        if not isinstance(node, _LineNode):
            return None
        dl = node.diff_line

        if role == Qt.ItemDataRole.DisplayRole:
            if col == DiffColumn.LEFT_ADDRESS:
                return f"0x{dl.left_address:04X}" if dl.left_address is not None else ""
            if col == DiffColumn.LEFT_COMMAND:
                return dl.left_name if dl.left is not None else ""
            if col == DiffColumn.STATUS:
                return _STATUS_SYMBOL.get(dl.status, "")
            if col == DiffColumn.RIGHT_ADDRESS:
                return f"0x{dl.right_address:04X}" if dl.right_address is not None else ""
            if col == DiffColumn.RIGHT_COMMAND:
                return dl.right_name if dl.right is not None else ""
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            return _STATUS_BACKGROUND.get(dl.status, None)

        if role == Qt.ItemDataRole.ForegroundRole:
            return _COLOR_TEXT

        if role == Qt.ItemDataRole.ToolTipRole:
            tips = []
            if dl.copy_left_to_right != CopyEligibility.ALLOWED:
                tips.append(f"Left->Right: {eligibility_reason(dl.copy_left_to_right)}")
            if dl.copy_right_to_left != CopyEligibility.ALLOWED:
                tips.append(f"Right->Left: {eligibility_reason(dl.copy_right_to_left)}")
            return "\n".join(tips) if tips else None

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(_COLUMN_HEADERS):
                return _COLUMN_HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


