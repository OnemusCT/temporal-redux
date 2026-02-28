from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QRadioButton, QLabel, QVBoxLayout, QWidget, QButtonGroup, QComboBox


class ValByteMathMenu(BaseCommandMenu):
    """Menu for value-to-memory byte math operations."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Operation selection
        self.op_group = QButtonGroup()
        self.add = QRadioButton("Add Value")
        self.subtract = QRadioButton("Subtract Value")
        
        self.op_group.addButton(self.add)
        self.op_group.addButton(self.subtract)
        self.add.setChecked(True)

        # Can select 1 or 2 bytes
        byte_label = QLabel("Number of Bytes")
        self.num_bytes = QComboBox()
        self.num_bytes.addItem("1 Byte", 1)
        self.num_bytes.addItem("2 Bytes", 2)
        
        # Value input - start with 1 byte limits
        value_label = QLabel("Value")
        self.value = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        # Update value limits when byte count changes
        self.num_bytes.currentIndexChanged.connect(self._update_value_limits)

        # Memory address input
        addr_label = QLabel("Memory Address (7F0200-7F0400)")
        self.addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        # Add widgets to layout
        layout.addWidget(self.add)
        layout.addWidget(self.subtract)
        layout.addWidget(byte_label)
        layout.addWidget(self.num_bytes)
        layout.addWidget(value_label)
        layout.addWidget(self.value)
        layout.addWidget(addr_label)
        layout.addWidget(self.addr)

        result.setLayout(layout)
        return result
        
    def _update_value_limits(self):
        """Update value input limits based on number of bytes selected."""
        if self.num_bytes.currentData() == 1:
            self.value.min_value = 0
            self.value.max_value = 0xFF
        else:
            self.value.min_value = 0
            self.value.max_value = 0xFFFF
        
        # Clear the current value since limits have changed
        self.value.clear()

    def validate(self) -> bool:
        return (self.addr.get_value() is not None and 
                self.value.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        addr = self.addr.get_value()
        value = self.value.get_value()
        num_bytes = self.num_bytes.currentData()
        
        # Use increment/decrement for value of 1
        if value == 1:
            if self.add.isChecked():
                return EventCommand.increment_mem(addr, num_bytes)
            elif num_bytes == 1:
                return EventCommand.decrement_mem(addr)
        
        # Otherwise use add/subtract value commands
        if self.add.isChecked():
            return EventCommand.add_value_to_mem(value, addr)
        else:
            return EventCommand.subtract_value_from_mem(value, addr, num_bytes)

    def apply_arguments(self, command: int, args: list):
        if len(args) < 1:
            return
            
        if command in [0x5B, 0x5F]:  # 1 byte add/subtract
            value = args[0]
            addr = 0x7F0200 + (args[1] * 2)
            self.num_bytes.setCurrentIndex(0)  # Set bytes first so limits are correct
            self.value.set_value(value)
            self.addr.set_value(addr)
            if command == 0x5B:
                self.add.setChecked(True)
            else:
                self.subtract.setChecked(True)
                
        elif command == 0x60:  # 2 byte subtract
            value = args[0]
            addr = 0x7F0200 + (args[1] * 2)
            self.num_bytes.setCurrentIndex(1)  # Set bytes first so limits are correct
            self.value.set_value(value)
            self.addr.set_value(addr)
            self.subtract.setChecked(True)
            
        elif command in [0x71, 0x72]:  # increment
            addr = 0x7F0200 + (args[0] * 2)
            self.num_bytes.setCurrentIndex(0 if command == 0x71 else 1)
            self.addr.set_value(addr)
            self.value.set_value(1)
            self.add.setChecked(True)
            
        elif command == 0x73:  # decrement
            addr = 0x7F0200 + (args[0] * 2)
            self.num_bytes.setCurrentIndex(0)
            self.addr.set_value(addr)
            self.value.set_value(1)
            self.subtract.setChecked(True)