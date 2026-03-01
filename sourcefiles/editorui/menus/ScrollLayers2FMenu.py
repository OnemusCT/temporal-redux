from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QFormLayout, QWidget


class ScrollLayers2FMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.param1 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.param2 = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addRow("Param 1", self.param1)
        layout.addRow("Param 2", self.param2)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        return EventCommand.generic_command(0x2F, self.param1.get_value(), self.param2.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.param1.set_value(args[0])
        if len(args) >= 2:
            self.param2.set_value(args[1])
