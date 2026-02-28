from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class GetPC1Menu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        address_label = QLabel("Destination Address")
        self.address = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        layout.addWidget(address_label)
        layout.addWidget(self.address)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            address = int(self.address.text(), 16)
            return EventCommand.get_pc1(address)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.address.setText("{:02X}".format(args[0]*2 + 0x7F0200))