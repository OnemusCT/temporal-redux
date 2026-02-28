from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from editorui.menus.MemCopyMenu import HexValidator
from jetsoftime.eventcommand import EventCommand, event_commands

from PyQt6.QtWidgets import QComboBox, QLabel, QLineEdit, QVBoxLayout, QWidget

class MultiModeMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Mode selection
        mode_label = QLabel("Mode")
        mode_label.setObjectName("Mode")
        self.mode = QComboBox()
        self.mode.addItems(["00", "20", "30", "40", "50", "80"])
        self.mode.currentIndexChanged.connect(self._update_ui)
        
        # Param inputs
        param1_label = QLabel("Param 1")
        param1_label.setObjectName("Param1")
        self.param1 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        param2_label = QLabel("Param 2")
        param2_label.setObjectName("Param2") 
        self.param2 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        param3_label = QLabel("Param 3")
        param3_label.setObjectName("Param3")
        self.param3 = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        # Hex data input for mode 80
        data_label = QLabel("Data (Hex)")
        data_label.setObjectName("Data")
        self.data = QLineEdit()
        self.data.setValidator(HexValidator())
        
        # Add all widgets
        layout.addWidget(mode_label)
        layout.addWidget(self.mode)
        layout.addWidget(param1_label)
        layout.addWidget(self.param1)
        layout.addWidget(param2_label)
        layout.addWidget(self.param2)
        layout.addWidget(param3_label)
        layout.addWidget(self.param3)
        layout.addWidget(data_label)
        layout.addWidget(self.data)
        
        result.setLayout(layout)
        self._update_ui(0)  # Initialize UI state
        return result
        
    def _update_ui(self, index):
        """Update visible parameters based on mode"""
        mode = int(self.mode.currentText(), 16)
        
        # Show/hide param1
        show_param1 = mode in [0x20, 0x30, 0x40, 0x50, 0x80]
        self.param1.setVisible(show_param1)
        self.param1.parent().findChild(QLabel, "Param1").setVisible(show_param1)
        
        # Show/hide param2
        show_param2 = mode in [0x20, 0x30, 0x40, 0x50]
        self.param2.setVisible(show_param2)
        self.param2.parent().findChild(QLabel, "Param2").setVisible(show_param2)
        
        # Show/hide param3
        show_param3 = mode in [0x40, 0x50]
        self.param3.setVisible(show_param3)
        self.param3.parent().findChild(QLabel, "Param3").setVisible(show_param3)
        
        # Show/hide hex data input
        show_data = mode == 0x80
        self.data.setVisible(show_data)
        self.data.parent().findChild(QLabel, "Data").setVisible(show_data)

    def validate(self) -> bool:
        mode = int(self.mode.currentText(), 16)
        
        if mode in [0x20, 0x30, 0x40, 0x50, 0x80]:
            if self.param1.get_value() is None:
                return False
                
        if mode in [0x20, 0x30, 0x40, 0x50]:
            if self.param2.get_value() is None:
                return False
                
        if mode in [0x40, 0x50]:
            if self.param3.get_value() is None:
                return False
                
        if mode == 0x80:
            # Validate hex data has even length
            cleaned_data = self.data.text().strip().replace(" ", "")
            if not cleaned_data or len(cleaned_data) % 2 != 0:
                return False
                
        return True

    def get_command(self) -> EventCommand:
        cmd = event_commands[0x88].copy()
        mode = int(self.mode.currentText(), 16)
        
        cmd.args = [mode]  # Always include mode
        
        if mode in [0x20, 0x30, 0x40, 0x50, 0x80]:
            cmd.args.append(self.param1.get_value())
            
        if mode in [0x20, 0x30, 0x40, 0x50]:
            cmd.args.append(self.param2.get_value())
            
        if mode in [0x40, 0x50]:
            cmd.args.append(self.param3.get_value())
            
        if mode == 0x80:
            # Convert hex string to bytes
            hex_data = self.data.text().strip().replace(" ", "")
            data_bytes = bytes.fromhex(hex_data)
            cmd.args.append(len(data_bytes) + 2)  # Add length
            cmd.args.append(bytearray(data_bytes))  # Add data
            
        return cmd
        
    def apply_arguments(self, command: int, args: list):
        if len(args) > 0:
            # Set mode
            mode = args[0]
            mode_index = self.mode.findText(f"{mode:02X}")
            if mode_index >= 0:
                self.mode.setCurrentIndex(mode_index)
            
            # Set params based on mode
            if mode in [0x20, 0x30, 0x40, 0x50, 0x80] and len(args) > 1:
                self.param1.set_value(args[1])
                
            if mode in [0x20, 0x30, 0x40, 0x50] and len(args) > 2:
                self.param2.set_value(args[2])
                
            if mode in [0x40, 0x50] and len(args) > 3:
                self.param3.set_value(args[3])
                
            if mode == 0x80 and len(args) > 4:
                # Convert data bytes to hex string
                hex_str = " ".join(f"{b:02X}" for b in args[4])
                self.data.setText(hex_str)