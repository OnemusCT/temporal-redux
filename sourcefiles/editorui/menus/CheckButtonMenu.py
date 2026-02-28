from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class CheckButtonMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Check type selection (Action vs Button)
        type_label = QLabel("Check Type:")
        self.check_type = QComboBox()
        self.check_type.addItem("Action")
        self.check_type.addItem("Button")
        self.check_type.currentIndexChanged.connect(self._update_button_choices)

        # Button/Action selection
        button_label = QLabel("Button/Action:")
        self.button_choice = QComboBox()

        # Current vs Since Last
        mode_label = QLabel("Check Mode:")
        self.check_mode = QComboBox()
        self.check_mode.addItem("Current")
        self.check_mode.addItem("Since Last Check")
        self.check_mode.currentIndexChanged.connect(self._validate_combination)

        # Command preview
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Add everything to layout
        layout.addWidget(type_label)
        layout.addWidget(self.check_type)
        layout.addWidget(button_label)
        layout.addWidget(self.button_choice)
        layout.addWidget(mode_label)
        layout.addWidget(self.check_mode)
        layout.addWidget(self.preview)

        result.setLayout(layout)

        # Initialize button choices
        self._update_button_choices(0)

        # Connect signals for preview updates
        self.check_type.currentIndexChanged.connect(self._update_preview)
        self.button_choice.currentIndexChanged.connect(self._update_preview)
        self.check_mode.currentIndexChanged.connect(self._update_preview)

        return result

    def _update_button_choices(self, index):
        """Update available button choices based on check type"""
        self.button_choice.clear()

        if index == 0:  # Action
            self.button_choice.addItem("Dash")
            self.button_choice.addItem("Confirm")
        else:  # Button
            for button in ["Any", "A", "B", "X", "Y", "L", "R"]:
                self.button_choice.addItem(button)

        self._validate_combination()

    def _validate_combination(self):
        """Validate the current combination of choices"""
        # "Any" button can't be used with "Since Last Check"
        is_any = (self.check_type.currentText() == "Button" and
                 self.button_choice.currentText() == "Any")
        is_since_last = self.check_mode.currentIndex() == 1

        if is_any and is_since_last:
            self.check_mode.setCurrentIndex(0)
            self.check_mode.setEnabled(False)
        else:
            self.check_mode.setEnabled(True)

    def _update_preview(self):
        """Update the command preview"""
        try:
            cmd = self.get_command()
            self.preview.setText(f"Command: {cmd.command:02X}")
            self.preview.setStyleSheet("")
        except (ValueError, CommandError) as e:
            self.preview.setText(str(e))
            self.preview.setStyleSheet("color: red;")

    def validate(self) -> bool:
        """Validate the current input"""
        # Check for invalid Any + Since Last combination
        is_any = (self.check_type.currentText() == "Button" and
                 self.button_choice.currentText() == "Any")
        is_since_last = self.check_mode.currentIndex() == 1

        if is_any and is_since_last:
            return False

        return True

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid button check combination")

        is_action = self.check_type.currentText() == "Action"
        button = self.button_choice.currentText()
        since_last = self.check_mode.currentIndex() == 1

        return EventCommand.check_button(is_action, button, since_last, 0)

    def apply_arguments(self, command: int, args: list):
        # Map command to settings
        if command in [0x30, 0x31]:  # Action current
            self.check_type.setCurrentText("Action")
            self.check_mode.setCurrentIndex(0)
            self.button_choice.setCurrentText("Dash" if command == 0x30 else "Confirm")

        elif command in [0x3B, 0x3C]:  # Action since last
            self.check_type.setCurrentText("Action")
            self.check_mode.setCurrentIndex(1)
            self.button_choice.setCurrentText("Dash" if command == 0x3B else "Confirm")

        elif command == 0x2D:  # Any button current
            self.check_type.setCurrentText("Button")
            self.check_mode.setCurrentIndex(0)
            self.button_choice.setCurrentText("Any")

        else:  # Specific button
            self.check_type.setCurrentText("Button")

            # Map command to button and mode
            button_map = {
                0x34: ("A", 0), 0x35: ("B", 0), 0x36: ("X", 0),
                0x37: ("Y", 0), 0x38: ("L", 0), 0x39: ("R", 0),
                0x3F: ("A", 1), 0x40: ("B", 1), 0x41: ("X", 1),
                0x42: ("Y", 1), 0x43: ("L", 1), 0x44: ("R", 1)
            }

            if command in button_map:
                button, mode = button_map[command]
                self.button_choice.setCurrentText(button)
                self.check_mode.setCurrentIndex(mode)