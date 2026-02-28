from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GetStoryCtrMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        addr_label = QLabel("Destination (7F0200-7F0400)")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.addr.setText("7F0200")

        layout.addWidget(addr_label)
        layout.addWidget(self.addr)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            addr = int(self.addr.text(), 16)
            return EventCommand.get_storyline(addr)
        except ValueError as e:
            print(e)

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.addr.setText("{:02X}".format(args[0]*2 + 0x7F0200))