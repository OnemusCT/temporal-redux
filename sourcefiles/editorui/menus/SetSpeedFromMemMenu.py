from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class SetSpeedFromMemMenu(BaseCommandMenu):
    """Menu for setting speed from a memory address (command 0x8A)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        addr_label = QLabel("Speed Address (7F0200-7F0400)")
        self.speed_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.speed_addr.setText("7F0200")
        
        layout.addWidget(addr_label)
        layout.addWidget(self.speed_addr)
        
        result.setLayout(layout)
        return result
    
    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid speed memory address")
        return EventCommand.set_speed_from_mem(self.speed_addr.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.speed_addr.setText("{:06X}".format(args[0]*2 + 0x7F0200))
