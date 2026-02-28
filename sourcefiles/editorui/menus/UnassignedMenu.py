from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand, event_commands


from PyQt6.QtWidgets import QWidget


class UnassignedMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        return QWidget()

    def get_command(self) -> EventCommand:
        return event_commands[1]

    def apply_arguments(self, command, args):
        pass