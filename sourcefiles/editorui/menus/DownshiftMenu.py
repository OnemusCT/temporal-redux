from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DownshiftMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Address input
        addr_label = QLabel("Memory Address (7F0200-7F0400)")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        # Shift amount input
        shift_label = QLabel("Shift Amount (0-7)")
        self.shift = ValidatingLineEdit(min_value=0, max_value=7)

        layout.addWidget(addr_label)
        layout.addWidget(self.addr)
        layout.addWidget(shift_label)
        layout.addWidget(self.shift)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return self.addr.get_value() is not None and self.shift.get_value() is not None

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        return EventCommand.shift_bits(self.addr.get_value(), self.shift.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return
            
        # First arg is shift amount, second is memory offset
        shift_amount = args[0]
        addr = 0x7F0200 + (args[1] * 2)
        
        self.shift.set_value(shift_amount)
        self.addr.set_value(addr)