from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class WaitForAddMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # No parameters needed for wait
        label = QLabel("Wait for color addition effect to complete")
        layout.addWidget(label)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.wait_for_brighten()