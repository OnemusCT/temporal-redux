"""Location / Overworld properties display panel (read-only).

Shows the tileset indices, palette index, map data index, and scroll
boundaries decoded from the 14-byte location properties record returned
by MapManager.get_location_props().
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QLabel, QVBoxLayout,
)


class LocationPropertiesPanel(QWidget):
    """Read-only panel showing the current location's property record."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        ts_box = QGroupBox("Tilesets & Palette")
        ts_form = QFormLayout(ts_box)
        self._l12_ts = QLabel("-")
        self._l3_ts = QLabel("-")
        self._palette = QLabel("-")
        self._map_idx = QLabel("-")
        ts_form.addRow("L12 Tileset:", self._l12_ts)
        ts_form.addRow("L3 Tileset:", self._l3_ts)
        ts_form.addRow("Palette:", self._palette)
        ts_form.addRow("Map Index:", self._map_idx)
        layout.addWidget(ts_box)

        sb_box = QGroupBox("Scroll Boundaries")
        sb_form = QFormLayout(sb_box)
        self._sb_left = QLabel("-")
        self._sb_top = QLabel("-")
        self._sb_right = QLabel("-")
        self._sb_bottom = QLabel("-")
        sb_form.addRow("Left:", self._sb_left)
        sb_form.addRow("Top:", self._sb_top)
        sb_form.addRow("Right:", self._sb_right)
        sb_form.addRow("Bottom:", self._sb_bottom)
        layout.addWidget(sb_box)

        layout.addStretch()

    def load(self, loc_props: dict) -> None:
        """Populate from a MapManager.get_location_props() result dict."""
        self._l12_ts.setText(str(loc_props.get('l12_tileset', '-')))
        self._l3_ts.setText(str(loc_props.get('l3_tileset', '-')))
        self._palette.setText(str(loc_props.get('palette', '-')))
        self._map_idx.setText(str(loc_props.get('map_index', '-')))
        self._sb_left.setText(str(loc_props.get('scroll_left', '-')))
        self._sb_top.setText(str(loc_props.get('scroll_top', '-')))
        self._sb_right.setText(str(loc_props.get('scroll_right', '-')))
        self._sb_bottom.setText(str(loc_props.get('scroll_bottom', '-')))

    def clear(self) -> None:
        """Reset all labels to the placeholder dash."""
        for w in (self._l12_ts, self._l3_ts, self._palette, self._map_idx,
                  self._sb_left, self._sb_top, self._sb_right, self._sb_bottom):
            w.setText('-')
