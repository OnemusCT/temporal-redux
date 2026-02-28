from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QGridLayout, QLabel, QVBoxLayout, QWidget


class MoveSpriteFromMemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        addr_layout = QGridLayout()

        x_label = QLabel("X Coordinate Address:")
        y_label = QLabel("Y Coordinate Address:")
        self.x_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        self.y_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        x_help = QLabel("(must be in 7F0200-7F0400)")
        y_help = QLabel("(must be in 7F0200-7F0400)")
        x_help.setStyleSheet("color: gray;")
        y_help.setStyleSheet("color: gray;")

        addr_layout.addWidget(x_label, 0, 0)
        addr_layout.addWidget(self.x_addr, 0, 1)
        addr_layout.addWidget(x_help, 1, 0, 1, 2)
        addr_layout.addWidget(y_label, 2, 0)
        addr_layout.addWidget(self.y_addr, 2, 1)
        addr_layout.addWidget(y_help, 3, 0, 1, 2)

        self.animated = QCheckBox("Animated Movement")

        layout.addLayout(addr_layout)
        layout.addWidget(self.animated)
        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.x_addr.get_value() is not None and
                self.y_addr.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Addresses must be valid script memory addresses")

        return EventCommand.move_sprite_from_mem(
            self.x_addr.get_value(),
            self.y_addr.get_value(),
            self.animated.isChecked()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            # Convert offsets back to full addresses
            self.x_addr.set_value(0x7F0200 + args[0] * 2)
            self.y_addr.set_value(0x7F0200 + args[1] * 2)
            self.animated.setChecked(command in [0xA1])