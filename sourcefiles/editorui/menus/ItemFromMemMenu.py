from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ItemFromMemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        addr_label = QLabel("Item ID Address")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        layout.addWidget(addr_label)
        layout.addWidget(self.addr)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            addr = int(self.addr.text(), 16)
            return EventCommand.add_item_from_mem(addr)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.addr.setText(f"{0x7F0200 + args[0]*2:06X}")