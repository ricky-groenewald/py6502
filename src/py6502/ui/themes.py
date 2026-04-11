import dearpygui.dearpygui as dpg
# TODO: Create a theme class so that themes can be reused across the app
def create_card_button_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 255, 255, 20))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 50))
            dpg.add_theme_color(dpg.mvThemeCol_Border, (60, 60, 60, 255))
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1.0)
    return theme

def create_standard_button_disabled_theme():
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvButton, enabled_state=False):
            # Set the default (normal) background color to black with full opacity.
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 255))
            # Override hovered and active colors so they remain black.
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (0, 0, 0, 255))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 255))
            # Set text color to grey
            dpg.add_theme_color(dpg.mvThemeCol_Text, (128, 128, 128, 255))
    return theme
