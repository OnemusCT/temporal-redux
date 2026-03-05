"""QGraphicsView for displaying and interacting with the map.

Handles:
  - Displaying the rendered QImage (via QGraphicsPixmapItem)
  - Left-click to paste/paint tiles
  - Right-click to copy (select) a tile
  - Rubber-band selection for area copy/paste
  - Mouse coordinate tracking
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QRubberBand,
)
from PyQt6.QtGui import QPixmap, QImage, QCursor, QPainter
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal


class MapGraphicsView(QGraphicsView):
    """Interactive view for a rendered map image."""

    # Emits (tile_x, tile_y) on mouse move
    tile_hovered = pyqtSignal(int, int)
    # Emits (tile_x, tile_y) on left-click -> paint
    tile_painted = pyqtSignal(int, int)
    # Emits (tile_x, tile_y) on right-click -> pick
    tile_picked = pyqtSignal(int, int)
    # Emits (x, y, w, h) on completed rubber-band selection
    region_selected = pyqtSignal(int, int, int, int)

    TILE_SIZE = 16

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._rb_origin = QPoint()
        self._selecting = False
        self._current_img: QImage | None = None

    def set_image(self, img: QImage) -> None:
        """Display a new rendered map image."""
        self._current_img = img
        pixmap = QPixmap.fromImage(img)
        self._item.setPixmap(pixmap)
        self._scene.setSceneRect(0, 0, img.width(), img.height())

    def clear(self) -> None:
        self._item.setPixmap(QPixmap())
        self._current_img = None

    def _scene_pos_to_tile(self, view_pos: QPoint) -> tuple[int, int]:
        sp = self.mapToScene(view_pos)
        return int(sp.x()) // self.TILE_SIZE, int(sp.y()) // self.TILE_SIZE

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            tx, ty = self._scene_pos_to_tile(event.pos())
            self.tile_painted.emit(tx, ty)
            # Start rubber-band for area selection (Shift+Left)
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._rb_origin = event.pos()
                self._rubber_band.setGeometry(QRect(self._rb_origin, QSize()))
                self._rubber_band.show()
                self._selecting = True
        elif event.button() == Qt.MouseButton.RightButton:
            tx, ty = self._scene_pos_to_tile(event.pos())
            self.tile_picked.emit(tx, ty)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        tx, ty = self._scene_pos_to_tile(event.pos())
        self.tile_hovered.emit(tx, ty)
        if self._selecting:
            self._rubber_band.setGeometry(
                QRect(self._rb_origin, event.pos()).normalized()
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._selecting = False
            self._rubber_band.hide()
            rb_rect = QRect(self._rb_origin, event.pos()).normalized()
            # Map view-rect corners to scene, then to tile coords
            sp1 = self.mapToScene(rb_rect.topLeft())
            sp2 = self.mapToScene(rb_rect.bottomRight())
            tx1 = int(sp1.x()) // self.TILE_SIZE
            ty1 = int(sp1.y()) // self.TILE_SIZE
            tx2 = int(sp2.x()) // self.TILE_SIZE
            ty2 = int(sp2.y()) // self.TILE_SIZE
            w = max(1, tx2 - tx1 + 1)
            h = max(1, ty2 - ty1 + 1)
            self.region_selected.emit(tx1, ty1, w, h)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        """Ctrl+wheel zooms."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)
