from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QCheckBox, QVBoxLayout, QWidget


class ObjectMovementPropertiesMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        self.through_walls = QCheckBox("Through Walls")
        self.through_pcs = QCheckBox("Through PCs")

        layout.addWidget(self.through_walls)
        layout.addWidget(self.through_pcs)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return True  # Always valid since checkboxes can't be invalid

    def get_command(self) -> EventCommand:
        return EventCommand.set_movement_properties(
            self.through_walls.isChecked(),
            self.through_pcs.isChecked()
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.through_walls.setChecked(args[0] & 0x01)
            self.through_pcs.setChecked(args[0] & 0x02)