from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QRadioButton, QLabel, QVBoxLayout, QWidget, QButtonGroup


class PcExtBitMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        self.op_group = QButtonGroup()
        self.set_btn = QRadioButton("Set Bit")
        self.clear_btn = QRadioButton("Clear Bit")
        self.op_group.addButton(self.set_btn)
        self.op_group.addButton(self.clear_btn)
        self.set_btn.setChecked(True)

        layout.addWidget(self.set_btn)
        layout.addWidget(self.clear_btn)

        bit_label = QLabel("Bit Number (0-7):")
        self.bit = ValidatingLineEdit(min_value=0, max_value=7)

        ext_label = QLabel("Ext Slot (0x00-0xFF):")
        self.ext_slot = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(bit_label)
        layout.addWidget(self.bit)
        layout.addWidget(ext_label)
        layout.addWidget(self.ext_slot)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return self.bit.get_value() is not None and self.ext_slot.get_value() is not None

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        bit = self.bit.get_value()
        ext = self.ext_slot.get_value()
        if self.set_btn.isChecked():
            return EventCommand.pc_bitset_ext(bit, ext)
        else:
            return EventCommand.pc_bitclear_ext(bit, ext)

    def apply_arguments(self, command: int, args: list):
        if command == 0x45:
            self.set_btn.setChecked(True)
        else:
            self.clear_btn.setChecked(True)
        if len(args) >= 2:
            self.bit.set_value(args[0] & 0x7F)
            self.ext_slot.set_value(args[1])
