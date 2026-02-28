from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QLabel, QSpinBox, QVBoxLayout, QWidget

class ColorAddMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # BGR Color (3 bits each)
        color_label = QLabel("Color (BGR)")
        color_label.setObjectName("Color")
        self.color = ValidatingLineEdit(min_value=0, max_value=0x7)  # 3 bits
        
        # Intensity (5 bits)
        intensity_label = QLabel("Intensity")
        intensity_label.setObjectName("Intensity")
        self.intensity = ValidatingLineEdit(min_value=0, max_value=0x1F)  # 5 bits
        
        # Add/Sub mode flag
        self.add_sub = QCheckBox("Add/Sub Mode")
        
        layout.addWidget(color_label)
        layout.addWidget(self.color)
        layout.addWidget(intensity_label)
        layout.addWidget(self.intensity)
        layout.addWidget(self.add_sub)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        return EventCommand.color_add(
            self.color.get_value(),
            self.intensity.get_value(),
            self.add_sub.isChecked()
        )
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.color.set_value((args[0] >> 5) & 0x7)
            self.intensity.set_value(args[0] & 0x1F)
            if len(args) >= 2:
                self.add_sub.setChecked(args[1] == 0x80)
