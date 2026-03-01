from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QFormLayout, QWidget


_FIELD_LABELS = [
    "Unknown 1",
    "XCoord 1 Src", "XCoord 1 Dest",
    "YCoord 1 Src", "YCoord 1 Dest",
    "XCoord 2 Src", "XCoord 2 Dest",
    "YCoord 2 Src", "YCoord 2 Dest",
    "XCoord 3 Src", "XCoord 3 Dest",
    "YCoord 3 Src", "YCoord 3 Dest",
    "XCoord 4 Src", "XCoord 4 Dest",
    "YCoord 4 Src", "YCoord 4 Dest",
]


class DrawGeometryMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self._fields = []
        for label in _FIELD_LABELS:
            field = ValidatingLineEdit(min_value=0, max_value=0xFF)
            self._fields.append(field)
            layout.addRow(label, field)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        values = [f.get_value() for f in self._fields]
        return EventCommand.generic_command(0xFE, *values)

    def apply_arguments(self, command: int, args: list):
        for i, field in enumerate(self._fields):
            if i < len(args):
                field.set_value(args[i])
