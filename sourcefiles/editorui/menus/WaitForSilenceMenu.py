from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QFormLayout, QWidget


class WaitForSilenceMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.combo = QComboBox()
        self.combo.addItems(["Total silence", "Song end"])
        layout.addRow("Waiting for...", self.combo)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        opcode = 0xED if self.combo.currentIndex() == 0 else 0xEE
        return EventCommand.generic_zero_arg(opcode)

    def apply_arguments(self, command: int, args: list):
        self.combo.setCurrentIndex(0 if command == 0xED else 1)
