from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

class CheckStorylineMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Storyline value input
        value_label = QLabel("Storyline Value:")
        self.storyline_value = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(value_label)
        layout.addWidget(self.storyline_value)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        storyline_val = self.storyline_value.get_value()
        return EventCommand.if_storyline_counter_lt(storyline_val, 0)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.storyline_value.set_value(args[0])