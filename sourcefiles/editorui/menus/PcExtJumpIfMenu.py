from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PcExtJumpIfMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        lhs_label = QLabel("Ext Slot (lhs, 0x00-0xFF):")
        self.lhs_ext = ValidatingLineEdit(min_value=0, max_value=0xFF)

        rhs_label = QLabel("Compare Value (0x00-0xFF):")
        self.rhs_val = ValidatingLineEdit(min_value=0, max_value=0xFF)

        op_label = QLabel("Compare Op (0x00-0xFF):")
        self.cmp_op = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(lhs_label)
        layout.addWidget(self.lhs_ext)
        layout.addWidget(rhs_label)
        layout.addWidget(self.rhs_val)
        layout.addWidget(op_label)
        layout.addWidget(self.cmp_op)

        result.setLayout(layout)
        return result

    def validate(self) -> bool:
        return (self.lhs_ext.get_value() is not None
                and self.rhs_val.get_value() is not None
                and self.cmp_op.get_value() is not None)

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        return EventCommand.pc_jumpif_ext(
            self.lhs_ext.get_value(),
            self.rhs_val.get_value(),
            self.cmp_op.get_value(),
            0,  # jump bytes recalculated automatically
        )

    def apply_arguments(self, command: int, args: list):
        # args: [lhs_ext, rhs_val, cmp_op, jump_off]
        if len(args) >= 3:
            self.lhs_ext.set_value(args[0])
            self.rhs_val.set_value(args[1])
            self.cmp_op.set_value(args[2])
