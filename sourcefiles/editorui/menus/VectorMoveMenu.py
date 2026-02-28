from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class VectorMoveMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Angle input (0-255 maps to 0-360 degrees)
        angle_layout = QHBoxLayout()
        angle_label = QLabel("Angle (degrees):")
        self.angle_input = ValidatingLineEdit(min_value=0, max_value=359)
        angle_layout.addWidget(angle_label)
        angle_layout.addWidget(self.angle_input)

        # Magnitude input
        mag_layout = QHBoxLayout()
        mag_label = QLabel("Magnitude:")
        self.mag_input = ValidatingLineEdit(min_value=0, max_value=0xFF)
        mag_layout.addWidget(mag_label)
        mag_layout.addWidget(self.mag_input)

        # Keep facing checkbox
        self.keep_facing = QCheckBox("Keep current facing")

        layout.addLayout(angle_layout)
        layout.addLayout(mag_layout)
        layout.addWidget(self.keep_facing)
        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.angle_input.get_value() is not None and
                self.mag_input.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Angle and magnitude must be valid")

        angle = self.angle_input.get_value()
        magnitude = self.mag_input.get_value()
        keep_facing = self.keep_facing.isChecked()

        return EventCommand.vector_move(angle, magnitude, keep_facing)

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return

        # Convert command byte angle (0-255) to degrees (0-359)
        angle_deg = int(args[0] * 360 / 256)
        self.angle_input.set_value(angle_deg)
        self.mag_input.set_value(args[1])

        # Command 0x9C keeps facing, 0x92 changes it
        self.keep_facing.setChecked(command == 0x9C)