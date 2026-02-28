from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CheckGoldMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        amount_label = QLabel("Gold Amount")
        self.amount = ValidatingLineEdit(min_value=0, max_value=0xFFFF)

        layout.addWidget(amount_label)
        layout.addWidget(self.amount)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            amount = int(self.amount.text(), 16)
            return EventCommand.check_gold(amount, 0)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.amount.setText(f"{args[0]:04X}")