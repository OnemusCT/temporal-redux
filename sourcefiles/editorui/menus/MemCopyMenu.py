from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, event_commands

from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget
from PyQt6.QtGui import QValidator
from PyQt6.QtCore import Qt

class HexValidator(QValidator):
    """Validator for hex input that requires even number of characters."""
    def validate(self, input_str: str, pos: int) -> tuple:
        # Allow empty string
        if not input_str:
            return (QValidator.State.Acceptable, input_str, pos)
            
        # Check if it's valid hex
        try:
            # Remove whitespace and validate
            cleaned = input_str.strip().replace(" ", "")
            int(cleaned, 16)
            
            # Must have even number of characters
            if len(cleaned) % 2 == 0:
                return (QValidator.State.Acceptable, input_str, pos)
            return (QValidator.State.Intermediate, input_str, pos)
        except ValueError:
            return (QValidator.State.Invalid, input_str, pos)

class MemCopyMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Address input
        addr_label = QLabel("Destination Address")
        addr_label.setObjectName("Address")
        self.addr = ValidatingLineEdit(min_value=0x7E0000, max_value=0x7FFFFF)
        
        # Hex data input with custom validator
        data_label = QLabel("Data to Copy (Hex)")
        data_label.setObjectName("Data")
        self.data = QLineEdit()
        self.data.setValidator(HexValidator())
        
        layout.addWidget(addr_label)
        layout.addWidget(self.addr)
        layout.addWidget(data_label)
        layout.addWidget(self.data)
        
        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        # Ensure both fields are filled
        if not self.addr.text() or not self.data.text():
            return False
            
        # Validate hex data length is even
        cleaned_data = self.data.text().strip().replace(" ", "")
        if len(cleaned_data) % 2 != 0:
            return False
            
        return True

    def get_command(self) -> EventCommand:
        # Get address components
        addr = self.addr.get_value()
        
        hex_data = self.data.text().strip().replace(" ", "")
        data_bytes = bytes.fromhex(hex_data)
        
        return EventCommand.mem_copy(addr, data_bytes)
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 4:
            # Reconstruct address from bank_addr and bank
            addr = (args[1] << 16) | args[0]
            self.addr.set_value(addr)
            
            # Convert data bytes to hex string
            hex_str = " ".join(f"{b:02X}" for b in args[3])
            self.data.setText(hex_str)