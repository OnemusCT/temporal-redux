from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class EquipItemMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()

        pc_label = QLabel("PC ID")
        self.pc_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        item_label = QLabel("Item ID")
        self.item_id = ValidatingLineEdit(min_value=0, max_value=0xFF)

        layout.addWidget(pc_label)
        layout.addWidget(self.pc_id)
        layout.addWidget(item_label)
        layout.addWidget(self.item_id)

        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        try:
            pc_id = int(self.pc_id.text(), 16)
            item_id = int(self.item_id.text(), 16)
            return EventCommand.equip_item(pc_id, item_id)
        except ValueError:
            print("ERROR")

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            self.pc_id.setText(f"{args[0]:02X}")
            self.item_id.setText(f"{args[1]:02X}")