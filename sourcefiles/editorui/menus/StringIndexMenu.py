from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class StringIndexMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        addr_label = QLabel("ROM Address")
        self.address = ValidatingLineEdit(min_value=0, max_value=0xFFFFFF)

        layout.addWidget(addr_label)
        layout.addWidget(self.address)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            address = int(self.address.text(), 16)
            return EventCommand.string_index(address)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.address.setText(f"{args[0]:06X}")