import tkinter as tk
from tkinter import messagebox
import serial.tools.list_ports
import asyncio
import serial_asyncio
import configparser

class SerialReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Reader")
        self.serial_loop = asyncio.get_event_loop()
        self.reader = None
        self.protocol = None
        self.running = True

        self.cr_var = tk.IntVar()
        self.lf_var = tk.IntVar()

        self.load_config()

        # Serial port selection
        self.port_var = tk.StringVar()
        self.ports = [port.device for port in serial.tools.list_ports.comports()]
        if self.ports:
            if self.port_name in self.ports:
                self.port_var.set(self.port_name)  # Set default port from config
            else:
                self.port_var.set(self.ports[0])  # Set default port
        self.port_menu = tk.OptionMenu(root, self.port_var, *self.ports, command=self.start_serial)
        self.port_menu.pack()

        # Baud rate selection
        self.baudrate_var = tk.StringVar()
        self.baudrates = [9600, 19200, 38400, 57600, 115200, 230400]
        if self.baudrate:
            self.baudrate_var.set(self.baudrate)  # Set default baud rate from config
        else:
            self.baudrate_var.set(115200)  # Set default baud rate
        self.baudrate_menu = tk.OptionMenu(root, self.baudrate_var, *self.baudrates, command=self.start_serial)
        self.baudrate_menu.pack()

        # Start the serial port
        self.start_serial()

        self.frame = tk.Frame(root)
        self.frame.pack(expand=True, fill='both')

        self.text_pane = tk.PanedWindow(self.frame)
        self.text_pane.pack(side='left', expand=True, fill='both')

        self.scrollbar = tk.Scrollbar(self.frame)
        self.scrollbar.pack(side='right', fill='y')

        self.text = tk.Text(self.text_pane, yscrollcommand=self.scrollbar.set)
        self.text_pane.add(self.text)

        self.hex_text = tk.Text(self.text_pane, yscrollcommand=self.scrollbar.set)
        self.text_pane.add(self.hex_text)

        self.scrollbar.config(command=self.yview_sync)

        self.entry_frame = tk.Frame(root)
        self.entry_frame.pack()

        self.input_entry = tk.Entry(self.entry_frame)
        self.input_entry.bind("<Return>", self.send_data)
        self.input_entry.pack(side="left")

        self.send_button = tk.Button(self.entry_frame, text="Send", command=self.send_data)
        self.send_button.pack(side="left")

        self.cr_cb = tk.Checkbutton(root, text="CR", variable=self.cr_var)
        self.cr_cb.pack(side="left")

        self.lf_cb = tk.Checkbutton(root, text="LF", variable=self.lf_var)
        self.lf_cb.pack(side="left")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.root.after(100, self.run_asyncio)

    def yview_sync(self, *args):
        self.text.yview(*args)
        self.hex_text.yview(*args)

    def run_asyncio(self):
        self.serial_loop.call_soon(self.serial_loop.stop)
        self.serial_loop.run_forever()
        self.root.after(100, self.run_asyncio)

    async def read_serial(self):
        try:
            self.reader, self.protocol = await serial_asyncio.open_serial_connection(
                url=self.port_var.get(), baudrate=int(self.baudrate_var.get()))
            while self.running:
                line = await self.reader.readline()
                hex_line = ' '.join(f'{i:02x}' for i in line)
                at_bottom = self.scrollbar.get()[1] == 1.0

                self.hex_text.insert(tk.END, hex_line + "\n")
                if at_bottom:
                    self.hex_text.see(tk.END)
                try:
                    line_decoded = line.decode().strip()
                except UnicodeDecodeError:
                    line_decoded = None
                if line_decoded is not None:
                    if line_decoded.isdigit():
                        value = int(line_decoded)
                        self.text.insert(tk.END, f"{value}\n")
                        if at_bottom:
                            self.text.see(tk.END)
                    else:
                        self.text.insert(tk.END, f"{line_decoded}\n")
                        if at_bottom:
                            self.text.see(tk.END)
                else:
                    decimal_value = int(line, 2)()
                    print(f"The decimal value of {line} is {decimal_value}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error reading serial port: {e}")

    def start_serial(self, *args):
        if hasattr(self, 'serial_task'):
            self.serial_task.cancel()
            if self.protocol:
                self.protocol.transport.close()
        self.running = True
        self.serial_task = self.serial_loop.create_task(self.read_serial())

    def send_data(self, *args):
        data = self.input_entry.get()
        if self.protocol and data:
            if self.cr_var.get() == 1:
                data += '\r'
            if self.lf_var.get() == 1:
                data += '\n'
        if self.protocol and data:
            self.protocol.write(data.encode())
            self.input_entry.delete(0, tk.END)

    async def close_serial(self):
        self.running = False
        if hasattr(self, 'serial_task'):
            self.serial_task.cancel()
            try:
                await self.serial_task
            except asyncio.CancelledError:
                pass
        if self.protocol:
            self.protocol.transport.close()

    def on_closing(self):
        self.save_config()
        self.serial_loop.run_until_complete(self.close_serial())
        self.root.destroy()

    def save_config(self):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {'port': self.port_var.get(),
                             'baudrate': self.baudrate_var.get(),
                             'cr': self.cr_var.get(),
                             'lf': self.lf_var.get()}
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.port_name = config.get('DEFAULT', 'port', fallback=None)
        self.baudrate = config.get('DEFAULT', 'baudrate', fallback=None)
        self.cr_var.set(int(config.get('DEFAULT', 'cr', fallback=0)))
        self.lf_var.set(int(config.get('DEFAULT', 'lf', fallback=0)))


if __name__ == "__main__":
    root = tk.Tk()
    app = SerialReaderApp(root)
    root.mainloop()
