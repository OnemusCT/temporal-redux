from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class HPMPMenu(BaseCommandMenu):
    """Menu for HP/MP restoration commands"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        restore_label = QLabel("Restore:")
        self.restore_type = QComboBox()
        self.restore_type.addItem("HP and MP")
        self.restore_type.addItem("HP Only")
        self.restore_type.addItem("MP Only")
        
        layout.addWidget(restore_label)
        layout.addWidget(self.restore_type)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        if self.restore_type.currentIndex() == 0:
            return EventCommand.generic_zero_arg(0xF8)  # Restore both
        elif self.restore_type.currentIndex() == 1:
            return EventCommand.generic_zero_arg(0xF9)  # Restore HP
        else:
            return EventCommand.generic_zero_arg(0xFA)  # Restore MP

    def apply_arguments(self, command: int, args: list):
        if command == 0xF8:
            self.restore_type.setCurrentIndex(0)
        elif command == 0xF9:
            self.restore_type.setCurrentIndex(1)
        elif command == 0xFA:
            self.restore_type.setCurrentIndex(2)
