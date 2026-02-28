from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class ChangeLocationFromMemMenu(BaseCommandMenu):
    """Menu for changing location using memory addresses (command 0xE2)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        location_label = QLabel("Location Address (7F0200-7F0400)")
        self.location_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.location_addr.setText("7F0200")
        
        x_label = QLabel("X Coordinate Address (7F0200-7F0400)")
        self.x_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.x_addr.setText("7F0200")
        
        y_label = QLabel("Y Coordinate Address (7F0200-7F0400)")
        self.y_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.y_addr.setText("7F0200")
        
        facing_label = QLabel("Facing Address (7F0200-7F0400)")
        self.facing_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.facing_addr.setText("7F0200")
        
        layout.addWidget(location_label)
        layout.addWidget(self.location_addr)
        layout.addWidget(x_label)
        layout.addWidget(self.x_addr)
        layout.addWidget(y_label)
        layout.addWidget(self.y_addr)
        layout.addWidget(facing_label)
        layout.addWidget(self.facing_addr)
        
        result.setLayout(layout)
        return result
    
    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid memory addresses")
            
        return EventCommand.generic_command(0xE2,
                                         (self.location_addr.get_value() - 0x7F0200) // 2,
                                         (self.x_addr.get_value() - 0x7F0200) // 2,
                                         (self.y_addr.get_value() - 0x7F0200) // 2,
                                         (self.facing_addr.get_value() - 0x7F0200) // 2)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 4:
            self.location_addr.setText("{:06X}".format(args[0]*2 + 0x7F0200))
            self.x_addr.setText("{:06X}".format(args[1]*2 + 0x7F0200))
            self.y_addr.setText("{:06X}".format(args[2]*2 + 0x7F0200))
            self.facing_addr.setText("{:06X}".format(args[3]*2 + 0x7F0200))