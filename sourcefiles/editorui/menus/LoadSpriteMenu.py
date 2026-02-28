from editorui.menus.BaseCommandMenu import BaseCommandMenu
from editorui.menus.ValidatingLineEdit import ValidatingLineEdit
from jetsoftime.eventcommand import EventCommand
from editorui.lookups import npcs, enemies, pcs

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLabel, QVBoxLayout, QWidget

class LoadSpriteMenu(BaseCommandMenu):

    def command_widget(self) -> QWidget:
        result = QWidget()
        layout = QVBoxLayout()
        
        # Sprite type selection
        type_label = QLabel("Sprite Type")
        type_label.setObjectName("Type")
        self.sprite_type = QComboBox()
        self.sprite_type.addItems(["PC (party)", "PC (always)", "NPC", "Enemy"])
        self.sprite_type.currentIndexChanged.connect(self._update_ui)
        
        # PC selection for both PC modes
        pc_label = QLabel("PC")
        pc_label.setObjectName("PC")
        self.pc_select = QComboBox()
        for id, name in pcs.items():
            if name != "Epoch":
                self.pc_select.addItem(name, id)
            
        # NPC selection
        npc_label = QLabel("NPC")
        npc_label.setObjectName("NPC")
        self.npc_select = QComboBox()
        for id, name in npcs.items():
            self.npc_select.addItem(name, id)
            
        # Enemy selection
        enemy_label = QLabel("Enemy")
        enemy_label.setObjectName("Enemy")
        self.enemy_select = QComboBox()
        for id, name in enemies.items():
            self.enemy_select.addItem(name, id)
            
        # Enemy options
        self.static_enemy = QCheckBox("Static Enemy")
        slot_label = QLabel("Slot")
        slot_label.setObjectName("Slot")
        self.slot = ValidatingLineEdit(min_value=0, max_value=0xF)
        
        # Add widgets
        layout.addWidget(type_label)
        layout.addWidget(self.sprite_type)
        layout.addWidget(pc_label)
        layout.addWidget(self.pc_select)
        layout.addWidget(npc_label)
        layout.addWidget(self.npc_select)
        layout.addWidget(enemy_label)
        layout.addWidget(self.enemy_select)
        layout.addWidget(self.static_enemy)
        layout.addWidget(slot_label)
        layout.addWidget(self.slot)
        
        result.setLayout(layout)
        self._update_ui(0)
        return result
        
    def _update_ui(self, index):
        """Update UI based on sprite type"""
        sprite_type = self.sprite_type.currentText()
        
        # Show/hide PC selection
        is_pc = sprite_type.startswith("PC")
        self.pc_select.setVisible(is_pc)
        self.pc_select.parent().findChild(QLabel, "PC").setVisible(is_pc)
        
        # Show/hide NPC selection
        is_npc = sprite_type == "NPC"
        self.npc_select.setVisible(is_npc)
        self.npc_select.parent().findChild(QLabel, "NPC").setVisible(is_npc)
        
        # Show/hide enemy selection and options
        is_enemy = sprite_type == "Enemy"
        self.enemy_select.setVisible(is_enemy)
        self.enemy_select.parent().findChild(QLabel, "Enemy").setVisible(is_enemy)
        self.static_enemy.setVisible(is_enemy)
        self.slot.setVisible(is_enemy)
        self.slot.parent().findChild(QLabel, "Slot").setVisible(is_enemy)

    def get_command(self) -> EventCommand:
        sprite_type = self.sprite_type.currentText()
        
        if sprite_type == "PC (party)":
            return EventCommand.load_pc_in_party(self.pc_select.currentData())
        elif sprite_type == "PC (always)":
            return EventCommand.load_pc_always(self.pc_select.currentData())
        elif sprite_type == "NPC":
            return EventCommand.load_npc(self.npc_select.currentData())
        else:  # Enemy
            return EventCommand.load_enemy(
                self.enemy_select.currentData(),
                self.slot.get_value(),
                self.static_enemy.isChecked()
            )
            
    def apply_arguments(self, command: int, args: list):
        if command in [0x57, 0x5C, 0x62, 0x68, 0x6A, 0x6C, 0x6D]:
            # PC (party) commands
            self.sprite_type.setCurrentText("PC (party)")
            pc_map = {
                0x57: 0,  # Crono
                0x5C: 1,  # Marle
                0x62: 2,  # Lucca
                0x6A: 3,  # Robo
                0x68: 4,  # Frog
                0x6C: 5,  # Ayla
                0x6D: 6   # Magus
            }
            self.pc_select.setCurrentIndex(pc_map[command])
            
        elif command == 0x81:
            # PC (always)
            self.sprite_type.setCurrentText("PC (always)")
            if len(args) >= 1:
                self.pc_select.setCurrentIndex(args[0])
                
        elif command == 0x82:
            # NPC
            self.sprite_type.setCurrentText("NPC")
            if len(args) >= 1:
                index = self.npc_select.findData(args[0])
                if index >= 0:
                    self.npc_select.setCurrentIndex(index)
                    
        elif command == 0x83:
            # Enemy
            self.sprite_type.setCurrentText("Enemy")
            if len(args) >= 2:
                index = self.enemy_select.findData(args[0])
                if index >= 0:
                    self.enemy_select.setCurrentIndex(index)
                self.static_enemy.setChecked(bool(args[1] & 0x80))
                self.slot.set_value(args[1] & 0x7F)