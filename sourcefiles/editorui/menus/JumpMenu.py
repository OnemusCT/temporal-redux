from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class JumpMenu(BaseCommandMenu):
    """Menu for NPC jump command (0x7A)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        x_label = QLabel("X Coordinate")
        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        y_label = QLabel("Y Coordinate")
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        height_label = QLabel("Jump Height/Speed")
        self.height = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(x_label)
        layout.addWidget(self.x_coord)
        layout.addWidget(y_label)
        layout.addWidget(self.y_coord)
        layout.addWidget(height_label)
        layout.addWidget(self.height)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid jump parameters")
            
        return EventCommand.generic_command(0x7A,
                                          self.x_coord.get_value(),
                                          self.y_coord.get_value(),
                                          self.height.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 3:
            self.x_coord.set_value(args[0])
            self.y_coord.set_value(args[1])
            self.height.set_value(args[2])
