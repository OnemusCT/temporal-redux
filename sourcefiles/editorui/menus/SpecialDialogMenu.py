from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand
from editorui.lookups import pcs

from PyQt6.QtWidgets import QComboBox, QVBoxLayout, QWidget

class SpecialDialogMenu(BaseCommandMenu):

    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        self.mode = QComboBox()
        self.mode.addItem("Replace Characters")
        self.mode.addItem("Rename Character")
        self.mode.addItem("Custom Dialog ID")

        self.dialog_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        self.char_id = QComboBox()
        for id, name in pcs.items():
            self.char_id.addItem(name, id)

        self.mode.currentIndexChanged.connect(self._on_mode_changed)

        layout.addWidget(self.mode)
        layout.addWidget(self.dialog_id)
        layout.addWidget(self.char_id)

        result.setLayout(layout)
        self._on_mode_changed(0)  # Initialize state
        return result

    def _on_mode_changed(self, index):
        self.dialog_id.setVisible(index == 2)
        self.char_id.setVisible(index == 1)

    def get_command(self) -> EventCommand:
        try:
            mode = self.mode.currentIndex()
            if mode == 0:
                return EventCommand.replace_characters()
            elif mode == 1:
                return EventCommand.rename_character(self.char_id.currentData())
            else:
                dialog_id = int(self.dialog_id.text(), 16)
                return EventCommand.special_dialog(dialog_id)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            arg = args[0]
            if arg == 0:
                self.mode.setCurrentIndex(0)  # Replace characters
            elif (arg & 0xC0) == 0xC0:
                self.mode.setCurrentIndex(1)  # Rename character
                self.char_id.setCurrentIndex(arg & 0x3F)
            else:
                self.mode.setCurrentIndex(2)  # Custom dialog
                self.dialog_id.setText(f"{arg:02X}")