from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

class SpritePriorityMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Mode selection
        mode_label = QLabel("Mode")
        self.mode = QComboBox()
        self.mode.addItems(["Mode 0", "Mode 1"])

        # Layer priorities
        priority_label = QLabel("Layer Priority")
        self.priority = QComboBox()
        self.priority.addItems([
            "Below Both (0)",
            "Below Both (1)", 
            "Below L1, Above L2",
            "Above Both"
        ])

        # Unknown flags
        self.unknown_40 = QCheckBox("Unknown Flag (0x40)")
        self.unknown_0C = QCheckBox("Unknown Flag (0x0C)")

        layout.addWidget(mode_label)
        layout.addWidget(self.mode)
        layout.addWidget(priority_label)
        layout.addWidget(self.priority)
        layout.addWidget(self.unknown_40)
        layout.addWidget(self.unknown_0C)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        priority_value = 0

        # Set mode bit
        if self.mode.currentIndex() == 1:
            priority_value |= 0x80

        # Set unknown flags
        if self.unknown_40.isChecked():
            priority_value |= 0x40
        if self.unknown_0C.isChecked():
            priority_value |= 0x0C

        # Set priority bits
        priority_value |= (self.priority.currentIndex() & 0x3)

        return EventCommand.generic_one_arg(0x8E, priority_value)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            priority = args[0]
            
            # Set mode
            self.mode.setCurrentIndex(1 if priority & 0x80 else 0)
            
            # Set unknown flags
            self.unknown_40.setChecked(bool(priority & 0x40))
            self.unknown_0C.setChecked(bool(priority & 0x0C))