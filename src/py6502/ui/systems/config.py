import dearpygui.dearpygui as dpg
from importlib import resources

AVAILABLE_CONFIGS = {
    "APPLE_I": {
        "name": "Apple I",
        "description": "Apple I emulator",
        "ram": {
            "options": [0x1000, 0x2000],
            "start_address": 0x0000,
            "default_size": 0x1000,
            "multiple": False,
            "accepts_binary": True,
            "binary_changeable": False,
            "default_binary": None
        },
        "rom": {
            "options": [0x100],
            "start_address": 0xFF00,
            "default_size": 0x100,
            "multiple": False,
            "accepts_binary": True,
            "binary_changeable": False,
            "default_binary": ("resource", ("py6502.sim.assets.bios", "apple1-wozmon.bin"))
        },
        "peripherals": [
            {
                "type": "Apple1",
                "start_address": 0xD010,
                "size": 0x0004,
                "address_changeable": False,
                "removable": False
            }
        ]
    },
    "CUSTOM_6502": {
        "name": "Custom 6502 System",
        "description": "Configure your own 6502 system",
        "ram": {
            "options": "any",
            "start_address": 0x0000,
            "default_size": 0x8000,
            "multiple": True,
            "accepts_binary": True,
            "binary_changeable": True,
            "default_binary": None
        },
        "rom": {
            "options": "any",
            "start_address": 0x8000,
            "default_size": 0x8000,
            "multiple": True,
            "accepts_binary": True,
            "binary_changeable": True,
            "default_binary": None
        },
        "peripherals": [
            {
                "type": "Apple1",
                "start_address": 0xD010,
                "size": 0x0004,
                "address_changeable": True,
                "removable": False
            }
        ]
    }
}

class Configurator:
    def __init__(self, config_name: str, parent_container_tag: str):
        self.config_name = config_name
        if self.config_name not in AVAILABLE_CONFIGS:
            raise ValueError(f"Invalid config name: {self.config_name}")

        self.parent_container_tag = parent_container_tag

    def __del__(self):
        pass

    def validate_page(self):
        pass

    # def 