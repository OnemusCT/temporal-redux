from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QRadioButton, QLabel, QVBoxLayout, QWidget, QButtonGroup, QComboBox


class MemByteMathMenu(BaseCommandMenu):
    """Menu for memory-to-memory byte math operations."""
    
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Operation selection
        self.op_group = QButtonGroup()
        self.add = QRadioButton("Add Memory")
        self.subtract = QRadioButton("Subtract Memory")
        
        self.op_group.addButton(self.add)
        self.op_group.addButton(self.subtract)
        self.add.setChecked(True)

        # For addition, can select 1 or 2 bytes
        byte_label = QLabel("Number of Bytes")
        self.num_bytes = QComboBox()
        self.num_bytes.addItem("1 Byte", 1)
        self.num_bytes.addItem("2 Bytes", 2)
        
        # Only show byte selection for addition
        self.add.toggled.connect(lambda checked: byte_label.setVisible(checked))
        self.add.toggled.connect(lambda checked: self.num_bytes.setVisible(checked))

        # Source address input
        from_label = QLabel("Source Address (7F0200-7F0400)")
        self.from_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        # Destination address input
        to_label = QLabel("Destination Address (7F0200-7F0400)")
        self.to_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)

        # Add widgets to layout
        layout.addWidget(self.add)
        layout.addWidget(self.subtract)
        layout.addWidget(byte_label)
        layout.addWidget(self.num_bytes)
        layout.addWidget(from_label)
        layout.addWidget(self.from_addr)
        layout.addWidget(to_label)
        layout.addWidget(self.to_addr)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.from_addr.get_value() is not None and 
                self.to_addr.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        from_addr = self.from_addr.get_value()
        to_addr = self.to_addr.get_value()

        if self.add.isChecked():
            return EventCommand.add_mem_to_mem(
                from_addr, 
                to_addr, 
                self.num_bytes.currentData()
            )
        else:  # subtract
            return EventCommand.subtract_mem_from_mem(from_addr, to_addr)

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return
            
        # Both args are memory offsets - convert back to full addresses
        from_addr = 0x7F0200 + (args[0] * 2)
        to_addr = 0x7F0200 + (args[1] * 2)
        
        self.from_addr.set_value(from_addr)
        self.to_addr.set_value(to_addr)
        
        if command == 0x5D:  # 1 byte add
            self.add.setChecked(True)
            self.num_bytes.setCurrentIndex(0)
        elif command == 0x5E:  # 2 byte add
            self.add.setChecked(True)
            self.num_bytes.setCurrentIndex(1)
        elif command == 0x61:  # subtract
            self.subtract.setChecked(True)