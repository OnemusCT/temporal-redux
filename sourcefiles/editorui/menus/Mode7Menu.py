from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, event_commands

from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget
)


_SPECIAL_ITEMS = [
    "Black Circle (90)",
    "Mode 91",
    "Left-Right Swipe Open (92)",
    "Right-Left Swipe Open (93)",
    "Left-Right Swipe Close (94)",
    "Right-Left Swipe Close (95)",
    "Reset (96)",
    "Mode 97",
    "Mode 98",
]

# Indices in _SPECIAL_ITEMS that have 3 extra param bytes (0x90 and 0x97)
_HAS_PARAMS = {0, 7}  # index 0 → 0x90, index 7 → 0x97


class Mode7Menu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        outer = QVBoxLayout()

        # Top-level mode combo: Scene / Special
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Scene", "Special"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        mode_form = QFormLayout()
        mode_form.addRow("Mode", self.mode_combo)
        outer.addLayout(mode_form)

        # Stacked widget — page 0 = Scene, page 1 = Special
        self.stack = QStackedWidget()

        scene_page = QWidget()
        scene_layout = QFormLayout()
        self.scene_field = ValidatingLineEdit(min_value=0, max_value=0x89)
        scene_layout.addRow("Scene", self.scene_field)
        scene_page.setLayout(scene_layout)
        self.stack.addWidget(scene_page)

        special_page = QWidget()
        special_layout = QFormLayout()
        self.special_combo = QComboBox()
        self.special_combo.addItems(_SPECIAL_ITEMS)
        self.special_combo.currentIndexChanged.connect(self._on_special_changed)
        special_layout.addRow("Special", self.special_combo)

        self._param_labels = []
        self._param_fields = []
        for i in range(1, 4):
            lbl = QLabel(f"Param {i}")
            field = ValidatingLineEdit(min_value=0, max_value=0xFF)
            self._param_labels.append(lbl)
            self._param_fields.append(field)
            special_layout.addRow(lbl, field)

        special_page.setLayout(special_layout)
        self.stack.addWidget(special_page)

        outer.addWidget(self.stack)
        result.setLayout(outer)

        self._on_mode_changed(0)
        return result

    def _on_mode_changed(self, index: int):
        self.stack.setCurrentIndex(index)

    def _on_special_changed(self, index: int):
        has_params = index in _HAS_PARAMS
        for lbl, field in zip(self._param_labels, self._param_fields):
            lbl.setVisible(has_params)
            field.setVisible(has_params)

    def get_command(self) -> EventCommand:
        cmd = event_commands[0xFF].copy()
        if self.mode_combo.currentIndex() == 0:
            # Scene mode
            cmd.arg_lens = [1]
            cmd.args = [self.scene_field.get_value()]
        else:
            # Special mode
            idx = self.special_combo.currentIndex()
            scene_byte = 0x90 + idx
            if idx in _HAS_PARAMS:
                cmd.arg_lens = [1, 1, 1, 1]
                cmd.args = [
                    scene_byte,
                    self._param_fields[0].get_value(),
                    self._param_fields[1].get_value(),
                    self._param_fields[2].get_value(),
                ]
            else:
                cmd.arg_lens = [1]
                cmd.args = [scene_byte]
        return cmd

    def apply_arguments(self, command: int, args: list):
        if not args:
            return
        val = args[0]
        if val < 0x90:
            self.mode_combo.setCurrentIndex(0)
            self.scene_field.set_value(val)
        else:
            self.mode_combo.setCurrentIndex(1)
            idx = val - 0x90
            if 0 <= idx < self.special_combo.count():
                self.special_combo.setCurrentIndex(idx)
            self._on_special_changed(idx)
            if idx in _HAS_PARAMS and len(args) >= 4:
                for i in range(3):
                    self._param_fields[i].set_value(args[i + 1])
