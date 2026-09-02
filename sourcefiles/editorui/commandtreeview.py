from PyQt6.QtWidgets import QTreeView, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, QModelIndex
from PyQt6.QtGui import (QMouseEvent, QDrag, QDragMoveEvent, QDragEnterEvent, 
                        QDropEvent, QPainter, QColor, QPen)

class CommandTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)  # We'll handle this ourselves
        self.setDragDropMode(QTreeView.DragDropMode.InternalMove)
        self.setSelectionMode(QTreeView.SelectionMode.ExtendedSelection)
        self.drag_start_position = None
        self.drop_indicator_rect = None
        self.drop_indicator_position = None
        self.current_drop_index = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if not self.drag_start_position:
            return

        # Convert current position to QPoint
        current_pos = event.position().toPoint()
        
        # Check if the mouse has moved far enough to start a drag
        distance = (current_pos - self.drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return

        # Only start drag if we're on a valid index
        index = self.indexAt(self.drag_start_position)
        if not index.isValid():
            return

        # Get all selected indexes for the drag operation
        selected_indexes = [idx for idx in self.selectedIndexes() if idx.column() == 0]
        if not selected_indexes:
            return

        # Create and execute the drag operation
        drag = QDrag(self)
        mime_data = self.model().mimeData(selected_indexes)
        drag.setMimeData(mime_data)
        
        # Execute drag
        drag.exec(Qt.DropAction.MoveAction)
        
        # Clear drop indicator when drag ends
        self.clearDropIndicator()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept the drag enter event if it's our format"""
        if event.mimeData().hasFormat('application/x-commanditem'):
            event.accept()
        else:
            event.ignore()
        self.clearDropIndicator()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move to show drop indicators"""
        if not event.mimeData().hasFormat('application/x-commanditem'):
            event.ignore()
            self.clearDropIndicator()
            return

        # Get the index where we're hovering
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        
        if not index.isValid():
            event.ignore()
            self.clearDropIndicator()
            return

        # Update drop indicator
        self.updateDropIndicator(pos, index)
        
        # Check if drop would be valid
        if self.model().canDropMimeData(event.mimeData(), 
                                      Qt.DropAction.MoveAction,
                                      -1, 0, index):
            event.accept()
        else:
            event.ignore()
            self.clearDropIndicator()

    def dragLeaveEvent(self, event):
        """Clear drop indicator when drag leaves the widget"""
        self.clearDropIndicator()
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        """Handle the actual drop event"""
        if not event.mimeData().hasFormat('application/x-commanditem'):
            event.ignore()
            return

        # Get the index where we're dropping
        drop_index = self.indexAt(event.position().toPoint())
        
        if not drop_index.isValid():
            event.ignore()
            return

        # Handle the drop in the model
        if self.model().dropMimeData(event.mimeData(),
                                   Qt.DropAction.MoveAction,
                                   -1, 0, drop_index):
            event.accept()
        else:
            event.ignore()

        # Clear the drop indicator
        self.clearDropIndicator()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_start_position = None
        super().mouseReleaseEvent(event)

    def updateDropIndicator(self, pos: QPoint, index: QModelIndex):
        """Update the drop indicator position"""
        rect = self.visualRect(index)
        
        self.drop_indicator_rect = QRect(0, rect.bottom(), self.viewport().width(), 2)
        self.drop_indicator_position = "below"
            
        self.current_drop_index = index
        self.viewport().update()

    def clearDropIndicator(self):
        """Clear the drop indicator"""
        self.drop_indicator_rect = None
        self.drop_indicator_position = None
        self.current_drop_index = None
        self.viewport().update()

    def paintEvent(self, event):
        """Paint the tree view and drop indicator"""
        super().paintEvent(event)
        
        # Paint drop indicator if it exists
        if self.drop_indicator_rect:
            painter = QPainter(self.viewport())
            painter.save()
            
            # Set up the pen for drawing
            pen = QPen(QColor(0, 120, 215))  # Use a blue color
            pen.setWidth(2)
            painter.setPen(pen)
            
            # Draw the line
            painter.drawLine(
                self.drop_indicator_rect.left(), 
                self.drop_indicator_rect.top(),
                self.drop_indicator_rect.right(), 
                self.drop_indicator_rect.top()
            )
            
            painter.restore()