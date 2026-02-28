from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from eventcommand import EventCommand, Operation

from PyQt6.QtWidgets import (QComboBox, QLabel, QVBoxLayout, QWidget, 
                           QRadioButton, QButtonGroup, QHBoxLayout)

class ComparisonMenu(BaseCommandMenu):
    """Menu for memory comparison operations"""
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # First memory address/value
        mem1_label = QLabel("First Memory Address:")
        self.mem1 = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)

        # Second memory address (for MEM_TO_MEM)
        self.mem2_label = QLabel("Second Memory Address:")
        self.mem2 = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)

        # Value (for VAL_TO_MEM)
        self.value_label = QLabel("Value:")
        self.value = ValidatingLineEdit(min_value=0, max_value=0xFFFF)

        # Operation selection
        op_label = QLabel("Operation:")
        self.operation = QComboBox()
        for op in Operation:
            self.operation.addItem(op.name.replace('_', ' '), op.value)

        # Byte width selection
        width_label = QLabel("Width:")
        width_layout = QHBoxLayout()
        self.width_group = QButtonGroup()
        self.width_1byte = QRadioButton("1 Byte")
        self.width_2byte = QRadioButton("2 Bytes")
        self.width_group.addButton(self.width_1byte)
        self.width_group.addButton(self.width_2byte)
        self.width_1byte.setChecked(True)
        width_layout.addWidget(self.width_1byte)
        width_layout.addWidget(self.width_2byte)

        # Add widgets to layout
        layout.addWidget(mem1_label)
        layout.addWidget(self.mem1)
        layout.addWidget(op_label)
        layout.addWidget(self.operation)
        layout.addWidget(width_label)
        layout.addLayout(width_layout)
        
        # Create mem2/value widgets container
        self.value_container = QWidget()
        value_layout = QVBoxLayout()
        value_layout.addWidget(self.value_label)
        value_layout.addWidget(self.value)
        self.value_container.setLayout(value_layout)
        
        self.mem2_container = QWidget()
        mem2_layout = QVBoxLayout()
        mem2_layout.addWidget(self.mem2_label)
        mem2_layout.addWidget(self.mem2)
        self.mem2_container.setLayout(mem2_layout)
        
        layout.addWidget(self.value_container)
        layout.addWidget(self.mem2_container)

        result.setLayout(layout)
        return result
    
    def validate(self) -> bool:
        if self.mem1.get_value() is None:
            return False
        if self.mem2.isVisible() and self.mem2.get_value() is None:
            return False
        if self.value.isVisible() and self.value.get_value() is None:
            return False
        return True

    def get_command(self) -> EventCommand:
        address = self.mem1.get_value()
        operation = Operation(self.operation.currentData())
        num_bytes = 2 if self.width_2byte.isChecked() else 1

        if self.mem2.isVisible():
            mem2 = self.mem2.get_value()
            return EventCommand.mem_to_mem_compare(
                address1=address,
                address2=mem2,
                operation=operation,
                num_bytes=num_bytes,
                jump_bytes=0
            )
        else:
            value = self.value.get_value()
            return EventCommand.if_mem_op_value(
                address=address,
                operation=operation,
                value=value,
                num_bytes=num_bytes,
                bytes_jump=0
            )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 3:
            if command in [0x14, 0x15]:  # MEM_TO_MEM
                self.mem1.set_value(0x7F0200 + args[0] * 2)
                self.mem2.set_value(0x7F0200 + args[1] * 2)
                self.operation.setCurrentIndex(args[2])
                self.width_2byte.setChecked(command == 0x15)
                self.width_1byte.setChecked(command == 0x14)
                self.mem2_container.setVisible(True)
                self.value_container.setVisible(False)
            else:  # VAL_TO_MEM
                self.mem1.set_value(0x7F0200 + args[0] * 2)
                self.value.set_value(args[1])
                self.operation.setCurrentIndex(args[2])
                self.width_2byte.setChecked(command in [0x13])
                self.width_1byte.setChecked(command in [0x12, 0x16])
                self.mem2_container.setVisible(False)
                self.value_container.setVisible(True)