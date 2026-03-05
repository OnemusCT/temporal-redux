"""Tile property editor panel.

Displays and edits the 3-byte tile property for the tile currently under
the cursor (or most-recently selected).
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QComboBox, QVBoxLayout, QLabel,
)
from PyQt6.QtCore import pyqtSignal

from editorui.mapeditor.tile_props import TileProperties


_SOLIDITY_NAMES = [
    "0 - Fully walkable",
    "1 - Block NW",
    "2 - Block NE",
    "3 - Block N half",
    "4 - Block SW",
    "5 - Block W half",
    "6 - Block diagonal NW-SE",
    "7 - Block N+W",
    "8 - Block SE",
    "9 - Block diagonal NE-SW",
    "10 - Block E half",
    "11 - Fully solid",
]


class TilePropsPanel(QWidget):
    """Editor for a single tile's property bytes."""

    props_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        self._cached_props = TileProperties(raw=b'\x00\x00\x00')
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        sol_box = QGroupBox("Solidity")
        sol_form = QFormLayout(sol_box)
        self._solidity = QComboBox()
        for name in _SOLIDITY_NAMES:
            self._solidity.addItem(name)
        sol_form.addRow("Quad:", self._solidity)
        layout.addWidget(sol_box)

        misc_box = QGroupBox("Z-Plane / Wind")
        misc_form = QFormLayout(misc_box)
        self._z_plane = QCheckBox("Z-Plane (layer above sprite)")
        misc_form.addRow(self._z_plane)
        self._wind_dir = QSpinBox(); self._wind_dir.setRange(0, 7)
        self._wind_speed = QSpinBox(); self._wind_speed.setRange(0, 31)
        misc_form.addRow("Wind Dir (0-7):", self._wind_dir)
        misc_form.addRow("Wind Speed (0-31):", self._wind_speed)
        layout.addWidget(misc_box)

        flag_box = QGroupBox("Flags")
        flag_form = QFormLayout(flag_box)
        self._is_door = QCheckBox("Door trigger")
        self._is_battle = QCheckBox("Battle encounter")
        self._is_npc_col = QCheckBox("NPC collision")
        flag_form.addRow(self._is_door)
        flag_form.addRow(self._is_battle)
        flag_form.addRow(self._is_npc_col)
        layout.addWidget(flag_box)

        self._raw_label = QLabel("Raw: 00 00 00")
        layout.addWidget(self._raw_label)
        layout.addStretch()

        for w in (self._solidity, self._wind_dir, self._wind_speed):
            w.currentIndexChanged.connect(self._on_changed) if isinstance(w, QComboBox) \
                else w.valueChanged.connect(self._on_changed)
        for cb in (self._z_plane, self._is_door, self._is_battle, self._is_npc_col):
            cb.stateChanged.connect(self._on_changed)

    def load(self, props: TileProperties) -> None:
        self._updating = True
        self._cached_props = props
        self._solidity.setCurrentIndex(min(props.solidity_quad,
                                           self._solidity.count() - 1))
        self._z_plane.setChecked(props.z_plane)
        self._wind_dir.setValue(props.wind_direction)
        self._wind_speed.setValue(props.wind_speed)
        self._is_door.setChecked(props.is_door)
        self._is_battle.setChecked(props.is_battle)
        self._is_npc_col.setChecked(props.is_npc_collision)
        self._raw_label.setText(
            f"Raw: {props.b0:02X} {props.b1:02X} {props.b2:02X}"
        )
        self._updating = False

    def current_props(self) -> TileProperties:
        b0 = (self._cached_props.b0 & ~0x7C) | ((self._solidity.currentIndex() & 0x0F) << 2) | (int(self._z_plane.isChecked()) << 6)
        b1 = self._wind_dir.value() | (self._wind_speed.value() << 3)
        b2 = (self._cached_props.b2 & ~0x70) | (
            (int(self._is_door.isChecked()) << 4)
            | (int(self._is_battle.isChecked()) << 5)
            | (int(self._is_npc_col.isChecked()) << 6)
        )
        return TileProperties(raw=bytes([b0, b1, b2]))

    def _on_changed(self, *_) -> None:
        if not self._updating:
            self.props_changed.emit(self.current_props())
