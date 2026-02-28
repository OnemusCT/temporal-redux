from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class ValToMemAssignMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        value_label = QLabel("Value")
        self.value = ValidatingLineEdit(min_value=0, max_value=0xFFFF)

        addr_label = QLabel("Destination Address")
        self.dest_addr = ValidatingLineEdit(min_value=0x7E0000, max_value=0x7FFFFF)

        size_label = QLabel("Size")
        self.size = QComboBox()
        self.size.addItem("Byte", 1)
        self.size.addItem("Word", 2)

        layout.addWidget(value_label)
        layout.addWidget(self.value)
        layout.addWidget(addr_label)
        layout.addWidget(self.dest_addr)
        layout.addWidget(size_label)
        layout.addWidget(self.size)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            value = int(self.value.text(), 16)
            dest_addr = int(self.dest_addr.text(), 16)
            return EventCommand.assign_val_to_mem(value, dest_addr, self.size.currentData())
        except ValueError as e:
            print(f"ERROR: {e}")

    def apply_arguments(self, command: int, args: list):
        if len(args) < 2:
            return

        # Decode based on command type
        if command in [0x4A, 0x4B]:  # Any memory address
            value = args[1]
            dest_addr = args[0]
        elif command in [0x4F, 0x50]:  # Script memory
            value = args[0]
            dest_addr = 0x7F0200 + (args[1] * 2)
        else:  # 0x56 - Bank 7F
            value = args[0]
            dest_addr = 0x7F0000 + args[1]

        self.value.setText(f"{value:X}")
        self.dest_addr.setText(f"{dest_addr:06X}")

        # Set size based on command
        if command in [0x4A, 0x4F, 0x56]:  # Byte commands
            self.size.setCurrentIndex(0)
        else:  # Word commands
            self.size.setCurrentIndex(1)