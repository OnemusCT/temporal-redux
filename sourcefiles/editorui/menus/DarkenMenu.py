from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class DarkenMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        amount_label = QLabel("Darken Amount")
        amount_label.setObjectName("Amount")
        self.amount = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(amount_label)
        layout.addWidget(self.amount)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.darken(self.amount.get_value())
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.amount.set_value(args[0])
