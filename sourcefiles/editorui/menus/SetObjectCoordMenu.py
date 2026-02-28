from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

class SetObjectCoordMenu(BaseCommandMenu):
    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Coordinate type selection
        type_label = QLabel("Coordinate Type")
        type_label.setObjectName("Type")
        self.coord_type = QComboBox()
        self.coord_type.addItems(["Tiles", "Pixels"])
        
        # Coordinates
        x_label = QLabel("X Coordinate")
        x_label.setObjectName("X")
        self.x_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        y_label = QLabel("Y Coordinate")
        y_label.setObjectName("Y")
        self.y_coord = ValidatingLineEdit(min_value=0, max_value=0xFF)
        
        layout.addWidget(type_label)
        layout.addWidget(self.coord_type)
        layout.addWidget(x_label)
        layout.addWidget(self.x_coord)
        layout.addWidget(y_label)
        layout.addWidget(self.y_coord)
        
        result.setLayout(layout)
        return result

    def get_command(self) -> EventCommand:
        x = self.x_coord.get_value()
        y = self.y_coord.get_value()
        
        if self.coord_type.currentText() == "Tiles":
            return EventCommand.set_object_coordinates_tile(x, y)
        else:
            return EventCommand.set_object_coordinates_pixels(x, y)

    def apply_arguments(self, command: int, args: list):
        if len(args) >= 2:
            if command == 0x8B:
                self.coord_type.setCurrentText("Tiles")
                self.x_coord.set_value(args[0])
                self.y_coord.set_value(args[1])
            else:  # 0x8D
                self.coord_type.setCurrentText("Pixels")
                self.x_coord.set_value(args[0] >> 4)  # Divide by 16
                self.y_coord.set_value(args[1] >> 4)  # Divide by 16
