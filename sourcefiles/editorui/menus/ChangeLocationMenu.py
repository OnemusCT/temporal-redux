from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget, QCheckBox, QHBoxLayout
from PyQt6.QtCore import Qt

# Import locations from lookups.py
from editorui.lookups import locations

class ChangeLocationMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Location selection
        location_label = QLabel("Location:")
        self.location = QComboBox()
        self.location.setMaximumWidth(200)  # Limit width to 400 pixels
        # Sort locations by ID and add to dropdown
        sorted_locations = sorted(locations, key=lambda x: x[0])
        for loc_id, loc_name in sorted_locations:
            self.location.addItem(f"{hex(loc_id)[2:].upper()}: {loc_name}", loc_id)

        # Coordinates
        coord_layout = QHBoxLayout()
        x_label = QLabel("X Coordinate:")
        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        y_label = QLabel("Y Coordinate:")
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        coord_layout.addWidget(x_label)
        coord_layout.addWidget(self.x_coord)
        coord_layout.addWidget(y_label)
        coord_layout.addWidget(self.y_coord)

        # Facing direction
        facing_label = QLabel("Facing Direction:")
        self.facing = QComboBox()
        self.facing.setMaximumWidth(100)  # Limit width to 100 pixels
        self.facing.addItem("Up", 0)
        self.facing.addItem("Down", 1)
        self.facing.addItem("Left", 2)
        self.facing.addItem("Right", 3)

        # Unknown value
        unknown_label = QLabel("Unknown Value:")
        self.unknown = ValidatingLineEdit(min_value=0, max_value=0x3)

        # Wait for VBlank
        self.wait_vblank = QCheckBox("Wait for VBlank")
        self.wait_vblank.stateChanged.connect(self._update_variant_visibility)

        # Command variant selection
        variant_layout = QHBoxLayout()
        variant_label = QLabel("Command Variant:")
        self.variant = QComboBox()
        self.variant.setMaximumWidth(100)  # Limit width to 100 pixels
        for cmd in [0xDC, 0xDD, 0xDE, 0xDF, 0xE0]:
            self.variant.addItem(f"0x{cmd:02X}", cmd)
        variant_layout.addWidget(variant_label)
        variant_layout.addWidget(self.variant)
        self.variant_widget = QWidget()
        self.variant_widget.setLayout(variant_layout)

        layout.addWidget(location_label)
        layout.addWidget(self.location)
        layout.addLayout(coord_layout)
        layout.addWidget(facing_label)
        layout.addWidget(self.facing)
        layout.addWidget(unknown_label)
        layout.addWidget(self.unknown)
        layout.addWidget(self.wait_vblank)
        layout.addWidget(self.variant_widget)

        result.setLayout(layout)
        return result

    def _update_variant_visibility(self, state):
        """Update visibility of variant selection based on wait_vblank state"""
        self.variant_widget.setEnabled(not self.wait_vblank.isChecked())

    def get_command(self) -> EventCommand:
        location = self.location.currentData()
        x_coord = self.x_coord.get_value()
        y_coord = self.y_coord.get_value()
        facing = self.facing.currentData()
        unknown = self.unknown.get_value() or 0

        wait_vblank = self.wait_vblank.isChecked()

        return EventCommand.change_location(
            location=location,
            x_coord=x_coord,
            y_coord=y_coord,
            facing=facing,
            unk=unknown,
            wait_vblank=wait_vblank
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 3:
            # Extract facing and unknown from first argument
            facing = (args[0] >> 0xB) & 0x03
            unknown = (args[0] >> 0x9) & 0x03
            location = args[0] & 0x1FF

            # Find and set location in dropdown
            index = self.location.findData(location)
            if index >= 0:
                self.location.setCurrentIndex(index)

            # Set coordinates
            self.x_coord.set_value(args[1])
            self.y_coord.set_value(args[2])

            # Set facing
            self.facing.setCurrentIndex(facing)

            # Set unknown value
            self.unknown.set_value(unknown)

            # Set wait_vblank based on command
            self.wait_vblank.setChecked(command == 0xE1)

            # Set variant if not using E1
            if command != 0xE1:
                index = self.variant.findData(command)
                if index >= 0:
                    self.variant.setCurrentIndex(index)