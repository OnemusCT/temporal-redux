"""Tile palette selector widget.

Displays all 16x16 tiles for the current tileset in a scrollable grid.
The user left-clicks a tile to select it (painted into the map),
or right-clicks to copy the tile under the cursor.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QScrollArea, QLabel, QVBoxLayout
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt6.QtCore import Qt, QPoint, pyqtSignal


class TilePaletteWidget(QScrollArea):
    """Scrollable tile palette. Emits tile_selected(tile_index)."""

    tile_selected = pyqtSignal(int)

    TILE_SIZE = 16
    COLS = 16

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._selected_idx = 0
        self._num_tiles = 0

        self._canvas = _PaletteCanvas(self)
        self._canvas.tile_clicked.connect(self._on_tile_clicked)
        self.setWidget(self._canvas)
        self.setWidgetResizable(False)

    def set_palette_image(self, img, num_tiles: int) -> None:
        """Update the palette display from a QImage of the tile grid."""
        self._num_tiles = num_tiles
        self._pixmap = QPixmap.fromImage(img)
        self._canvas.set_pixmap(self._pixmap, num_tiles, self.COLS, self.TILE_SIZE)
        self._canvas.set_selection(self._selected_idx)

    def set_selected_tile(self, idx: int) -> None:
        self._selected_idx = idx
        self._canvas.set_selection(idx)

    def _on_tile_clicked(self, idx: int) -> None:
        self._selected_idx = idx
        self._canvas.set_selection(idx)
        self.tile_selected.emit(idx)


class _PaletteCanvas(QWidget):
    """Internal widget that draws the tile grid and selection highlight."""

    tile_clicked = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._num_tiles = 0
        self._cols = 16
        self._tile_size = 16
        self._selected = 0

    def set_pixmap(self, pixmap: QPixmap, num_tiles: int,
                   cols: int, tile_size: int) -> None:
        self._pixmap = pixmap
        self._num_tiles = num_tiles
        self._cols = cols
        self._tile_size = tile_size
        rows = (num_tiles + cols - 1) // cols
        self.setFixedSize(cols * tile_size, rows * tile_size)
        self.update()

    def set_selection(self, idx: int) -> None:
        self._selected = idx
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        if not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)
        # Draw selection highlight
        col = self._selected % self._cols
        row = self._selected // self._cols
        pen = QPen(QColor(255, 255, 0), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(
            col * self._tile_size,
            row * self._tile_size,
            self._tile_size - 1,
            self._tile_size - 1,
        )

    def mousePressEvent(self, event) -> None:
        if event.button() in (Qt.MouseButton.LeftButton,
                               Qt.MouseButton.RightButton):
            col = event.pos().x() // self._tile_size
            row = event.pos().y() // self._tile_size
            idx = row * self._cols + col
            if 0 <= idx < self._num_tiles:
                self.tile_clicked.emit(idx)
        super().mousePressEvent(event)
