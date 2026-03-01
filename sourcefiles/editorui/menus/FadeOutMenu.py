from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class FadeOutMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # No parameters needed for fade out
        label = QLabel("Fade out screen")
        layout.addWidget(label)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.fade_screen()

    def apply_arguments(self, command: int, args: list):
        pass