from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QCheckBox, QFormLayout, QWidget


_FLAG_LABELS = [
    "Copy L1",
    "Copy L2",
    "Copy L3",
    "Cpy L1 Prop",
    "Unknown 9.10",
    "Unknown 9.20",
    "Z Plane",
    "Wind",
]


class CopyTilesMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.wait_vblank = QCheckBox()
        self.src_left = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.src_top = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.src_right = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.src_bottom = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.dst_left = ValidatingLineEdit(min_value=0, max_value=0xFF)
        self.dst_top = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addRow("Wait VBlank", self.wait_vblank)
        layout.addRow("Src Left", self.src_left)
        layout.addRow("Src Top", self.src_top)
        layout.addRow("Src Right", self.src_right)
        layout.addRow("Src Bottom", self.src_bottom)
        layout.addRow("Dest Left", self.dst_left)
        layout.addRow("Dest Top", self.dst_top)

        self._flag_checkboxes = []
        for label in _FLAG_LABELS:
            cb = QCheckBox()
            self._flag_checkboxes.append(cb)
            layout.addRow(label, cb)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        opcode = 0xE4 if self.wait_vblank.isChecked() else 0xE5
        flags = sum(cb.isChecked() << i for i, cb in enumerate(self._flag_checkboxes))
        return EventCommand.generic_command(
            opcode,
            self.src_left.get_value(),
            self.src_top.get_value(),
            self.src_right.get_value(),
            self.src_bottom.get_value(),
            self.dst_left.get_value(),
            self.dst_top.get_value(),
            flags,
        )

    def apply_arguments(self, command: int, args: list):
        self.wait_vblank.setChecked(command == 0xE4)
        coords = [self.src_left, self.src_top, self.src_right, self.src_bottom, self.dst_left, self.dst_top]
        for i, field in enumerate(coords):
            if i < len(args):
                field.set_value(args[i])
        if len(args) >= 7:
            for i, cb in enumerate(self._flag_checkboxes):
                cb.setChecked(bool(args[6] >> i & 1))
