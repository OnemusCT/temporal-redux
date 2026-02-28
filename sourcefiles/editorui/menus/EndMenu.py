from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class EndMenu(BaseCommandMenu):
    """Menu for end/return/break commands"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        end_label = QLabel("End Type:")
        self.end_type = QComboBox()
        self.end_type.addItem("Return")
        self.end_type.addItem("Break")
        self.end_type.addItem("End")
        
        layout.addWidget(end_label)
        layout.addWidget(self.end_type)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        if self.end_type.currentIndex() == 0:
            return EventCommand.return_cmd()
        elif self.end_type.currentIndex() == 1:
            return EventCommand.break_cmd()
        else:
            return EventCommand.end_cmd()

    def apply_arguments(self, command: int, args: list):
        if command == 0x00:
            self.end_type.setCurrentIndex(0)
        elif command == 0xB1:
            self.end_type.setCurrentIndex(1)
        elif command == 0xB2:
            self.end_type.setCurrentIndex(2)
