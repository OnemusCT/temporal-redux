from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GetResultMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        addr_label = QLabel("Store To Address")
        self.addr = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)

        layout.addWidget(addr_label)
        layout.addWidget(self.addr)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            addr = int(self.addr.text(), 16)
            return EventCommand.get_result(addr)
        except ValueError as e:
            print(f"ERROR: {e}")

    def apply_arguments(self, command: int, args: list):
        if len(args) == 0:
            return

        if command == 0x19:  # Script memory
            addr = 0x7F0200 + (args[0] * 2)
        else:  # 0x1C - Local memory
            addr = 0x7F0000 + args[0]

        self.addr.setText(f"{addr:06X}")