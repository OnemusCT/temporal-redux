from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class SetObjectCoordFromMemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Memory addresses
        x_label = QLabel("Load X From Address")
        x_label.setObjectName("X Address")
        self.x_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        y_label = QLabel("Load Y From Address")
        y_label.setObjectName("Y Address")
        self.y_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        layout.addWidget(x_label)
        layout.addWidget(self.x_addr)
        layout.addWidget(y_label)
        layout.addWidget(self.y_addr)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        return EventCommand.set_own_coordinates_from_mem(
            self.x_addr.get_value(),
            self.y_addr.get_value()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.x_addr.set_value(0x7F0200 + (args[0] * 2))
            self.y_addr.set_value(0x7F0200 + (args[1] * 2))