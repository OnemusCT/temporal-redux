from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, FuncSync

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

class ScriptProcessingMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        self.enabled = QCheckBox("Script Processing Enabled")
        
        obj_label = QLabel("Object ID")
        obj_label.setObjectName("Object")
        self.obj_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(self.enabled)
        layout.addWidget(obj_label)
        layout.addWidget(self.obj_id)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        return EventCommand.generic_command(
            0x0C if self.enabled.isChecked() else 0x0B,
            self.obj_id.get_value() * 2
        )
        
    def apply_arguments(self, command: int, args: list):
        self.enabled.setChecked(command == 0x0C)
        if len(args) >= 1:
            self.obj_id.set_value(args[0] // 2)