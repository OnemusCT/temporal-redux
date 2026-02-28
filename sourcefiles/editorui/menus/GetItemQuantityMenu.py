from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GetItemQuantityMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        item_label = QLabel("Item ID")
        self.item_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        addr_label = QLabel("Store To Address")
        self.store_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        layout.addWidget(item_label)
        layout.addWidget(self.item_id)
        layout.addWidget(addr_label)
        layout.addWidget(self.store_addr)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            item_id = int(self.item_id.text(), 16)
            store_addr = int(self.store_addr.text(), 16)
            return EventCommand.get_item_quantity(item_id, store_addr)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.item_id.setText(f"{args[0]:02X}")
            self.store_addr.setText(f"{0x7F0200 + args[1]*2:06X}")