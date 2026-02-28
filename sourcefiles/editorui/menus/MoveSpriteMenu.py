from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QGridLayout, QLabel, QVBoxLayout, QWidget


class MoveSpriteMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        coord_layout = QGridLayout()

        x_label = QLabel("X Coordinate:")
        y_label = QLabel("Y Coordinate:")
        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)

        coord_layout.addWidget(x_label, 0, 0)
        coord_layout.addWidget(self.x_coord, 0, 1)
        coord_layout.addWidget(y_label, 1, 0)
        coord_layout.addWidget(self.y_coord, 1, 1)

        self.animated = QCheckBox("Animated Movement")

        layout.addLayout(coord_layout)
        layout.addWidget(self.animated)
        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.x_coord.get_value() is not None and
                self.y_coord.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Coordinates must be valid")

        return EventCommand.move_sprite(
            self.x_coord.get_value(),
            self.y_coord.get_value(),
            self.animated.isChecked()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.x_coord.set_value(args[0])
            self.y_coord.set_value(args[1])
            self.animated.setChecked(command in [0xA0, 0xA1])