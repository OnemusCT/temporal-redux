from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SetStorylineMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        value_label = QLabel("Storyline Value")
        self.value = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.value.setPlaceholderText("Enter value (0-FF)")

        layout.addWidget(value_label)
        layout.addWidget(self.value)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        if self.value.get_value() is None:
            return False
        return True

    def get_command(self) -> EventCommand:
        value = self.value.get_value()
        if value is None:
            raise CommandError("Invalid storyline value")
        return EventCommand.set_storyline_counter(value)

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.value.set_value(args[0])