from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class SetFacingFromMemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        addr_label = QLabel("Load From Address")
        addr_label.setObjectName("Address")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        layout.addWidget(addr_label)
        layout.addWidget(self.addr)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.generic_command(
            0xA7,
            (self.addr.get_value() - 0x7F0200) // 2
        )
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.addr.set_value(0x7F0200 + (args[0] * 2))