from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class SetFacingMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Target selection
        target_label = QLabel("Target")
        target_label.setObjectName("Target")
        self.target = QComboBox()
        self.target.addItem("Self")
        for i in range(0x33):
            self.target.addItem(f"NPC {i:02X}")
            
        # Direction selection
        direction_label = QLabel("Direction")
        direction_label.setObjectName("Direction")
        self.direction = QComboBox()
        self.direction.addItems(["Up", "Down", "Left", "Right"])
        
        layout.addWidget(target_label)
        layout.addWidget(self.target)
        layout.addWidget(direction_label)
        layout.addWidget(self.direction)
        
        result.setLayout(layout)
        return result
        
    def get_command(self) -> EventCommand:
        direction = self.direction.currentIndex()
        target_idx = self.target.currentIndex() - 1  # -1 accounts for "Self"
        
        if target_idx == -1:  # Self
            # Use direct commands for self
            cmd_map = {0: 0x0F, 1: 0x17, 2: 0x1B, 3: 0x1D}
            return EventCommand.generic_zero_arg(cmd_map[direction])
        else:
            # Use direction-specific NPC commands
            cmd_map = {0: 0x1E, 1: 0x1F, 2: 0x25, 3: 0x26}
            return EventCommand.generic_command(cmd_map[direction], target_idx * 2)

    def apply_arguments(self, command: int, args: list):
        if command in [0x0F, 0x17, 0x1B, 0x1D]:
            self.target.setCurrentIndex(0)  # Self
            dir_map = {0x0F: 0, 0x17: 1, 0x1B: 2, 0x1D: 3}
            self.direction.setCurrentIndex(dir_map[command])
        elif command in [0x1E, 0x1F, 0x25, 0x26] and len(args) >= 1:
            if args[0] // 2 <= 0x32:
                self.target.setCurrentIndex((args[0] // 2) + 1)
            dir_map = {0x1E: 0, 0x1F: 1, 0x25: 2, 0x26: 3}
            self.direction.setCurrentIndex(dir_map[command])
        elif command == 0xA6 and len(args) >= 2:
            if args[0] <= 0x32:
                self.target.setCurrentIndex(args[0] + 1)
            self.direction.setCurrentIndex(args[1])