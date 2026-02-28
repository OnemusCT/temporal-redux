from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget
     
class GotoMenu(BaseCommandMenu):
    """Menu for forward/backward jump commands"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        type_label = QLabel("Jump Type:")
        self.jump_type = QComboBox()
        self.jump_type.addItem("Forward")
        self.jump_type.addItem("Backward")
        
        bytes_label = QLabel("Jump Bytes:")
        self.jump_bytes = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(type_label)
        layout.addWidget(self.jump_type)
        layout.addWidget(bytes_label)
        layout.addWidget(self.jump_bytes)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        jump_bytes = self.jump_bytes.get_value()
        if self.jump_type.currentIndex() == 0:
            return EventCommand.jump_forward(jump_bytes)
        else:
            return EventCommand.jump_back(jump_bytes)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            if command == 0x10:
                self.jump_type.setCurrentIndex(0)
            else:
                self.jump_type.setCurrentIndex(1)
            self.jump_bytes.set_value(args[0])