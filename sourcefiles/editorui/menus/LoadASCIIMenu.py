from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadASCIIMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        index_label = QLabel("ASCII Index")
        self.index = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(index_label)
        layout.addWidget(self.index)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            index = int(self.index.text(), 16)
            return EventCommand.load_ascii(index)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.index.setText(f"{args[0]:02X}")