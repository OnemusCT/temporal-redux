from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QFormLayout, QWidget


class ScrollLayersMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.param1 = ValidatingLineEdit(min_value=0, max_value=0xFFFF)
        self.scroll_l1 = QCheckBox()
        self.scroll_l2 = QCheckBox()
        self.scroll_l3 = QCheckBox()
        self.param3 = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addRow("Param 1", self.param1)
        layout.addRow("Scroll L1", self.scroll_l1)
        layout.addRow("Scroll L2", self.scroll_l2)
        layout.addRow("Scroll L3", self.scroll_l3)
        layout.addRow("Param 3", self.param3)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        flags = (
            self.scroll_l1.isChecked()
            | (self.scroll_l2.isChecked() << 1)
            | (self.scroll_l3.isChecked() << 2)
        )
        return EventCommand.generic_command(0xE6, self.param1.get_value(), flags, self.param3.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            self.param1.set_value(args[0])
        if len(args) >= 2:
            self.scroll_l1.setChecked(bool(args[1] & 0x1))
            self.scroll_l2.setChecked(bool(args[1] & 0x2))
            self.scroll_l3.setChecked(bool(args[1] & 0x4))
        if len(args) >= 3:
            self.param3.set_value(args[2])
