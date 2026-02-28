from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

_byte_commands = [
    0x4F,  # assignment with value
    0x51,  # mem-to-mem assignment
    0x53,  # assignment from address
    0x58,  # inverse assignment
    0x5D,  # add operation
    0x5F,  # subtract operation
    0x71,  # increment
    0x75,  # set byte
    0x4C,  # loads one byte
]

_word_commands = [
    0x50,  # two byte version of 4F
    0x52,  # two byte version of 51
    0x54,  # two byte version of 53
    0x59,  # two byte version of 58
    0x5E,  # two byte version of 5D
    0x60,  # two byte version of 5F
    0x72,  # two byte version of 71
    0x76,  # two byte version of 75
    0x4D,  # loads two bytes
]

class MemToMemAssignMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        from_label = QLabel("From Address")
        self.source_addr = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)

        to_label = QLabel("To Address")
        self.dest_addr = ValidatingLineEdit(min_value=0x7F0000, max_value=0x7FFFFF)

        num_bytes_label = QLabel("Size")
        self.num_bytes = QComboBox()
        self.num_bytes.addItem("Byte", 1)
        self.num_bytes.addItem("Word", 2)
        #num_bytes.setItemData(0, 1)
        layout.addWidget(from_label)
        layout.addWidget(self.source_addr)

        layout.addWidget(to_label)
        layout.addWidget(self.dest_addr)

        layout.addWidget(num_bytes_label)
        layout.addWidget(self.num_bytes)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            source_addr = int(self.source_addr.text(), 16)
            dest_addr = int(self.dest_addr.text(), 16)
            num_bytes = self.num_bytes.currentData()
            return EventCommand.assign_mem_to_mem(source_addr, dest_addr, num_bytes)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command, args):
        if command == 0x48 or command == 0x49:
            # 48: aaaaaa - address to load from, oo - offset to store to (*2, +7F0200)
            # 49: aaaaaa - address to load from, oo - offset to store to (/2 +7F0200)
            source_addr = args[0]
            if command == 0x48:
                dest_addr = 0x7F0200 + (args[1] * 2)
            else:  # 0x49
                dest_addr = 0x7F0200 + (args[1] // 2)
        elif command == 0x4C or command == 0x4D:
            # 4C: aaaaaa - address to store to, oo - offset to load from (*2, +7F0200)
            # 4D: aaaaaa - address to store to, oo - offset to load from (*2, +7F0200)
            source_addr = 0x7F0200 + (args[1] * 2)
            dest_addr = args[0]

        elif command == 0x51 or command == 0x52:
            # 51/52: aa - offset to load from (*2, +7F0200), oo - offset to store to (*2, +7F0200)
            source_addr = 0x7F0200 + (args[0] * 2)
            dest_addr = 0x7F0200 + (args[1] * 2)

        elif command == 0x53 or command == 0x54:
            # 53/54: aaaa - address to load from (+7F0000), oo - offset to store to (*2, +7F0200)
            source_addr = 0x7F0000 + args[0]
            dest_addr = 0x7F0200 + (args[1] * 2)

        else:  # 0x58 or 0x59
            # 58/59: oo - offset to load from (*2, +7F0200), aaaa - address to store to (+7F0000)
            source_addr = 0x7F0200 + (args[0] * 2)
            dest_addr = 0x7F0000 + args[1]

        self.source_addr.setText("{:02X}".format(source_addr))
        self.dest_addr.setText("{:02X}".format(dest_addr))
        if command in _byte_commands:
            self.num_bytes.setCurrentIndex(0)
        elif command in _word_commands:
            self.num_bytes.setCurrentIndex(1)
        else:
            print("ERROR!!!")