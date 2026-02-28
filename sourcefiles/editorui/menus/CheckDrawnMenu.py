from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class CheckDrawnMenu(BaseCommandMenu):
    """Menu for checking if an object is visible"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        obj_label = QLabel("Object ID:")
        self.obj_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(obj_label)
        layout.addWidget(self.obj_id)
        
        result.setLayout(layout)
        return result
    
    def get_command(self) -> EventCommand:
        obj_id = self.obj_id.get_value()

        if obj_id is None:
            raise CommandError("Invalid input")

        return EventCommand.check_drawn(obj_id, 0)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.obj_id.set_value(args[0])
