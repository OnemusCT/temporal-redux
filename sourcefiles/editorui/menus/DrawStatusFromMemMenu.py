from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class DrawStatusFromMemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Drawing status dropdown
        status_label = QLabel("Drawing Status")
        self.status = QComboBox()
        self.status.addItems(["Draw", "Hide"])
        
        # Object ID input
        obj_label = QLabel("Object ID")
        self.obj_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(status_label)
        layout.addWidget(self.status)
        layout.addWidget(obj_label)
        layout.addWidget(self.obj_id)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        is_drawn = self.status.currentText() == "Draw"
        return EventCommand.set_object_drawing_status(self.obj_id.get_value(), is_drawn)
            
    def apply_arguments(self, command: int, args: list):
        self.status.setCurrentText("Draw" if command == 0x7C else "Hide")
        if len(args) >= 1:
            self.obj_id.set_value(args[0] // 2)