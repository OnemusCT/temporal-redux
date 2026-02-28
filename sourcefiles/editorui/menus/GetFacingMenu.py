from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class GetFacingMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Target type selection
        type_label = QLabel("Target Type")
        type_label.setObjectName("Type")
        self.target_type = QComboBox()
        self.target_type.addItems(["Object", "PC"])
        
        # Target ID
        target_label = QLabel("Target ID")
        target_label.setObjectName("Target")
        self.target_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        # Memory address
        addr_label = QLabel("Store To Address")
        addr_label.setObjectName("Address")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        layout.addWidget(type_label)
        layout.addWidget(self.target_type)
        layout.addWidget(target_label)
        layout.addWidget(self.target_id)
        layout.addWidget(addr_label)
        layout.addWidget(self.addr)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        is_pc = self.target_type.currentText() == "PC"
        cmd_id = 0x24 if is_pc else 0x23
        return EventCommand.generic_command(
            cmd_id,
            self.target_id.get_value() * 2,
            (self.addr.get_value() - 0x7F0200) // 2
        )
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.target_type.setCurrentText("PC" if command == 0x24 else "Object")
            self.target_id.set_value(args[0] // 2)
            self.addr.set_value(0x7F0200 + (args[1] * 2))