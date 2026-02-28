from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AnimationLimiterMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        limit_label = QLabel("Animation Limit")
        self.limit = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(limit_label)
        layout.addWidget(self.limit)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            limit = int(self.limit.text(), 16)
            return EventCommand.animation_limiter(limit)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.limit.setText(f"{args[0]:02X}")