from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResetAnimationMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        # Since this command takes no arguments, we'll just show a label
        result = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Reset Animation Command")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description = QLabel("Resets the current object's animation")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)
        layout.addWidget(description)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return True  # Always valid since no inputs

    def get_command(self) -> EventCommand:
        return EventCommand.reset_animation()

    def apply_arguments(self, command: int, args: list):
        pass  # No arguments to apply