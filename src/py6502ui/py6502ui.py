import dearpygui.dearpygui as dpg
from time import perf_counter, sleep
from py6502sim.peripheral import Apple1
from py6502sim.cpu import MOS6502
from py6502sim.bus import BusController, Memory

class Py6502UI:
    def __init__(self, rom_data):
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(title="Py6502UI", width=1024, height=768, vsync=True)
        dpg.setup_dearpygui()
        self.texture_data = [0] * 256 * 240 * 4
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(
                256,
                240,
                self.texture_data,
                tag="test_texture"
            )

        self.ram = Memory(0xD000, "RAM", 0)
        self.ram.set_data_from_array(rom_data[:0xD000])
        self.rom = Memory(0x100, "ROM", 1)
        self.rom.set_data_from_array(rom_data[0xFF00:])
        self.processor = MOS6502()
        self.bus_controller = BusController("Bus Controller", self.processor)
        self.bus_controller.add_component(self.ram, 0x0000)
        self.bus_controller.add_component(self.rom, 0xFF00)
        self.apple1 = Apple1(4, "Apple 1")
        self.bus_controller.add_component(self.apple1, 0xD010)
        self.bus_controller.send_reset()
        self.key_buffer = []
        self.shift_down = False
        self.key_down = False

    def key_down_handler(self, sender, app_data, user_data):
        # Handle shift key state
        self.shift_down = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
        
        if app_data == dpg.mvKey_Return:
            self.key_buffer.append(0x0D)
            return
        elif app_data == dpg.mvKey_Back:
            self.key_buffer.append(0x08)
            return
        elif app_data == dpg.mvKey_Escape:
            self.key_buffer.append(0x1B)
            return
        else:
            # Convert key code to character
            try:
                # Handle letters
                if dpg.mvKey_A <= app_data <= dpg.mvKey_Z:
                    char = chr(app_data - dpg.mvKey_A + ord('A'))
                # Handle numbers
                elif dpg.mvKey_0 <= app_data <= dpg.mvKey_9:
                    if self.shift_down:
                        shift_chars = ')!@#$%^&*('
                        char = shift_chars[app_data - dpg.mvKey_0]
                    else:
                        char = chr(app_data - dpg.mvKey_0 + ord('0'))
                # Handle space
                elif app_data == dpg.mvKey_Spacebar:
                    char = ' '
                # Handle special characters
                elif app_data == dpg.mvKey_Comma:
                    char = '<' if self.shift_down else ','
                elif app_data == dpg.mvKey_Period:
                    char = '>' if self.shift_down else '.'
                elif app_data == dpg.mvKey_Slash:
                    char = '?' if self.shift_down else '/'
                elif app_data == 601:
                    char = ':' if self.shift_down else ';'
                elif app_data == 596:
                    char = '"' if self.shift_down else "'"
                elif app_data == dpg.mvKey_Open_Brace:
                    char = '{' if self.shift_down else '['
                elif app_data == dpg.mvKey_Close_Brace:
                    char = '}' if self.shift_down else ']'
                elif app_data == dpg.mvKey_Backslash:
                    char = '|' if self.shift_down else '\\'
                elif app_data == dpg.mvKey_Minus:
                    char = '_' if self.shift_down else '-'
                elif app_data == 602:
                    char = '+' if self.shift_down else '='
                elif app_data == 606:
                    char = '~' if self.shift_down else '`'
                else:
                    # print(f'Key pressed: {app_data}')
                    return  # Ignore other keys
                
                self.key_buffer.append(ord(char))
                
            except (ValueError, IndexError):
                return  # Ignore invalid keys

    def start(self):
        with dpg.window(label="Example Window", width=256 * 3 + 40, height=240 * 3 + 40):
            dpg.draw_image("test_texture", (0, 0), (256 * 3, 240 * 3))

        with dpg.handler_registry():
            dpg.add_key_press_handler(key=dpg.mvKey_None, callback=self.key_down_handler)

        dpg.show_viewport()
        frame_count = 0
        now = perf_counter()
        # frame_time = perf_counter()
        print("Added character to kb buffer")
        while dpg.is_dearpygui_running():
            for key in self.key_buffer:
                self.apple1.add_character_to_kb_buffer(key)
            self.key_buffer = []
            for _ in range(16667):
                self.bus_controller.clock()
            dpg.set_value("test_texture", self.apple1.get_screen_buffer())
            dpg.render_dearpygui_frame()
            frame_count += 1
            if perf_counter() - now > 10:
                print(f"FPS: {frame_count / 10}")
                frame_count = 0
                now = perf_counter()
            # snap_time = perf_counter() - frame_time
            # if snap_time < (1 / 30):
            #     sleep(max(0, (1 / 31) - snap_time))
            # frame_time = perf_counter()
        dpg.destroy_context()
