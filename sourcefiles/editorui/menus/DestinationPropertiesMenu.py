from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QVBoxLayout, QWidget


class DestinationPropertiesMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        self.onto_tile = QCheckBox("Onto Tile")
        self.onto_object = QCheckBox("Onto Object")

        layout.addWidget(self.onto_tile)
        layout.addWidget(self.onto_object)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return True  # Always valid since checkboxes can't be invalid

    def get_command(self) -> EventCommand:
        return EventCommand.set_destination_properties(
            self.onto_tile.isChecked(),
            self.onto_object.isChecked()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.onto_tile.setChecked(args[0] & 0x01)
            self.onto_object.setChecked(args[0] & 0x02)