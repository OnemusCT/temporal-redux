from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class ExploreModeMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        explore_label = QLabel("Explore Mode")
        self.explore_mode = QComboBox()
        self.explore_mode.addItem("On")
        self.explore_mode.addItem("Off")
        self.explore_mode.setCurrentIndex(0)

        layout.addWidget(explore_label)
        layout.addWidget(self.explore_mode)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
       return EventCommand.set_explore_mode(self.explore_mode.currentIndex() == 0)


    def apply_arguments(self, command: int, args: list):
        if args[0] == 1:
            self.explore_mode.setCurrentIndex(0)
        else:
            self.explore_mode.setCurrentIndex(1)