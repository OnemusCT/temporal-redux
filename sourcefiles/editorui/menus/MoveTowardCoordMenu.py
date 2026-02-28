from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget


class MoveTowardCoordMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QGridLayout()

        x_label = QLabel("X Coordinate:")
        y_label = QLabel("Y Coordinate:")
        dist_label = QLabel("Distance:")

        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.distance = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(x_label, 0, 0)
        layout.addWidget(self.x_coord, 0, 1)
        layout.addWidget(y_label, 1, 0)
        layout.addWidget(self.y_coord, 1, 1)
        layout.addWidget(dist_label, 2, 0)
        layout.addWidget(self.distance, 2, 1)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.x_coord.get_value() is not None and
                self.y_coord.get_value() is not None and
                self.distance.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("All values must be valid (00-FF)")

        return EventCommand.move_toward_coord(
            self.x_coord.get_value(),
            self.y_coord.get_value(),
            self.distance.get_value()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 3:
            self.x_coord.set_value(args[0])
            self.y_coord.set_value(args[1])
            self.distance.set_value(args[2])