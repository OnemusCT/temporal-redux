from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand, FuncSync
from editorui.lookups import pcs

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

class CallObjFuncMenu(BaseCommandMenu):

    FUNC_NAMES = [
        "Startup",
        "Activate",
        "Touch",
        "Function 0",
        "Function 1",
        "Function 2",
        "Function 3",
        "Function 4",
        "Function 5",
        "Function 6",
        "Function 7",
        "Function 8",
        "Function 9",
        "Function A",
        "Function B",
        "Function C"
    ]

    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Target type (Object/PC)
        type_label = QLabel("Target Type")
        type_label.setObjectName("Type")
        self.target_type = QComboBox()
        self.target_type.addItems(["Object", "PC"])
        self.target_type.currentIndexChanged.connect(self._update_ui)
        
        # Target ID - either dropdown for PC or input for Object
        target_label = QLabel("Target ID")
        target_label.setObjectName("Target")
        
        # PC Dropdown
        self.pc_select = QComboBox()
        for id, name in pcs.items():
            if name != "Epoch":
                self.pc_select.addItem(name, id)
            
        # Object ID input
        self.obj_id = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        # Function sync type
        sync_label = QLabel("Sync Type")
        sync_label.setObjectName("Sync")
        self.sync_type = QComboBox()
        self.sync_type.addItems(["Continuous", "Sync", "Halt"])
        
        # Priority (hex 0-F)
        priority_label = QLabel("Priority (0-F)")
        priority_label.setObjectName("Priority")
        self.priority = ValidatingLineEdit(min_value=0, max_value=0xF)
        
        # Function selection
        func_label = QLabel("Function")
        func_label.setObjectName("Function")
        self.function = QComboBox()
        self.function.addItems(self.FUNC_NAMES)
        
        layout.addWidget(type_label)
        layout.addWidget(self.target_type)
        layout.addWidget(target_label)
        layout.addWidget(self.pc_select)
        layout.addWidget(self.obj_id)
        layout.addWidget(sync_label)
        layout.addWidget(self.sync_type)
        layout.addWidget(priority_label)
        layout.addWidget(self.priority)
        layout.addWidget(func_label)
        layout.addWidget(self.function)
        
        result.setLayout(layout)
        self._update_ui(0)
        return result
        
    def _update_ui(self, index):
        """Update UI based on target type"""
        is_pc = self.target_type.currentText() == "PC"
        self.pc_select.setVisible(is_pc)
        self.obj_id.setVisible(not is_pc)

    def get_command(self) -> EventCommand:
        is_pc = self.target_type.currentText() == "PC"
        sync_type = {
            "Continuous": FuncSync.CONT,
            "Sync": FuncSync.SYNC,
            "Halt": FuncSync.HALT
        }[self.sync_type.currentText()]
        
        if is_pc:
            return EventCommand.call_pc_function(
                self.pc_select.currentData(),
                self.function.currentIndex(),
                self.priority.get_value(),
                sync_type
            )
        else:
            return EventCommand.call_obj_function(
                self.obj_id.get_value(),
                self.function.currentIndex(),
                self.priority.get_value(),
                sync_type
            )
        
    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            # Set target type based on command
            is_pc = command in [0x05, 0x06, 0x07]
            self.target_type.setCurrentText("PC" if is_pc else "Object")
            
            # Set target ID
            target_id = args[0] // 2
            if is_pc:
                index = self.pc_select.findData(target_id)
                if index >= 0:
                    self.pc_select.setCurrentIndex(index)
            else:
                self.obj_id.set_value(target_id)
            
            # Set sync type based on command
            sync_map = {
                0x02: "Continuous", 0x05: "Continuous",
                0x03: "Sync", 0x06: "Sync",
                0x04: "Halt", 0x07: "Halt"
            }
            self.sync_type.setCurrentText(sync_map[command])
            
            # Set priority and function from second argument
            self.priority.set_value((args[1] >> 4) & 0xF)
            self.function.setCurrentIndex(args[1] & 0xF)