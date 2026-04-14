"""DearPyGui theme factories for py6502."""
import dearpygui.dearpygui as dpg


class ThemeManager:
    """Creates and caches all app themes at init time.

    Call ``build()`` once after ``dpg.create_context()``, then access
    themes by name (e.g. ``themes.disabled_button``).
    """

    def __init__(self) -> None:
        self.disabled_button: int = 0
        self.card_button: int = 0
        self.section_header: int = 0

    def build(self) -> None:
        self.disabled_button = self._create_disabled_button_theme()
        self.card_button = self._create_card_button_theme()
        self.section_header = self._create_section_header_theme()

    # ------------------------------------------------------------------
    # Individual theme builders
    # ------------------------------------------------------------------
    @staticmethod
    def _create_disabled_button_theme() -> int:
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvButton, enabled_state=False):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (40, 40, 40, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (40, 40, 40, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (40, 40, 40, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (100, 100, 100, 255))
        return theme

    @staticmethod
    def _create_card_button_theme() -> int:
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (255, 255, 255, 20))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (0, 0, 0, 50))
                dpg.add_theme_color(dpg.mvThemeCol_Border, (60, 60, 60, 255))
                dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 1.0)
        return theme

    @staticmethod
    def _create_section_header_theme() -> int:
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0, 255))
        return theme
