from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.CommandError import CommandError
from jetsoftime.eventcommand import EventCommand
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class GotoMenu(BaseCommandMenu):
    """Menu for forward/backward jump commands"""

    def __init__(self):
        super().__init__()
        self._updating: bool = False

    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        type_label = QLabel("Jump Type:")
        self.jump_type = QComboBox()
        self.jump_type.addItem("Forward")
        self.jump_type.addItem("Backward")

        target_label = QLabel("Target Address: (hex)")
        self.target_address = ValidatingLineEdit(min_value=0, max_value=0xFFFF)

        bytes_label = QLabel("Jump Bytes: (computed, hex)")
        self.jump_bytes = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(type_label)
        layout.addWidget(self.jump_type)
        layout.addWidget(target_label)
        layout.addWidget(self.target_address)
        layout.addWidget(bytes_label)
        layout.addWidget(self.jump_bytes)
        result.setLayout(layout)

        self.jump_type.currentIndexChanged.connect(self._on_target_address_changed)
        self.target_address.textChanged.connect(self._on_target_address_changed)

        return result

    def _on_target_address_changed(self) -> None:
        if self._updating or not hasattr(self, 'jump_bytes'):
            return
        if self._current_address is None:
            return
        try:
            target = int(self.target_address.text(), 16)
        except ValueError:
            self.jump_bytes.clear()
            return
        if self.jump_type.currentIndex() == 0:
            jump_bytes = target - self._current_address - 1
        else:
            jump_bytes = self._current_address + 1 - target
        if 0 <= jump_bytes <= 0xFF:
            self.jump_bytes.set_value(jump_bytes)
        else:
            self.jump_bytes.clear()

    def set_address(self, address: int | None) -> None:
        super().set_address(address)
        if hasattr(self, 'jump_bytes'):
            is_computed = address is not None
            self.jump_bytes.setReadOnly(is_computed)
            self.jump_bytes.setStyleSheet("background-color: palette(window);" if is_computed else "")

    def get_command(self) -> EventCommand:
        jump_bytes = self.jump_bytes.get_value()
        if jump_bytes is None:
            raise CommandError("Jump Bytes is required")
        if self.jump_type.currentIndex() == 0:
            return EventCommand.jump_forward(jump_bytes)
        else:
            return EventCommand.jump_back(jump_bytes)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 1:
            if command == 0x10:
                self.jump_type.setCurrentIndex(0)
            else:
                self.jump_type.setCurrentIndex(1)
            jump_bytes = args[0]
            self.jump_bytes.set_value(jump_bytes)
            if self._current_address is not None:
                if command == 0x10:
                    target = self._current_address + 1 + jump_bytes
                else:
                    target = self._current_address + 1 - jump_bytes
                self._updating = True
                self.target_address.set_value(target)
                self._updating = False