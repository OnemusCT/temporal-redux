from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class ScrollScreenMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        x_label = QLabel("X Coordinate")
        x_label.setObjectName("X")
        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        y_label = QLabel("Y Coordinate")
        y_label.setObjectName("Y")
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(x_label)
        layout.addWidget(self.x_coord)
        layout.addWidget(y_label)
        layout.addWidget(self.y_coord)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.scroll_screen(
            self.x_coord.get_value(),
            self.y_coord.get_value()
        )
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.x_coord.set_value(args[0])
            self.y_coord.set_value(args[1])
