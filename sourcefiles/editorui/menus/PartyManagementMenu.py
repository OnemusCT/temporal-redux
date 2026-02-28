from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand
from editorui.lookups import pcs

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class PartyManagementMenu(BaseCommandMenu):
    """Menu for party management commands (add/remove/move PCs)."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Command type selector
        command_label = QLabel("Command Type")
        self.command_type = QComboBox()
        self.command_type.addItems([
            "Add PC to Reserve Party",
            "Remove PC",
            "Add PC to Active Party", 
            "Move PC to Reserve Party",
            "Remove PC from Active Party"
        ])

        # PC selector
        pc_label = QLabel("Character")
        self.pc_select = QComboBox()
        for id, name in pcs.items():
            if name != "Epoch":  # Exclude Epoch from the list
                self.pc_select.addItem(name, id)

        layout.addWidget(command_label)
        layout.addWidget(self.command_type)
        layout.addWidget(pc_label)
        layout.addWidget(self.pc_select)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        pc_id = self.pc_select.currentData()
        command_index = self.command_type.currentIndex()
        
        # Map command types to their event commands
        command_map = {
            0: EventCommand.generic_one_arg(0xD0, pc_id),  # Add to reserve
            1: EventCommand.generic_one_arg(0xD1, pc_id),  # Remove PC
            2: EventCommand.generic_one_arg(0xD3, pc_id),  # Add to active
            3: EventCommand.generic_one_arg(0xD4, pc_id),  # Move to reserve
            4: EventCommand.generic_one_arg(0xD6, pc_id)   # Remove from active
        }
        
        return command_map[command_index]

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            # Find and set PC in dropdown
            pc_id = args[0]
            index = self.pc_select.findData(pc_id)
            if index >= 0:
                self.pc_select.setCurrentIndex(index)
            
            # Set command type based on command code
            command_map = {
                0xD0: 0,  # Add to reserve
                0xD1: 1,  # Remove PC
                0xD3: 2,  # Add to active
                0xD4: 3,  # Move to reserve
                0xD6: 4   # Remove from active
            }
            if command in command_map:
                self.command_type.setCurrentIndex(command_map[command])