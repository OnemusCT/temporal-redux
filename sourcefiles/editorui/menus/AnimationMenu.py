from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class AnimationMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Animation ID input with validation
        animation_label = QLabel("Animation ID")
        self.animation_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        # Loops input with validation
        loops_label = QLabel("Loops")
        self.loops = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.loops.setText("0")
        self.loops.setDisabled(True)

        # Animation type selector
        type_label = QLabel("Type")
        self.type = QComboBox()
        self.type.addItem("Normal")
        self.type.addItem("Static")
        self.type.addItem("Loop")
        self.type.setCurrentIndex(0)
        self.type.currentIndexChanged.connect(self._on_index_changed)

        # Add components to layout
        layout.addWidget(animation_label)
        layout.addWidget(self.animation_id)
        layout.addWidget(type_label)
        layout.addWidget(self.type)
        layout.addWidget(loops_label)
        layout.addWidget(self.loops)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        """Validate all inputs before creating command."""
        self.clear_error()

        # Check animation ID
        if self.animation_id.get_value() is None:
            return False

        # Check loops if in loop mode
        if self.type.currentText() == "Loop" and not self.loops.isEnabled():
            if self.loops.get_value() is None:
                return False

        return True

    def get_command(self) -> EventCommand:
        animation_id = self.animation_id.get_value()
        if animation_id is None:
            raise CommandError("Invalid animation ID")

        anim_type = self.type.currentText()
        loops = self.loops.get_value() if self.loops.isEnabled() else 0

        if anim_type == "Loop" and loops is None:
            raise CommandError("Invalid loop count")

        return EventCommand.animation(animation_id, anim_type, loops)

    def apply_arguments(self, command: int, args: list):
        # Handle special cases B3 and B4 (hard-coded animation IDs)
        if command == 0xB3:
            self.animation_id.set_value(0)
            self.type.setCurrentText("Normal")
            self.loops.set_value(0)
            return
        elif command == 0xB4:
            self.animation_id.set_value(1)
            self.type.setCurrentText("Normal")
            self.loops.set_value(0)
            return

        # Handle other commands
        if command == 0xAA:  # Infinite loop
            self.animation_id.set_value(args[0])
            self.type.setCurrentText("Loop")
            self.loops.set_value(0)
        elif command == 0xAB:  # Normal animation
            self.animation_id.set_value(args[0])
            self.type.setCurrentText("Normal")
            self.loops.set_value(0)
        elif command == 0xAC:  # Static animation
            self.animation_id.set_value(args[0])
            self.type.setCurrentText("Static")
            self.loops.set_value(0)
        elif command == 0xB7:  # Specified loop count
            self.animation_id.set_value(args[0])
            self.type.setCurrentText("Loop")
            self.loops.set_value(args[1])

    def _on_index_changed(self, index):
        self.loops.setEnabled(self.type.currentText() == "Loop")
        if not self.loops.isEnabled():
            self.loops.setText("0")
            self.loops.clear_error()