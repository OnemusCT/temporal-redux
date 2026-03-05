"""Map header editor panel.

Exposes all 6-byte MapHeader fields (layer sizes, scrolling, priority,
translucency) as editable spin-boxes / check-boxes.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QVBoxLayout
)
from PyQt6.QtCore import pyqtSignal

from sourcefiles.mapedit.mapdata import MapHeader


class MapHeaderPanel(QWidget):
    """Editable map header panel. Emits header_changed(MapHeader)."""

    header_changed = pyqtSignal(object) # MapHeader

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._updating = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        dim_box = QGroupBox("Layer Dimensions")
        dim_form = QFormLayout(dim_box)
        self._l1w = self._spin(16, 64, 16); dim_form.addRow("L1 Width", self._l1w)
        self._l1h = self._spin(16, 64, 16); dim_form.addRow("L1 Height", self._l1h)
        self._l2w = self._spin(16, 64, 16); dim_form.addRow("L2 Width", self._l2w)
        self._l2h = self._spin(16, 64, 16); dim_form.addRow("L2 Height", self._l2h)
        self._l3w = self._spin(16, 64, 16); dim_form.addRow("L3 Width", self._l3w)
        self._l3h = self._spin(16, 64, 16); dim_form.addRow("L3 Height", self._l3h)
        layout.addWidget(dim_box)

        scroll_box = QGroupBox("Scrolling")
        scroll_form = QFormLayout(scroll_box)
        self._l1s = self._spin(0, 7); scroll_form.addRow("L1 Scroll", self._l1s)
        self._l2s = self._spin(0, 255); scroll_form.addRow("L2 Scroll", self._l2s)
        self._l3s = self._spin(0, 255); scroll_form.addRow("L3 Scroll", self._l3s)
        self._draw_l3 = QCheckBox("Draw L3")
        scroll_form.addRow(self._draw_l3)
        layout.addWidget(scroll_box)

        pri_box = QGroupBox("Priority (byte 4)")
        pri_form = QFormLayout(pri_box)
        self._pri_checks: list[QCheckBox] = []
        labels = ["L1 Main", "L2 Main", "L3 Main", "Sprites Main",
                  "L1 Sub", "L2 Sub", "L3 Sub", "Sprites Sub"]
        for i, lbl in enumerate(labels):
            cb = QCheckBox(lbl)
            pri_form.addRow(cb)
            self._pri_checks.append(cb)
        layout.addWidget(pri_box)

        fx_box = QGroupBox("Color Effects (byte 5)")
        fx_form = QFormLayout(fx_box)
        self._fx_checks: list[QCheckBox] = []
        fx_labels = ["L1 Translucent", "L2 Translucent", "L3 Translucent",
                     "Unk 5.3", "Sprites Trans", "Def Color Trans",
                     "Half Intensity", "Subtractive"]
        for lbl in fx_labels:
            cb = QCheckBox(lbl)
            fx_form.addRow(cb)
            self._fx_checks.append(cb)
        layout.addWidget(fx_box)

        for spin in (self._l1w, self._l1h, self._l2w, self._l2h,
                     self._l3w, self._l3h, self._l1s, self._l2s, self._l3s):
            spin.valueChanged.connect(self._on_changed)
        self._draw_l3.stateChanged.connect(self._on_changed)
        for cb in self._pri_checks + self._fx_checks:
            cb.stateChanged.connect(self._on_changed)

        layout.addStretch()

    @staticmethod
    def _spin(lo: int, hi: int, step: int = 1) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setSingleStep(step)
        return s

    def load(self, header: MapHeader) -> None:
        """Populate all controls from *header* without triggering signals."""
        self._updating = True
        self._l1w.setValue(header.l1_width)
        self._l1h.setValue(header.l1_height)
        self._l2w.setValue(header.l2_width)
        self._l2h.setValue(header.l2_height)
        self._l3w.setValue(header.l3_width)
        self._l3h.setValue(header.l3_height)
        self._l1s.setValue(header.l1_scroll)
        self._l2s.setValue(header.l2_scroll)
        self._l3s.setValue(header.l3_scroll)
        self._draw_l3.setChecked(header.draw_l3)
        for i, cb in enumerate(self._pri_checks):
            cb.setChecked(bool(header.priority & (1 << i)))
        for i, cb in enumerate(self._fx_checks):
            cb.setChecked(bool(header.color_fx & (1 << i)))
        self._updating = False

    def current_header(self) -> MapHeader:
        """Read all controls and return a MapHeader."""
        pri = sum(1 << i for i, cb in enumerate(self._pri_checks) if cb.isChecked())
        fx = sum(1 << i for i, cb in enumerate(self._fx_checks) if cb.isChecked())
        return MapHeader(
            l1_width = self._l1w.value(),
            l1_height = self._l1h.value(),
            l2_width = self._l2w.value(),
            l2_height = self._l2h.value(),
            l3_width = self._l3w.value(),
            l3_height = self._l3h.value(),
            l1_scroll = self._l1s.value(),
            l2_scroll = self._l2s.value(),
            l3_scroll = self._l3s.value(),
            draw_l3 = self._draw_l3.isChecked(),
            priority = pri,
            color_fx = fx,
        )

    def _on_changed(self, *_) -> None:
        if not self._updating:
            self.header_changed.emit(self.current_header())
