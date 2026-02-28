from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class MoveTowardTargetMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Target type selector
        type_layout = QHBoxLayout()
        type_label = QLabel("Target Type:")
        self.target_type = QComboBox()
        self.target_type.addItem("Object")
        self.target_type.addItem("PC")
        self.target_type.currentIndexChanged.connect(self._update_validator)
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.target_type)

        # Target ID input
        target_layout = QHBoxLayout()
        target_label = QLabel("Target ID:")
        self.target_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_id)

        # Distance input
        dist_layout = QHBoxLayout()
        dist_label = QLabel("Distance:")
        self.distance = ValidatingLineEdit(min_value=0, max_value=0xFF)
        dist_layout.addWidget(dist_label)
        dist_layout.addWidget(self.distance)

        # Keep facing checkbox
        self.keep_facing = QCheckBox("Keep Current Facing")

        layout.addLayout(type_layout)
        layout.addLayout(target_layout)
        layout.addLayout(dist_layout)
        layout.addWidget(self.keep_facing)

        result.setLayout(layout)
        self._update_validator(0)  # Initialize for Object
        return result

    def _update_validator(self, index):
        """Update target ID validator based on type"""
        if index == 0:  # Object
            self.target_id.setValidator(ValidatingLineEdit(min_value=0, max_value=0xFF))
        else:  # PC
            self.target_id.setValidator(ValidatingLineEdit(min_value=1, max_value=6))

    def validate(self) -> bool:
        if self.target_id.get_value() is None:
            return False
        if self.distance.get_value() is None:
            return False

        if self.target_type.currentText() == "PC":
            return 1 <= self.target_id.get_value() <= 6
        else:
            return 0 <= self.target_id.get_value() <= 0xFF

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid target ID or distance")

        return EventCommand.move_toward_object(
            self.target_id.get_value(),
            self.distance.get_value(),
            self.target_type.currentText() == "PC",
            self.keep_facing.isChecked()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            is_pc = command in [0x99, 0x9F]
            self.target_type.setCurrentText("PC" if is_pc else "Object")
            self.target_id.set_value(args[0])
            self.distance.set_value(args[1])
            self.keep_facing.setChecked(command in [0x9E, 0x9F])