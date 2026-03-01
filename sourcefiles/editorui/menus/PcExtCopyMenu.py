from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


# (opcode, display_text, arg0_label, arg1_label)
_OPS = [
    (0x3A, "ext[slot] = imm",            "Value (0x00-0xFF)",       "Ext Slot (0x00-0xFF)"),
    (0x3D, "ext[slot] = mem[local]",     "Local Offset (0x00-0xFF)", "Ext Slot (0x00-0xFF)"),
    (0x3E, "mem[local] = ext[slot]",     "Ext Slot (0x00-0xFF)",    "Local Offset (0x00-0xFF)"),
    (0x70, "mem[local] = party[slot]",   "Party Slot (0x00-0xFF)",  "Local Offset (0x00-0xFF)"),
    (0x74, "mem16[local] = ext16[slot]", "Ext Slot (0x00-0xFF)",    "Local Offset (0x00-0xFF)"),
    (0x78, "ext16[slot] = mem16[local]", "Local Offset (0x00-0xFF)", "Ext Slot (0x00-0xFF)"),
]

_OPCODE_INDEX = {op[0]: i for i, op in enumerate(_OPS)}


class PcExtCopyMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        op_label = QLabel("Operation:")
        self.op_combo = QComboBox()
        for opcode, text, _, _ in _OPS:
            self.op_combo.addItem(text, opcode)

        self.arg0_label = QLabel(_OPS[0][2])
        self.arg0 = ValidatingLineEdit(min_value=0, max_value=0xFF)

        self.arg1_label = QLabel(_OPS[0][3])
        self.arg1 = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(op_label)
        layout.addWidget(self.op_combo)
        layout.addWidget(self.arg0_label)
        layout.addWidget(self.arg0)
        layout.addWidget(self.arg1_label)
        layout.addWidget(self.arg1)

        result.setLayout(layout)

        self.op_combo.currentIndexChanged.connect(self._update_labels)
        return result

    def _update_labels(self):
        idx = self.op_combo.currentIndex()
        if 0 <= idx < len(_OPS):
            self.arg0_label.setText(_OPS[idx][2])
            self.arg1_label.setText(_OPS[idx][3])

    def validate(self) -> bool:
        return self.arg0.get_value() is not None and self.arg1.get_value() is not None

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid input values")

        opcode = self.op_combo.currentData()
        a0 = self.arg0.get_value()
        a1 = self.arg1.get_value()

        if opcode == 0x3A:
            return EventCommand.pc_copy_imm_to_ext(a0, a1)
        elif opcode == 0x3D:
            return EventCommand.pc_copy_local_to_ext(a0, a1)
        elif opcode == 0x3E:
            return EventCommand.pc_copy_ext_to_local(a0, a1)
        elif opcode == 0x70:
            return EventCommand.pc_copy_party_to_local(a0, a1)
        elif opcode == 0x74:
            return EventCommand.pc_copy_ext16_to_local(a0, a1)
        else:  # 0x78
            return EventCommand.pc_copy_local_to_ext16(a0, a1)

    def apply_arguments(self, command: int, args: list):
        idx = _OPCODE_INDEX.get(command)
        if idx is None:
            return
        self.op_combo.setCurrentIndex(idx)
        self._update_labels()
        if len(args) >= 2:
            self.arg0.set_value(args[0])
            self.arg1.set_value(args[1])
