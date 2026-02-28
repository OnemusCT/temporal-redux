from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class SetSpeedMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        # Speed type selector
        type_layout = QHBoxLayout()
        type_label = QLabel("Speed Source:")
        self.speed_type = QComboBox()
        self.speed_type.addItem("Direct Value")
        self.speed_type.addItem("From Memory")
        self.speed_type.currentIndexChanged.connect(self._update_ui)
        type_layout.addWidget(type_label)
        type_layout.addWidget(self.speed_type)

        # Speed value input
        value_layout = QHBoxLayout()
        self.value_label = QLabel("Speed Value:")
        self.speed_value = ValidatingLineEdit(min_value=0, max_value=0xFF)
        value_layout.addWidget(self.value_label)
        value_layout.addWidget(self.speed_value)

        # Memory address input
        addr_layout = QHBoxLayout()
        self.addr_label = QLabel("Memory Address:")
        self.speed_addr = ValidatingLineEdit(min_value=0x7F0200, max_value=0x7F0400)
        addr_layout.addWidget(self.addr_label)
        addr_layout.addWidget(self.speed_addr)

        layout.addLayout(type_layout)
        layout.addLayout(value_layout)
        layout.addLayout(addr_layout)

        result.setLayout(layout)
        self._update_ui(0)  # Initialize for direct value
        return result

    def _update_ui(self, index):
        """Update UI based on speed source"""
        is_direct = index == 0
        self.value_label.setVisible(is_direct)
        self.speed_value.setVisible(is_direct)
        self.addr_label.setVisible(not is_direct)
        self.speed_addr.setVisible(not is_direct)

    def validate(self) -> bool:
        if self.speed_type.currentIndex() == 0:
            return self.speed_value.get_value() is not None
        else:
            return self.speed_addr.get_value() is not None

    def get_command(self) -> EventCommand:
        if not self.validate():
            raise CommandError("Invalid speed value or address")

        if self.speed_type.currentIndex() == 0:
            return EventCommand.set_speed(self.speed_value.get_value())
        else:
            return EventCommand.set_speed_from_mem(self.speed_addr.get_value())

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            if command == 0x89:
                self.speed_type.setCurrentIndex(0)
                self.speed_value.set_value(args[0])
            else:  # 0x8A
                self.speed_type.setCurrentIndex(1)
                self.speed_addr.set_value(0x7F0200 + args[0] * 2)