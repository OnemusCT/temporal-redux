from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, FuncSync

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

class ActivateMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        self.active = QCheckBox("Object Active")
        layout.addWidget(self.active)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        return EventCommand.generic_zero_arg(0x09 if self.active.isChecked() else 0x08)
        
    def apply_arguments(self, command: int, args: list):
        self.active.setChecked(command == 0x09)
