from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SpriteCollisionMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        props_label = QLabel("Solidity Properties")
        self.props = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(props_label)
        layout.addWidget(self.props)
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            props = int(self.props.text(), 16)
            return EventCommand.sprite_collision(props)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.props.setText(f"{args[0]:02X}")