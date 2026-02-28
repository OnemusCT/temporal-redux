from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PartyFollowMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        label = QLabel("Makes PC2 and PC3 follow PC1")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(label)
        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return True  # Always valid, no parameters

    def get_command(self) -> EventCommand:
        return EventCommand.party_follow()

    def apply_arguments(self, command: int, args: list):
        pass  # No arguments to apply