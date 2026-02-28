from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.lookups import pcs
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class CheckPartyMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Check type selector
        type_label = QLabel("Check Type:")
        self.check_type = QComboBox()
        self.check_type.addItem("Check if Active")
        self.check_type.addItem("Check if Recruited")

        # PC Selection dropdown
        pc_label = QLabel("Character:")
        self.pc_id = QComboBox()
        for id, name in pcs.items():
            if name != "Epoch":
                self.pc_id.addItem(name, id)
        
        layout.addWidget(type_label)
        layout.addWidget(self.check_type)
        layout.addWidget(pc_label)
        layout.addWidget(self.pc_id)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        pc_id = self.pc_id.currentData()

        if self.check_type.currentIndex() == 0:
            return EventCommand.check_active_pc(pc_id, 0)
        else:
            return EventCommand.check_recruited_pc(pc_id, 0)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            if command == 0xD2:
                self.check_type.setCurrentIndex(0)  # Active
            else:
                self.check_type.setCurrentIndex(1)  # Recruited
            self.pc_id.setCurrentIndex(args[0])