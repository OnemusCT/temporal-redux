from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class DrawStatusMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Drawing status dropdown
        status_label = QLabel("Drawing Status")
        status_label.setObjectName("Status")
        self.status = QComboBox()
        self.status.addItems(["Draw", "Hide", "Remove"])
        self.status.currentIndexChanged.connect(self._update_ui)
        
        # Variant dropdown for Hide
        variant_label = QLabel("Variant")
        variant_label.setObjectName("Variant")
        self.variant = QComboBox()
        self.variant.addItems(["Normal (91)", "Alternate (7E)"])
        self.variant.setVisible(False)
        variant_label.setVisible(False)
        
        # Object ID for Remove
        obj_label = QLabel("Object ID")
        obj_label.setObjectName("Object ID")
        self.obj_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        obj_label.setVisible(False)
        self.obj_id.setVisible(False)
        
        layout.addWidget(status_label)
        layout.addWidget(self.status)
        layout.addWidget(variant_label)
        layout.addWidget(self.variant)
        layout.addWidget(obj_label)
        layout.addWidget(self.obj_id)
        
        result.setLayout(layout)
        return result
        
    def _update_ui(self, index):
        """Update UI based on selected status"""
        is_hide = index == 1
        is_remove = index == 2
        
        self.variant.setVisible(is_hide)
        self.variant.parent().findChild(QLabel, "Variant").setVisible(is_hide)
        
        self.obj_id.setVisible(is_remove)
        self.obj_id.parent().findChild(QLabel, "Object ID").setVisible(is_remove)

    def get_command(self) -> EventCommand:
        status = self.status.currentText()
        
        if status == "Draw":
            return EventCommand.set_own_drawing_status(True)
        elif status == "Hide":
            use_7e = self.variant.currentIndex() == 1
            return EventCommand.set_own_drawing_status(False, 0x7E if use_7e else 0x91)
        else:  # Remove
            return EventCommand.remove_object(self.obj_id.get_value())
            
    def apply_arguments(self, command: int, args: list):
        if command == 0x90:
            self.status.setCurrentText("Draw")
        elif command in [0x91, 0x7E]:
            self.status.setCurrentText("Hide")
            self.variant.setCurrentIndex(1 if command == 0x7E else 0)
        elif command == 0x0A:
            self.status.setCurrentText("Remove")
            if len(args) >= 1:
                self.obj_id.set_value(args[0] // 2)