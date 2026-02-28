from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResultMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        addr_label = QLabel("Store To Address")
        self.addr = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)
        self.addr.setPlaceholderText("Enter address (e.g. 7F0200)")

        layout.addWidget(addr_label)
        layout.addWidget(self.addr)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        if self.addr.get_value() is None:
            return False
        return True

    def get_command(self) -> EventCommand:
        addr = self.addr.get_value()
        if addr is None:
            raise CommandError("Invalid address value")
        return EventCommand.get_result(addr)

    def apply_arguments(self, command: int, args: list):
        if len(args) == 0:
            return

        if command == 0x19:  # Script memory
            addr = 0x7F0200 + (args[0] * 2)
        else:  # 0x1C - Local memory
            addr = 0x7F0000 + args[0]

        self.addr.set_value(addr)