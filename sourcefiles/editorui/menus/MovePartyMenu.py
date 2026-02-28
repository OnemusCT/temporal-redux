from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QGridLayout, QLabel, QWidget


class MovePartyMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QGridLayout()

        # Create inputs for each PC's coordinates
        self.coords = []
        for i in range(3):
            pc_label = QLabel(f"PC{i+1} Position:")
            x_label = QLabel("X:")
            y_label = QLabel("Y:")

            x_input = ValidatingLineEdit(min_value=0, max_value=0xFF)
            y_input = ValidatingLineEdit(min_value=0, max_value=0xFF)

            layout.addWidget(pc_label, i*2, 0)
            layout.addWidget(x_label, i*2+1, 0)
            layout.addWidget(x_input, i*2+1, 1)
            layout.addWidget(y_label, i*2+1, 2)
            layout.addWidget(y_input, i*2+1, 3)

            self.coords.append((x_input, y_input))

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return all(x.get_value() is not None and y.get_value() is not None
                  for x, y in self.coords)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("All coordinates must be valid")

        coords = []
        for x_input, y_input in self.coords:
            coords.extend([x_input.get_value(), y_input.get_value()])

        return EventCommand.move_party(*coords)

    def apply_arguments(self, command: int, args: list):
        if len(args) < 6:
            return

        for i, (x_input, y_input) in enumerate(self.coords):
            x_input.set_value(args[i*2])
            y_input.set_value(args[i*2+1])