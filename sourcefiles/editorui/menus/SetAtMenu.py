from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class SetAtMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Bit pattern selection
        bit_label = QLabel("Bit to Set at 7E0154")
        self.bit_pattern = QComboBox()
        self.bit_pattern.addItem("0x04", 0x04)
        self.bit_pattern.addItem("0x08", 0x08)
        self.bit_pattern.addItem("0x10", 0x10)

        layout.addWidget(bit_label)
        layout.addWidget(self.bit_pattern)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return True  # Always valid since using combobox with fixed values

    def get_command(self) -> EventCommand:
        pattern = self.bit_pattern.currentData()
        return EventCommand.set_bit_at_0x7E0154(pattern)

    def apply_arguments(self, command: int, args: list):
        # Map commands to their bit patterns
        pattern_map = {
            0x2A: 0x04,
            0x2B: 0x08,
            0x32: 0x10
        }
        
        if command in pattern_map:
            # Find the index in combobox for this bit pattern
            index = self.bit_pattern.findData(pattern_map[command])
            if index >= 0:
                self.bit_pattern.setCurrentIndex(index)