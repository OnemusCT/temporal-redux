from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QRadioButton, QLabel, QVBoxLayout, QWidget, QButtonGroup


class BitMathMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Operation selection
        self.op_group = QButtonGroup()
        self.set_bit = QRadioButton("Set Single Bit")
        self.reset_bit = QRadioButton("Reset Single Bit")
        self.set_bits = QRadioButton("Set Multiple Bits")
        self.reset_bits = QRadioButton("Reset Multiple Bits")
        self.toggle_bits = QRadioButton("Toggle Bits")
        
        self.op_group.addButton(self.set_bit)
        self.op_group.addButton(self.reset_bit)
        self.op_group.addButton(self.set_bits)
        self.op_group.addButton(self.reset_bits)
        self.op_group.addButton(self.toggle_bits)
        
        # Add radio buttons to layout first
        layout.addWidget(self.set_bit)
        layout.addWidget(self.reset_bit)
        layout.addWidget(self.set_bits)
        layout.addWidget(self.reset_bits)
        layout.addWidget(self.toggle_bits)

        # Address input
        self.addr_label = QLabel("Memory Address (7F0000-7F0400)")
        self.addr = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7F0400)
        layout.addWidget(self.addr_label)
        layout.addWidget(self.addr)

        # Single bit input 
        self.bit_label = QLabel("Bit (0-7)")
        self.bit = ValidatingLineEdit(min_value=0, max_value=7)
        layout.addWidget(self.bit_label)
        layout.addWidget(self.bit)

        # Bitmask input
        self.mask_label = QLabel("Bitmask (00-FF)")
        self.bitmask = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addWidget(self.mask_label)
        layout.addWidget(self.bitmask)

        # Set initial radio button state
        self.set_bit.setChecked(True)
        
        # Connect radio buttons to update UI after all widgets are created
        self.set_bit.toggled.connect(self._update_visible_fields)
        self.reset_bit.toggled.connect(self._update_visible_fields)
        self.set_bits.toggled.connect(self._update_visible_fields)
        self.reset_bits.toggled.connect(self._update_visible_fields)
        self.toggle_bits.toggled.connect(self._update_visible_fields)

        result.setLayout(layout)
        
        # Initialize visible fields after everything is set up
        self._update_visible_fields()
        
        return result

    def _update_visible_fields(self):
        """Update which input fields are visible based on selected operation."""
        # Address is always visible
        self.addr_label.setVisible(True)
        self.addr.setVisible(True)
        
        # Show bit field for single bit operations
        is_single_bit = self.set_bit.isChecked() or self.reset_bit.isChecked()
        self.bit_label.setVisible(is_single_bit)
        self.bit.setVisible(is_single_bit)
        
        # Show bitmask field for multiple bit operations
        is_multi_bit = self.set_bits.isChecked() or self.reset_bits.isChecked() or self.toggle_bits.isChecked()
        self.mask_label.setVisible(is_multi_bit)
        self.bitmask.setVisible(is_multi_bit)

    def validate(self) -> bool:
        if self.addr.get_value() is None:
            return False
            
        if self.set_bit.isChecked() or self.reset_bit.isChecked():
            return self.bit.get_value() is not None
        else:  # Multiple bits operations
            return self.bitmask.get_value() is not None

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        address = self.addr.get_value()

        if self.set_bit.isChecked():
            return EventCommand.set_reset_bit(address, 1 << self.bit.get_value(), True)
        elif self.reset_bit.isChecked():
            return EventCommand.set_reset_bit(address, 1 << self.bit.get_value(), False)
        elif self.set_bits.isChecked():
            return EventCommand.set_reset_bits(address, self.bitmask.get_value(), True)
        elif self.reset_bits.isChecked():
            return EventCommand.set_reset_bits(address, self.bitmask.get_value(), False)
        else:  # toggle_bits
            return EventCommand.toggle_bits(address, self.bitmask.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return

        if command in [0x63, 0x64, 0x65, 0x66]:  # Single bit operations
            # Extract bit number from args[0]
            if command in [0x65, 0x66]:  # Local memory commands
                bit_num = args[0] & 0x7
                addr = 0x7F0000 + args[1]
                if args[0] & 0x80:  # High byte access
                    addr += 0x100
            else:  # Script memory commands
                bit_num = args[0] & 0x7
                addr = 0x7F0200 + (args[1] * 2)

            # Set UI state
            self.addr.set_value(addr)
            self.bit.set_value(bit_num)
            if command in [0x63, 0x65]:
                self.set_bit.setChecked(True)
            else:
                self.reset_bit.setChecked(True)

        else:  # Multiple bits operations
            addr = 0x7F0200 + (args[1] * 2)
            self.addr.set_value(addr)
            self.bitmask.set_value(args[0])
            
            if command == 0x69:
                self.set_bits.setChecked(True)
            elif command == 0x67:
                self.reset_bits.setChecked(True)
            else:  # 0x6B
                self.toggle_bits.setChecked(True)