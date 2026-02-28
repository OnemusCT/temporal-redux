from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CheckResultMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Result value input
        value_label = QLabel("Result Value:")
        self.result_value = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(value_label)
        layout.addWidget(self.result_value)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        result_val = self.result_value.get_value()
        return EventCommand.if_result_equals(result_val, 0)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.result_value.set_value(args[0])
