from editorui.menus.BaseCommandMenu import BaseCommandMenu
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QGridLayout, QLabel, QVBoxLayout, QWidget


class BattleMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Create grid layout for checkboxes
        grid = QGridLayout()

        # All flags in a simple list
        self.flags = [
            ('no_win_pose', "No win pose"),
            ('bottom_menu', "Bottom menu"),
            ('small_pc_sol', "Small PC Sol."),
            ('unused_108', "Unused 1.08"),
            ('static_enemies', "Static enemies"),
            ('special_event', "Special event"),
            ('unknown_140', "Unknown 1.40"),
            ('no_run', "No run"),
            ('unknown_201', "Unknown 2.01"),
            ('unknown_202', "Unknown 2.02"),
            ('unknown_204', "Unknown 2.04"),
            ('unknown_208', "Unknown 2.08"),
            ('unknown_210', "Unknown 2.10"),
            ('no_game_over', "No game over"),
            ('map_music', "Map music"),
            ('regroup', "Regroup")
        ]

        # Add checkboxes in a 2-column grid
        for i, (attr_name, label) in enumerate(self.flags):
            checkbox = QCheckBox(label)
            setattr(self, attr_name, checkbox)
            grid.addWidget(checkbox, i // 2, i % 2)
            checkbox.stateChanged.connect(self._update_hex_display)

        # Add hex display of current values
        self.hex_display = QLabel()
        self.hex_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_hex_display()

        layout.addLayout(grid)
        layout.addWidget(self.hex_display)
        result.setLayout(layout)
        return result

    def _update_hex_display(self):
        """Update the hex display to show current flag values"""
        byte1 = 0
        byte2 = 0

        # First byte flags
        for i, (attr_name, _) in enumerate(self.flags[:8]):
            if getattr(self, attr_name).isChecked():
                byte1 |= (1 << i)

        # Second byte flags
        for i, (attr_name, _) in enumerate(self.flags[8:]):
            if getattr(self, attr_name).isChecked():
                byte2 |= (1 << i)

        self.hex_display.setText(f"Value: {byte1:02X} {byte2:02X}")

    def validate(self) -> bool:
        return True  # Always valid since checkboxes can't have invalid state

    def get_command(self) -> EventCommand:
        return EventCommand.battle(
            **{attr_name: getattr(self, attr_name).isChecked()
               for attr_name, _ in self.flags}
        )

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return

        # First byte flags
        for i, (attr_name, _) in enumerate(self.flags[:8]):
            getattr(self, attr_name).setChecked(args[0] & (1 << i))

        # Second byte flags
        for i, (attr_name, _) in enumerate(self.flags[8:]):
            getattr(self, attr_name).setChecked(args[1] & (1 << i))