from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class ShakeScreenMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        self.enabled = QCheckBox("Enable Screen Shake")
        layout.addWidget(self.enabled)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.shake_screen(self.enabled.isChecked())
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.enabled.setChecked(args[0] != 0)
