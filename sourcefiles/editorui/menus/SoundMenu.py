from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QWidget


# (label, opcode, sub, param1_label, param2_label)
# sub=None means opcode has no sub-command byte
# param1_label=None means no param1; param2_label=None means no param2
_COMMANDS = [
    ("Play song",               0xEA, None,  "Song",     None),
    ("Interrupt and play song", 0xEC, 0x14,  "Song",     None),
    ("Play sound (E8)",         0xE8, None,  "Sound",    None),
    ("Play sound (EC/19)",      0xEC, 0x19,  "Sound",    None),
    ("Sound volume (82)",       0xEC, 0x82,  "Duration", "Volume"),
    ("Unknown (83)",            0xEC, 0x83,  "Param 1",  "Param 2"),
    ("Song speed (85)",         0xEC, 0x85,  "Duration", "Speed"),
    ("Song speed (86)",         0xEC, 0x86,  "Duration", "Speed"),
    ("Change song state",       0xEC, 0x88,  None,       None),
    ("Song to silence",         0xEC, 0xF0,  None,       None),
    ("Sound to silence",        0xEC, 0xF2,  None,       None),
    ("Song volume (EB)",        0xEB, None,  "Duration", "Volume"),
]

# Map (opcode, sub) -> command index
_CMD_INDEX: dict[tuple, int] = {}
for _i, (_lbl, _op, _sub, _p1, _p2) in enumerate(_COMMANDS):
    _CMD_INDEX[(_op, _sub)] = _i


class SoundMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.cmd_combo = QComboBox()
        self.cmd_combo.addItems([c[0] for c in _COMMANDS])
        self.cmd_combo.currentIndexChanged.connect(self._on_cmd_changed)
        layout.addRow("Command", self.cmd_combo)

        self._p1_label = QLabel("Param 1")
        self.param1 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addRow(self._p1_label, self.param1)

        self._p2_label = QLabel("Param 2")
        self.param2 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addRow(self._p2_label, self.param2)

        result.setLayout(layout)
        self._on_cmd_changed(0)
        return result

    def _on_cmd_changed(self, index: int):
        _, _, _, p1_lbl, p2_lbl = _COMMANDS[index]
        show1 = p1_lbl is not None
        show2 = p2_lbl is not None
        self._p1_label.setVisible(show1)
        self.param1.setVisible(show1)
        self._p2_label.setVisible(show2)
        self.param2.setVisible(show2)
        if show1:
            self._p1_label.setText(p1_lbl)
        if show2:
            self._p2_label.setText(p2_lbl)

    def get_command(self) -> EventCommand:
        idx = self.cmd_combo.currentIndex()
        _, opcode, sub, p1_lbl, p2_lbl = _COMMANDS[idx]
        p1 = self.param1.get_value()
        p2 = self.param2.get_value()

        if idx == 0:    # Play song — 0xEA, 1 arg
            return EventCommand.generic_one_arg(0xEA, p1)
        elif idx == 1:  # Interrupt and play song — 0xEC 0x14 song
            return EventCommand.generic_command(0xEC, 0x14, p1)
        elif idx == 2:  # Play sound — 0xE8
            return EventCommand.generic_one_arg(0xE8, p1)
        elif idx == 3:  # Play sound EC/19
            return EventCommand.generic_command(0xEC, 0x19, p1)
        elif idx in (4, 5, 6, 7):
            return EventCommand.generic_command(opcode, sub, p1, p2)
        elif idx == 8:  # Change song state — 0xEC 0x88, no extra params
            return EventCommand.generic_command(0xEC, 0x88)
        elif idx == 9:  # Song to silence
            return EventCommand.generic_command(0xEC, 0xF0)
        elif idx == 10: # Sound to silence
            return EventCommand.generic_command(0xEC, 0xF2)
        else:           # idx == 11: Song volume EB
            return EventCommand.generic_two_arg(0xEB, p1, p2)

    def apply_arguments(self, command: int, args: list):
        if command == 0xEA:
            self._set_index(0)
            if args:
                self.param1.set_value(args[0])
        elif command == 0xE8:
            self._set_index(2)
            if args:
                self.param1.set_value(args[0])
        elif command == 0xEB:
            self._set_index(11)
            if len(args) >= 1:
                self.param1.set_value(args[0])
            if len(args) >= 2:
                self.param2.set_value(args[1])
        elif command == 0xEC:
            sub = args[0] if args else None
            _sub_map = {0x14: 1, 0x19: 3, 0x82: 4, 0x83: 5, 0x85: 6,
                        0x86: 7, 0x88: 8, 0xF0: 9, 0xF2: 10}
            idx = _sub_map.get(sub, 8)
            self._set_index(idx)
            if idx in (1, 3) and len(args) >= 2:
                self.param1.set_value(args[1])
            elif idx in (4, 5, 6, 7) and len(args) >= 2:
                self.param1.set_value(args[1])
                if len(args) >= 3:
                    self.param2.set_value(args[2])

    def _set_index(self, idx: int):
        self.cmd_combo.setCurrentIndex(idx)
        self._on_cmd_changed(idx)
