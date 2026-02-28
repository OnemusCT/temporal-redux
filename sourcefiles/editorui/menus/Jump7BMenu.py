from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
   
class Jump7BMenu(BaseCommandMenu):
    """Menu for alternate jump command (0x7B)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Create 4 generic parameter inputs
        self.params = []
        for i in range(4):
            label = QLabel(f"Parameter {i+1}")
            param = ValidatingLineEdit(min_value=0, max_value=0xFF)
            self.params.append(param)
            layout.addWidget(label)
            layout.addWidget(param)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid parameters")
            
        return EventCommand.generic_command(0x7B,
                                          self.params[0].get_value(),
                                          self.params[1].get_value(),
                                          self.params[2].get_value(),
                                          self.params[3].get_value())

    def apply_arguments(self, command: int, args: list):
        for i in range(min(len(args), 4)):
            self.params[i].set_value(args[i])