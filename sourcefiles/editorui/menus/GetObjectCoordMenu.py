from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class GetObjectCoordMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Target type selection
        type_label = QLabel("Target Type")
        type_label.setObjectName("Type")
        self.target_type = QComboBox()
        self.target_type.addItems(["NPC", "PC"])
        
        # Target ID
        target_label = QLabel("Target ID")
        target_label.setObjectName("Target")
        self.target_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        # Store addresses
        x_label = QLabel("Store X To Address")
        x_label.setObjectName("X Address")
        self.x_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        y_label = QLabel("Store Y To Address")
        y_label.setObjectName("Y Address")
        self.y_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        
        layout.addWidget(type_label)
        layout.addWidget(self.target_type)
        layout.addWidget(target_label)
        layout.addWidget(self.target_id)
        layout.addWidget(x_label)
        layout.addWidget(self.x_addr)
        layout.addWidget(y_label)
        layout.addWidget(self.y_addr)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        if self.target_type.currentText() == "PC":
            return EventCommand.get_pc_coordinates(
                self.target_id.get_value(),
                self.x_addr.get_value(),
                self.y_addr.get_value()
            )
        else:
            return EventCommand.get_object_coordinates(
                self.target_id.get_value(),
                self.x_addr.get_value(),
                self.y_addr.get_value()
            )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 3:
            self.target_type.setCurrentText("PC" if command == 0x22 else "NPC")
            self.target_id.set_value(args[0] // 2)
            self.x_addr.set_value(0x7F0200 + (args[1] * 2))
            self.y_addr.set_value(0x7F0200 + (args[2] * 2))
