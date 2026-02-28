from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class ControllableMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        controllable_label = QLabel("Controllable")
        self.controllable = QComboBox()
        self.controllable.addItem("Once")
        self.controllable.addItem("Infinite")
        self.controllable.setCurrentIndex(0)

        layout.addWidget(controllable_label)
        layout.addWidget(self.controllable)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
       if self.controllable.currentIndex() == 0:
           return EventCommand.set_controllable_once()
       return EventCommand.set_controllable_infinite()


    def apply_arguments(self, command: int, args: list):
        if command == 0xAF:
            self.controllable.setCurrentIndex(0)
        else:
            self.controllable.setCurrentIndex(1)