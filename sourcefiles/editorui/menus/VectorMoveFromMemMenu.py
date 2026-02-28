from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class VectorMoveFromMemMenu(BaseCommandMenu):
    """Menu for vector movement using memory addresses (command 0x9D)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        dir_label = QLabel("Direction Address (7F0200-7F0400)")
        self.dir_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.dir_addr.setText("7F0200")
        
        mag_label = QLabel("Magnitude Address (7F0200-7F0400)")
        self.mag_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.mag_addr.setText("7F0200")
        
        layout.addWidget(dir_label)
        layout.addWidget(self.dir_addr)
        layout.addWidget(mag_label)
        layout.addWidget(self.mag_addr)
        
        result.setLayout(layout)
        return result
    
    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid memory addresses")
        return EventCommand.generic_command(0x9D, 
                                         (self.dir_addr.get_value() - 0x7F0200) // 2,
                                         (self.mag_addr.get_value() - 0x7F0200) // 2)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.dir_addr.setText("{:06X}".format(args[0]*2 + 0x7F0200))
            self.mag_addr.setText("{:06X}".format(args[1]*2 + 0x7F0200))
