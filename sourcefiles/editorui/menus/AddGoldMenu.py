from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class AddGoldMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        amount_label = QLabel("Gold Amount")
        self.amount = ValidatingLineEdit(min_value=0, max_value=0xFFFF)

        self.add_mode = QComboBox()
        self.add_mode.addItem("Add Gold")
        self.add_mode.addItem("Remove Gold")

        layout.addWidget(self.add_mode)
        layout.addWidget(amount_label)
        layout.addWidget(self.amount)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            amount = int(self.amount.text(), 16)
            if self.add_mode.currentIndex() == 0:
                return EventCommand.add_gold(amount)
            else:
                return EventCommand.remove_gold(amount)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.amount.setText(f"{args[0]:04X}")
            # Set mode based on command
            self.add_mode.setCurrentIndex(0 if command == 0xCD else 1)


