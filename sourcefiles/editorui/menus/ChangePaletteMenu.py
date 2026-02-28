from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ChangePaletteMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        palette_label = QLabel("Palette ID")
        self.palette = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(palette_label)
        layout.addWidget(self.palette)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            palette = int(self.palette.text(), 16)
            return EventCommand.change_palette(palette)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.palette.setText(f"{args[0]:02X}")