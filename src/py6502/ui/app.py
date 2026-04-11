import dearpygui.dearpygui as dpg
from py6502.ui.windows.systemselector import SystemSelector

class Py6502App:
    def __init__(self):
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(title="Py6502", width=1340)
        self.emulator = None
        dpg.setup_dearpygui()
        
        # Configure app settings
        dpg.configure_app(init_file="./py6502ui.ini")
        dpg.set_exit_callback(self.save_init_file)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Set primary window
        dpg.show_viewport()
        
    def create_menu_bar(self):
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File", tag="FileMenu"):
                dpg.add_menu_item(label="New System", tag="NewSystemMenuItem", callback=self.new_system_selector)
                dpg.add_separator(tag="FileMenuSeparator1")
                dpg.add_menu_item(label="Exit", tag="ExitMenuItem", callback=dpg.stop_dearpygui)
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: dpg.show_tool(dpg.mvTool_About))

    def save_init_file(self):
        dpg.save_init_file("./py6502ui.ini")

    def new_system_selector(self):
        SystemSelector().show()

    def run(self):
        while dpg.is_dearpygui_running():
            if self.emulator:
                self.emulator.on_update()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()
