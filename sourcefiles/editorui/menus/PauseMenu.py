from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QDoubleValidator

class PauseMenu(BaseCommandMenu):
    """Menu for pause duration commands"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        pause_label = QLabel("Duration (seconds):")
        self.duration = ValidatingLineEdit()
        # Allow decimal values by setting custom validator
        self.duration.setValidator(QDoubleValidator(0, 10, 4))  # Up to 10 seconds, 4 decimal places
        
        layout.addWidget(pause_label)
        layout.addWidget(self.duration)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            duration = float(self.duration.text())
            
            # Check for special case durations
            if duration == 0.25:
                return EventCommand.generic_zero_arg(0xB9)
            elif duration == 0.5:
                return EventCommand.generic_zero_arg(0xBA)
            elif duration == 1.0:
                return EventCommand.generic_zero_arg(0xBC)
            elif duration == 2.0:
                return EventCommand.generic_zero_arg(0xBD)
            
            # Convert arbitrary duration to 1/16th second ticks
            ticks = int(duration * 16)
            return EventCommand.generic_one_arg(0xAD, ticks)
        except ValueError:
            return None

    def apply_arguments(self, command: int, args: list):
        if command == 0xB9:
            self.duration.setText("0.25")
        elif command == 0xBA:
            self.duration.setText("0.5")
        elif command == 0xBC:
            self.duration.setText("1")
        elif command == 0xBD:
            self.duration.setText("2")
        elif command == 0xAD and len(args) >= 1:
            duration = args[0] / 16  # Convert ticks back to seconds
            self.duration.setText(f"{duration:.4f}")