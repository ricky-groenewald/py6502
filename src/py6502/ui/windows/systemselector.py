import dearpygui.dearpygui as dpg
from py6502.ui.systems.config import AVAILABLE_CONFIGS, Configurator
from py6502.ui.themes import *

class SystemSelector:
    def __init__(self):
        self.selected_system = None
        self.configurator = None
        self.card_button_theme = create_card_button_theme()
        self.disabled_button_theme = create_standard_button_disabled_theme()
        
    def show(self):
        # Create the main window
        with dpg.window(
            label="New System",
            modal=True,
            show=True,
            tag="system_selector_window",
            width=800,
            height=470,
            pos=(300, 200),
            no_resize=True
        ):
            # Create horizontal layout for two panes
            with dpg.group(horizontal=True):
                # Left pane - System cards
                with dpg.child_window(width=300, height=400, border=False):
                    # Retrieve the theme for system card buttons
                    for system_id, config in AVAILABLE_CONFIGS.items():
                        with dpg.child_window(height=80, tag=f"card_{system_id}", border=False):
                            # Create a centered group for text with padding
                            with dpg.group(horizontal=False):
                                group_width = 270  # Reduced width to account for padding

                                dpg.add_spacer(height=5)

                                # Simple name text
                                dpg.add_separator(label=config["name"])

                                # Simple description text with wrap
                                dpg.add_text(
                                    config["description"],
                                    color=(180, 180, 180, 255),
                                    wrap=group_width,
                                    indent=10
                                )

                            # Add a button with the imported custom theme
                            button = dpg.add_button(
                                label="##invisible_" + system_id,
                                width=299,
                                height=75,
                                callback=self.select_system,
                                user_data=system_id,
                                pos=dpg.get_item_pos(f"card_{system_id}")
                            )
                            dpg.bind_item_theme(button, self.card_button_theme)

                # Right pane - Configuration
                with dpg.child_window(width=460, height=400, tag="config_pane"):
                    # This will be populated when a system is selected
                    pass

            # Bottom buttons
            with dpg.group(horizontal=True):
                create_btn = dpg.add_button(
                    label="Create",
                    width=120,
                    enabled=False,
                    tag="create_system_button",
                    callback=self.create_system
                )
                dpg.bind_item_theme(create_btn, self.disabled_button_theme)
                dpg.add_button(
                    label="Cancel",
                    width=120,
                    callback=lambda: dpg.delete_item("system_selector_window")
                )

    def select_system(self, sender, app_data, user_data):
        print(f"Sender: {sender}")
        print(f"App data: {app_data}")
        print(f"User data: {user_data}")
        
        create_btn_state = dpg.get_item_configuration("create_system_button")
        dpg.configure_item("create_system_button", enabled=(not create_btn_state["enabled"]))
        # # Update selected system
        # self.selected_system = user_data
        
        # # Enable create button
        # dpg.configure_item("create_system_button", enabled=True)
        
        # # Clear and update right pane
        # dpg.delete_item("config_pane", children_only=True)
        
        # # Create configurator for selected system
        # self.configurator = Configurator(system_id)
        # config = self.configurator.get_config()
        
        # # Add system name and description to right pane
        # with dpg.group(parent="config_pane"):
        #     dpg.add_text(config["name"], size=20)
        #     dpg.add_text(config["description"])
        #     dpg.add_separator()
            
        #     # Here you would add specific configuration options
        #     # based on the selected system type
        #     if system_id == "APPLE_I":
        #         self.create_apple1_config()
        #     elif system_id == "CUSTOM_6502":
        #         self.create_custom_config()

    def create_apple1_config(self):
        # Add Apple I specific configuration options
        pass

    def create_custom_config(self):
        # Add custom system configuration options
        pass

    def create_system(self):
        # Handle system creation based on configuration
        dpg.delete_item("system_selector_window")
