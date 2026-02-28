from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class TextboxMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        string_label = QLabel("String ID")
        self.string_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        self.box_type = QComboBox()
        self.box_type.addItem("Auto-positioned")
        self.box_type.addItem("Top")
        self.box_type.addItem("Bottom")
        self.box_type.addItem("Auto-positioned (Top)")
        self.box_type.addItem("Auto-positioned (Bottom)")
        self.box_type.addItem("Personal")

        self.first_line = QComboBox()
        self.last_line = QComboBox()
        for i in range(4):
            self.first_line.addItem(f"Line {i}")
            self.last_line.addItem(f"Line {i}")

        self.box_type.currentIndexChanged.connect(self._on_type_changed)

        layout.addWidget(string_label)
        layout.addWidget(self.string_id)
        layout.addWidget(self.box_type)
        layout.addWidget(QLabel("First Line"))
        layout.addWidget(self.first_line)
        layout.addWidget(QLabel("Last Line"))
        layout.addWidget(self.last_line)

        result.setLayout(layout)
        self._on_type_changed(0)  # Initialize state
        return result

    def _on_type_changed(self, index):
        # Show line selection only for auto-positioned types
        needs_lines = index in [0, 3, 4]
        self.first_line.setVisible(needs_lines)
        self.last_line.setVisible(needs_lines)

    def get_command(self) -> EventCommand:
        try:
            string_id = int(self.string_id.text(), 16)
            box_type = self.box_type.currentIndex()

            if box_type == 0:  # Auto
                return EventCommand.textbox_auto(string_id,
                                              self.first_line.currentIndex(),
                                              self.last_line.currentIndex())
            elif box_type == 1:  # Top
                return EventCommand.textbox_top(string_id)
            elif box_type == 2:  # Bottom
                return EventCommand.textbox_bottom(string_id)
            elif box_type == 3:  # Auto Top
                return EventCommand.textbox_auto_top(string_id,
                                                  self.first_line.currentIndex(),
                                                  self.last_line.currentIndex())
            elif box_type == 4:  # Auto Bottom
                return EventCommand.textbox_auto_bottom(string_id,
                                                    self.first_line.currentIndex(),
                                                    self.last_line.currentIndex())
            else:  # Personal
                return EventCommand.personal_textbox(string_id)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            self.string_id.setText(f"{args[0]:02X}")

            if command == 0xBB:  # Personal
                self.box_type.setCurrentIndex(5)
            elif command == 0xC0:  # Auto
                self.box_type.setCurrentIndex(0)
                if len(args) > 1:
                    self.first_line.setCurrentIndex(args[1] >> 2)
                    self.last_line.setCurrentIndex(args[1] & 0x03)
            elif command == 0xC1:  # Top
                self.box_type.setCurrentIndex(1)
            elif command == 0xC2:  # Bottom
                self.box_type.setCurrentIndex(2)
            elif command == 0xC3:  # Auto Top
                self.box_type.setCurrentIndex(3)
                if len(args) > 1:
                    self.first_line.setCurrentIndex(args[1] >> 2)
                    self.last_line.setCurrentIndex(args[1] & 0x03)
            elif command == 0xC4:  # Auto Bottom
                self.box_type.setCurrentIndex(4)
                if len(args) > 1:
                    self.first_line.setCurrentIndex(args[1] >> 2)
                    self.last_line.setCurrentIndex(args[1] & 0x03)