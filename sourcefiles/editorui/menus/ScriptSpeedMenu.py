from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ScriptSpeedMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        speed_label = QLabel("Script Speed (0=fastest, 80=stop)")
        self.speed = ValidatingLineEdit(min_value=0, max_value=0x80)

        layout.addWidget(speed_label)
        layout.addWidget(self.speed)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            speed = int(self.speed.text(), 16)
            return EventCommand.script_speed(speed)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.speed.setText(f"{args[0]:02X}")