import dearpygui.dearpygui as dpg
from time import perf_counter, sleep
from py6502.sim.peripherals import Apple1
from py6502.sim.cpu import MOS6502
from py6502.sim.bus import BusController, Memory
from py6502.ui.utils.instructionmaps import INSTRUCTION_MAP_6502

class Py6502UI:
    def __init__(self, rom_data):
        self.context = dpg.create_context()
        self.viewport = dpg.create_viewport(title="Py6502UI", vsync=True, width=1340)
        dpg.setup_dearpygui()
        self.texture_data = [0] * 256 * 240 * 4
        with dpg.texture_registry(show=False):
            dpg.add_dynamic_texture(
                256,
                240,
                self.texture_data,
                tag="output_texture"
            )

        self.ram = Memory(0xD000, "RAM", 0)
        self.ram.set_data(rom_data[:0xD000])
        self.ram2 = Memory(0xFF00 - 0xD100, "RAM2", 0)
        self.ram2.set_data(rom_data[0xD100:0xFF00])
        self.rom = Memory(0x100, "ROM", 1)
        self.rom.set_data(rom_data[0xFF00:])
        self.processor = MOS6502()
        self.bus_controller = BusController("Bus Controller", self.processor)
        self.bus_controller.add_component(self.ram, 0x0000)
        self.bus_controller.add_component(self.ram2, 0xD100)
        self.bus_controller.add_component(self.rom, 0xFF00)
        self.apple1 = Apple1(self.bus_controller)
        self.bus_controller.add_component(self.apple1, 0xD010)
        self.bus_controller.send_reset()
        self.key_buffer = []
        self.sim_running = False
        self.mem_monitor_start_page = 0x00
        self.mem_monitor_end_page = 0x00
        self.opcode_disasm = {}
        self.set_up_opcode_disasm()

    def set_up_opcode_disasm(self):
        mnemonic_list = [
            'imm',
            'abs',
            'zp',
            'acc',
            'imp',
            '(ind,X)',
            '(ind),Y',
            'zp,X',
            'abs,X',
            'abs,Y',
            'rel',
            '(ind)',
            'zp,Y'
        ]
        for opcode_label, opcode_data in INSTRUCTION_MAP_6502.items():
            for i, opcode in enumerate(opcode_data):
                if opcode is not None:
                    self.opcode_disasm[opcode] = f'{opcode_label} {mnemonic_list[i]}'
        

    def key_pressed_handler(self, sender, app_data, user_data):
        if not self.sim_running:
            return
        
        if not dpg.get_item_state("video_output")['focused']:
            return

        # Handle shift key state
        shift_down = dpg.is_key_down(dpg.mvKey_LShift) or dpg.is_key_down(dpg.mvKey_RShift)
        
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
                    if shift_down:
                        shift_chars = ')!@#$%^&*('
                        char = shift_chars[app_data - dpg.mvKey_0]
                    else:
                        char = chr(app_data - dpg.mvKey_0 + ord('0'))
                # Handle space
                elif app_data == dpg.mvKey_Spacebar:
                    char = ' '
                # Handle special characters
                elif app_data == dpg.mvKey_Comma:
                    char = '<' if shift_down else ','
                elif app_data == dpg.mvKey_Period:
                    char = '>' if shift_down else '.'
                elif app_data == dpg.mvKey_Slash:
                    char = '?' if shift_down else '/'
                elif app_data == 601:
                    char = ':' if shift_down else ';'
                elif app_data == 596:
                    char = '"' if shift_down else "'"
                elif app_data == dpg.mvKey_Open_Brace:
                    char = '{' if shift_down else '['
                elif app_data == dpg.mvKey_Close_Brace:
                    char = '}' if shift_down else ']'
                elif app_data == dpg.mvKey_Backslash:
                    char = '|' if shift_down else '\\'
                elif app_data == dpg.mvKey_Minus:
                    char = '_' if shift_down else '-'
                elif app_data == 602:
                    char = '+' if shift_down else '='
                elif app_data == 606:
                    char = '~' if shift_down else '`'
                else:
                    # print(f'Key pressed: {app_data}')
                    return  # Ignore other keys
                
                self.key_buffer.append(ord(char))
                
            except (ValueError, IndexError):
                return  # Ignore invalid keys
            
    def reset_handler(self):
        self.bus_controller.send_reset()
        self.apple1.clear_kbd_buffer()
        self.key_buffer = []
        self.clock_step_handler()
        self.clock_step_handler()
        dpg.focus_item("video_output")

    def clock_step_handler(self):
        self.bus_controller.clock()
        dpg.set_value("output_texture", self.apple1.get_screen_buffer())
        self.update_registers()
        self.update_memory_monitor()

    def inst_step_handler(self):
        registers = self.bus_controller.get_registers()
        opcode_inst, opcode_addr = registers['OPCODE'], registers['OPCODE_ADDR']
        
        while registers['OPCODE'] == opcode_inst and registers['OPCODE_ADDR'] == opcode_addr:
            self.bus_controller.clock()
            registers = self.bus_controller.get_registers()

        dpg.set_value("output_texture", self.apple1.get_screen_buffer())
        self.update_registers()
        self.update_memory_monitor()

    def run_handler(self):
        self.sim_running = True
        dpg.configure_item("stop_button", enabled=True)
        dpg.configure_item("run_button", enabled=False)
        dpg.configure_item("clock_step_button", enabled=False)
        dpg.configure_item("inst_step_button", enabled=False)
        dpg.focus_item("video_output")

    def stop_handler(self):
        self.sim_running = False
        dpg.configure_item("stop_button", enabled=False)
        dpg.configure_item("run_button", enabled=True)
        dpg.configure_item("clock_step_button", enabled=True)
        dpg.configure_item("inst_step_button", enabled=True)

    def save_init_file(self):
        dpg.save_init_file("./py6502ui.ini")

    def update_registers(self):
        registers = self.bus_controller.get_registers()
        dpg.set_value("reg_a", f"{registers['ACC']:02X}")
        dpg.set_value("reg_x", f"{registers['X']:02X}")
        dpg.set_value("reg_y", f"{registers['Y']:02X}")
        dpg.set_value("reg_pc", f"{registers['PC']:04X}")
        dpg.set_value("reg_sp", f"{registers['S']:02X}")
        dpg.set_value("status_n_flag", f"N:{(registers['P'] & 0b10000000) >> 7:01b}")
        dpg.set_value("status_v_flag", f"V:{(registers['P'] & 0b01000000) >> 6:01b}")
        dpg.set_value("status_b_flag", f"B:{(registers['P'] & 0b00010000) >> 4:01b}")
        dpg.set_value("status_d_flag", f"D:{(registers['P'] & 0b00001000) >> 3:01b}")
        dpg.set_value("status_i_flag", f"I:{(registers['P'] & 0b00000100) >> 2:01b}")
        dpg.set_value("status_z_flag", f"Z:{(registers['P'] & 0b00000010) >> 1:01b}")
        dpg.set_value("status_c_flag", f"C:{registers['P'] & 0b00000001:01b}")
        dpg.set_value("reg_opcode", f"{registers['OPCODE']:02X} ({self.opcode_disasm[registers['OPCODE']]})")
        dpg.set_value("reg_opcode_addr", f"{registers['OPCODE_ADDR']:04X}")

    def update_memory_monitor(self):
        mon_text = ''
        for page in range(self.mem_monitor_start_page, self.mem_monitor_end_page + 1):
            if page < 0xD0:
                page_data = self.ram.get_data(page << 8, 0x100)
            elif page >= 0xD1 and page < 0xFF:
                page_data = self.ram2.get_data((page - 0xD1) << 8, 0x100)
            elif page == 0xFF:
                page_data = self.rom.get_data(0x0000, 0x100)
            else:
                mon_text += f'{page << 8:04X}: Unmapped memory range\n'
                dpg.set_value("mem_monitor", mon_text)
                dpg.configure_item("mem_monitor", color=(255, 0, 0))  # Set text color to red
                return

            for i in range(0, 0x100, 16):
                addr = (page << 8) | i
                mon_text += f'{addr:04X}: '
                mon_text += ' '.join([f'{byte:02X}' for byte in page_data[i:i+8]])
                mon_text += '  '
                mon_text += ' '.join([f'{byte:02X}' for byte in page_data[i+8:i+16]])
                mon_text += '  |'
                mon_text += ''.join([f'{chr(byte)}' if 0x20 <= byte <= 0x7F else '.' for byte in page_data[i:i+16]])
                mon_text += '|'
                mon_text += '\n'
        dpg.configure_item("mem_monitor", color=(255, 255, 255))  # Set text color to white
        dpg.set_value("mem_monitor", mon_text)

    def update_page_range(self, sender, app_data, _user_data):
        try:
            value = int(app_data, 16)
            if 0 <= value <= 0xFF:
                self.mem_monitor_start_page = value
                self.mem_monitor_end_page = value  # End page automatically matches start page
                dpg.set_value("end_page", f"{value:02X}")  # Update end page display

            dpg.set_value("start_page", f"{self.mem_monitor_start_page:02X}")
            self.update_memory_monitor()
        except ValueError:
            # Reset to current value if invalid input
            dpg.set_value("start_page", f"{self.mem_monitor_start_page:02X}")

    def load_binary_handler(self, sender, app_data):
        # Clear the selected file path when opening the dialog
        dpg.set_value("selected_file_path", "")
        dpg.show_item("load_binary_window")

    def select_file_handler(self):
        dpg.show_item("file_dialog_select_binary")

    def file_selected_callback(self, sender, app_data):
        file_path = app_data['file_path_name']
        dpg.set_value("selected_file_path", file_path)
        # Only hide the file selection dialog, keeping the load binary window open
        dpg.hide_item("file_dialog_select_binary")
        dpg.show_item("load_binary_window")

    def load_binary_callback(self):
        file_path = dpg.get_value("selected_file_path")
        if not file_path:
            return
            
        try:
            start_address = int(dpg.get_value("binary_load_address"), 16)
            with open(file_path, 'rb') as f:
                data = f.read()
                
                if start_address < 0xD000:
                    self.ram.set_data(list(data), start_address)
                elif start_address >= 0xD100 and start_address < 0xFF00:
                    self.ram2.set_data(list(data), start_address - 0xD100)
                    
                self.update_memory_monitor()
                dpg.hide_item("load_binary_window")
                
                # Show success dialog
                with dpg.window(label="Success", modal=True, pos=(400, 300), width=400, height=100) as success_modal:
                    dpg.add_text(f"Successfully loaded {len(data)} bytes at address ${start_address:04X}")
                    dpg.add_button(label="OK", callback=lambda: dpg.delete_item(success_modal))
                
        except (IOError, ValueError) as e:
            with dpg.window(label="Error", modal=True, pos=(400, 300), width=400, height=100) as error_modal:
                dpg.add_text(str(e))
                dpg.add_button(label="OK", callback=lambda: dpg.delete_item(error_modal))

    def create_file_dialog(self):
        # File selection dialog as a separate window
        with dpg.file_dialog(
            directory_selector=False, 
            show=False,
            callback=self.file_selected_callback,
            tag="file_dialog_select_binary",
            width=700,
            height=400
        ):
            dpg.add_file_extension(".bin", color=(0, 255, 0, 255))
            dpg.add_file_extension(".rom", color=(0, 255, 0, 255))

        # Main load binary window
        with dpg.window(
            label="Load Binary",
            show=False,
            tag="load_binary_window",
            width=500,
            height=150,
            pos=(400, 300)
        ):
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="selected_file_path",
                    readonly=True,
                    width=350
                )
                dpg.add_button(label="Select File", callback=self.select_file_handler)
            
            with dpg.group(horizontal=True):
                dpg.add_text("Load Address (hex):")
                dpg.add_input_text(
                    tag="binary_load_address",
                    default_value="0000",
                    width=60,
                    uppercase=True,
                    hexadecimal=True
                )
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load", callback=self.load_binary_callback)
                dpg.add_button(label="Cancel", callback=lambda: dpg.hide_item("load_binary_window"))

    def start(self):
        dpg.configure_app(init_file="./py6502ui.ini")
        dpg.set_exit_callback(self.save_init_file)
        
        # Add menu bar
        with dpg.viewport_menu_bar():
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="Load Binary...", callback=self.load_binary_handler)
                dpg.add_menu_item(label="Exit", callback=lambda: dpg.stop_dearpygui())
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: dpg.show_tool(dpg.mvTool_About))

        # Add this after the menu bar creation:
        self.create_file_dialog()

        with dpg.window(label="Video Output", width=256 * 3 + 16, height=240 * 3 + 16, no_resize=True, no_close=True, no_title_bar=True, tag="video_output"):
            dpg.draw_image("output_texture", (0, 20), (256 * 3, 240 * 3 + 1))

        with dpg.window(label="Emulator Controls", width=256, height=400, no_close=True):  # Increased height for registers
            with dpg.group(horizontal=True):
                dpg.add_button(label="Reset", callback=self.reset_handler, tag="reset_button")
                dpg.add_button(label="Run", callback=self.run_handler, tag="run_button")
                dpg.add_button(label="Stop", callback=self.stop_handler, enabled=False, tag="stop_button")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Step (Single CPU Clock Cycle)", callback=self.clock_step_handler, tag="clock_step_button")
                dpg.add_button(label="Step (Next CPU Instruction)", callback=self.inst_step_handler, tag="inst_step_button")
            
            dpg.add_separator()
            dpg.add_text("CPU Registers", color=(255, 255, 0))
            with dpg.group(horizontal=True):
                dpg.add_text("A: ", tag="reg_a_label")
                dpg.add_text("00", tag="reg_a")
            with dpg.group(horizontal=True):
                dpg.add_text("X: ", tag="reg_x_label")
                dpg.add_text("00", tag="reg_x")
            with dpg.group(horizontal=True):
                dpg.add_text("Y: ", tag="reg_y_label")
                dpg.add_text("00", tag="reg_y")
            with dpg.group(horizontal=True):
                dpg.add_text("PC: ", tag="reg_pc_label")
                dpg.add_text("0000", tag="reg_pc")
            with dpg.group(horizontal=True):
                dpg.add_text("SP: ", tag="reg_sp_label")
                dpg.add_text("00", tag="reg_sp")
            with dpg.group(horizontal=True):
                dpg.add_text("Status: ", tag="reg_status_label")
                dpg.add_text("N:0", tag="status_n_flag")
                dpg.add_text("V:0", tag="status_v_flag")
                dpg.add_text("B:0", tag="status_b_flag")
                dpg.add_text("D:0", tag="status_d_flag")
                dpg.add_text("I:0", tag="status_i_flag")
                dpg.add_text("Z:0", tag="status_z_flag")
                dpg.add_text("C:0", tag="status_c_flag")
            with dpg.group(horizontal=True):
                dpg.add_text("OPCODE: ", tag="reg_opcode_label")
                dpg.add_text("00", tag="reg_opcode")
            with dpg.group(horizontal=True):
                dpg.add_text("OPCODE Addr: ", tag="reg_opcode_addr_label")
                dpg.add_text("0000", tag="reg_opcode_addr")

            dpg.add_separator()
            dpg.add_text("Memory Monitor", color=(255, 255, 0))
            with dpg.group(horizontal=True, horizontal_spacing=0):
                dpg.add_text("Address: 0x")
                dpg.add_input_text(
                    tag="start_page",
                    default_value="00",
                    width=20,
                    callback=self.update_page_range,
                    uppercase=True,
                    hexadecimal=True,
                    no_spaces=True
                )
                dpg.add_text("00 ~ 0x")
                dpg.add_text("00", tag="end_page")  # Changed to text instead of input
                dpg.add_text("FF")
            dpg.add_text("", tag="mem_monitor")

        dpg.set_primary_window("video_output", True)
        self.update_memory_monitor()

        with dpg.handler_registry():
            dpg.add_key_press_handler(key=dpg.mvKey_None, callback=self.key_pressed_handler)

        dpg.show_viewport()
        frame_count = 0
        now = perf_counter()
        dt = 1/60
        prev_time = 0
        
        while dpg.is_dearpygui_running():
            for key in self.key_buffer:
                self.apple1.add_character_to_kb_buffer(key)
            self.key_buffer = []
            if self.sim_running:
                current_time = perf_counter()
                if current_time - prev_time >= (2 * dt):
                    prev_time = current_time - (2 * dt)

                if current_time - prev_time >= dt:
                    # Clock the apple1 for 16667 clock cycles (1MHz / 60Hz)
                    self.apple1.clock()

                    # Update registers
                    self.update_registers()
                    self.update_memory_monitor()

                    # Update video frame
                    dpg.set_value("output_texture", self.apple1.get_screen_buffer())

                    prev_time += dt
            dpg.render_dearpygui_frame()
            frame_count += 1
            if perf_counter() - now > 2:
                dpg.set_viewport_title(f"Py6502UI - FPS: {frame_count/ 2}")
                frame_count = 0
                now = perf_counter()

        dpg.destroy_context()
