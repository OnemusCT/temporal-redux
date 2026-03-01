from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.MemCopyMenu import HexValidator
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, event_commands

from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
)


_COLOR_NAMES = ["Black", "Blue", "Red", "Purple", "Green", "Cyan", "Yellow", "White"]


class ColorMathMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QFormLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Addition", "Subtraction", "Assignment"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addRow("Mode", self.mode_combo)

        # --- Addition / Subtraction widgets ---
        self._color_label = QLabel("Color")
        self.color_combo = QComboBox()
        self.color_combo.addItems(_COLOR_NAMES)
        layout.addRow(self._color_label, self.color_combo)

        self._index_label = QLabel("Index")
        self.index_field = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addRow(self._index_label, self.index_field)

        self._colors_label = QLabel("Colors")
        self.colors_field = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addRow(self._colors_label, self.colors_field)

        self._start_label = QLabel("Start Intensity")
        self.start_int = ValidatingLineEdit(min_value=0, max_value=0xF)
        layout.addRow(self._start_label, self.start_int)

        self._end_label = QLabel("End Intensity")
        self.end_int = ValidatingLineEdit(min_value=0, max_value=0xF)
        layout.addRow(self._end_label, self.end_int)

        self._duration_label = QLabel("Duration")
        self.duration = ValidatingLineEdit(min_value=0, max_value=0xFF)
        layout.addRow(self._duration_label, self.duration)

        # --- Assignment widgets ---
        self._unk_label = QLabel("Unk 1.0F")
        self.unk_field = ValidatingLineEdit(min_value=0, max_value=0xF)
        layout.addRow(self._unk_label, self.unk_field)

        self._palette_label = QLabel("Palette")
        self.palette_field = ValidatingLineEdit(min_value=0, max_value=0xF)
        layout.addRow(self._palette_label, self.palette_field)

        self._start_color_label = QLabel("Start Color")
        self.start_color_field = ValidatingLineEdit(min_value=0, max_value=0xF)
        layout.addRow(self._start_color_label, self.start_color_field)

        self._data_label = QLabel("Data (Hex)")
        self.data_field = QLineEdit()
        self.data_field.setValidator(HexValidator())
        layout.addRow(self._data_label, self.data_field)

        result.setLayout(layout)
        self._on_mode_changed(0)
        return result

    def _addsub_widgets(self):
        return [
            self._color_label, self.color_combo,
            self._index_label, self.index_field,
            self._colors_label, self.colors_field,
            self._start_label, self.start_int,
            self._end_label, self.end_int,
            self._duration_label, self.duration,
        ]

    def _assign_widgets(self):
        return [
            self._unk_label, self.unk_field,
            self._palette_label, self.palette_field,
            self._start_color_label, self.start_color_field,
            self._data_label, self.data_field,
        ]

    def _on_mode_changed(self, index: int):
        is_assign = (index == 2)
        for w in self._addsub_widgets():
            w.setVisible(not is_assign)
        for w in self._assign_widgets():
            w.setVisible(is_assign)

    def get_command(self) -> EventCommand:
        cmd = event_commands[0x2E].copy()
        mode_idx = self.mode_combo.currentIndex()
        if mode_idx == 0:  # Addition
            color_idx = self.color_combo.currentIndex()
            cmd.arg_lens = [1, 1, 1, 1, 1]
            cmd.args = [
                0x40 | color_idx,
                self.index_field.get_value(),
                self.colors_field.get_value(),
                ((self.start_int.get_value() & 0xF) << 4) | (self.end_int.get_value() & 0xF),
                self.duration.get_value(),
            ]
        elif mode_idx == 1:  # Subtraction
            color_idx = self.color_combo.currentIndex()
            cmd.arg_lens = [1, 1, 1, 1, 1]
            cmd.args = [
                0x50 | (7 - color_idx),
                self.index_field.get_value(),
                self.colors_field.get_value(),
                ((self.start_int.get_value() & 0xF) << 4) | (self.end_int.get_value() & 0xF),
                self.duration.get_value(),
            ]
        else:  # Assignment
            unk = self.unk_field.get_value() or 0
            palette = self.palette_field.get_value() or 0
            start_color = self.start_color_field.get_value() or 0
            hex_text = self.data_field.text().strip().replace(" ", "")
            data_bytes = bytes.fromhex(hex_text) if hex_text else b""
            cmd.arg_lens = [1, 1, 2, len(data_bytes)]
            cmd.args = [
                0x80 | unk,
                (palette << 4) | start_color,
                len(data_bytes) + 2,
                bytearray(data_bytes),
            ]
        return cmd

    def apply_arguments(self, command: int, args: list):
        if not args:
            return
        mode = args[0] & 0xF0
        if mode == 0x40:
            self.mode_combo.setCurrentIndex(0)
            self.color_combo.setCurrentIndex(args[0] & 0xF)
            self._fill_addsub(args)
        elif mode == 0x50:
            self.mode_combo.setCurrentIndex(1)
            self.color_combo.setCurrentIndex(7 - (args[0] & 0xF))
            self._fill_addsub(args)
        elif mode == 0x80:
            self.mode_combo.setCurrentIndex(2)
            self.unk_field.set_value(args[0] & 0xF)
            if len(args) >= 2:
                self.palette_field.set_value((args[1] >> 4) & 0xF)
                self.start_color_field.set_value(args[1] & 0xF)
            if len(args) >= 4:
                data = args[3]
                if isinstance(data, (bytes, bytearray)):
                    self.data_field.setText(data.hex().upper())

    def _fill_addsub(self, args: list):
        if len(args) >= 2:
            self.index_field.set_value(args[1])
        if len(args) >= 3:
            self.colors_field.set_value(args[2])
        if len(args) >= 4:
            self.start_int.set_value((args[3] >> 4) & 0xF)
            self.end_int.set_value(args[3] & 0xF)
        if len(args) >= 5:
            self.duration.set_value(args[4])
