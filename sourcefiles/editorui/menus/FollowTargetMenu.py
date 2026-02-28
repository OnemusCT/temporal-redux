from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class FollowTargetMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Follow type selector
        type_layout = QHBoxLayout()
        type_label = QLabel("Follow Mode:")
        self.follow_type = QComboBox()
        self.follow_type.addItem("At Distance (PC only)")
        self.follow_type.addItem("Follow Object")
        self.follow_type.addItem("Follow PC")
        self.follow_type.currentIndexChanged.connect(self._update_ui)
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.follow_type)

        # Target ID input
        target_layout = QHBoxLayout()
        target_label = QLabel("Target ID:")
        self.target_id = ValidatingLineEdit(min_value=1, max_value=6)  # Starts as PC mode
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_id)

        # Repeat checkbox (not shown for distance follow)
        self.repeat = QCheckBox("Repeat Follow")

        layout.addLayout(type_layout)
        layout.addLayout(target_layout)
        layout.addWidget(self.repeat)

        result.setLayout(layout)
        self._update_ui(0)  # Initialize for distance follow
        return result

    def _update_ui(self, index):
        """Update UI based on follow type"""
        if index == 0:  # At Distance
            self.target_id.setValidator(ValidatingLineEdit(min_value=1, max_value=6))
            self.repeat.setVisible(False)
        elif index == 1:  # Follow Object
            self.target_id.setValidator(ValidatingLineEdit(min_value=0, max_value=0xFF))
            self.repeat.setVisible(True)
        else:  # Follow PC
            self.target_id.setValidator(ValidatingLineEdit(min_value=1, max_value=6))
            self.repeat.setVisible(True)

    def validate(self) -> bool:
        if self.target_id.get_value() is None:
            return False

        follow_type = self.follow_type.currentIndex()
        if follow_type in [0, 2]:  # PC modes
            return 1 <= self.target_id.get_value() <= 6
        else:  # Object mode
            return 0 <= self.target_id.get_value() <= 0xFF

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid target ID")

        follow_type = self.follow_type.currentIndex()
        if follow_type == 0:  # At Distance
            return EventCommand.follow_pc_at_distance(self.target_id.get_value())
        else:
            return EventCommand.follow_target(
                self.target_id.get_value(),
                follow_type == 2,  # is_pc
                self.repeat.isChecked()
            )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            if command == 0x8F:
                self.follow_type.setCurrentIndex(0)  # At Distance
                self.target_id.set_value(args[0])
            elif command in [0x94, 0xB5]:  # Follow Object
                self.follow_type.setCurrentIndex(1)
                self.target_id.set_value(args[0])
                self.repeat.setChecked(command == 0xB5)
            elif command in [0x95, 0xB6]:  # Follow PC
                self.follow_type.setCurrentIndex(2)
                self.target_id.set_value(args[0])
                self.repeat.setChecked(command == 0xB6)