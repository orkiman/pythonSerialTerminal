import tkinter as tk
import serial.tools.list_ports
import asyncio
import serial_asyncio
import configparser

class SerialReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Reader")
        self.root.configure(bg="lightblue")
        self.serial_loop = asyncio.get_event_loop()
        self.reader = None
        self.protocol = None
        self.running = True
        self.serial_task = None  # Initialize serial_task to None

        self.cr_var = tk.IntVar()
        self.lf_var = tk.IntVar()
        self.send_checkbox_var = tk.BooleanVar()

        # Baud rate selection
        self.baudrate_var = tk.StringVar()
        self.baudrate_var.set("9600")
        self.baudrate_label = tk.Label(root, text="Baud Rate:", bg="lightgreen", fg="black")
        self.baudrate_label.pack()
        self.baudrate_entry = tk.Entry(root, textvariable=self.baudrate_var, bg="lightyellow", fg="black")
        self.baudrate_entry.pack()

        self.load_config()

        # Serial port selection
        self.port_var = tk.StringVar()
        self.ports = [port.device for port in serial.tools.list_ports.comports()]
        if self.ports:
            if self.port_name in self.ports:
                self.port_var.set(self.port_name)
            else:
                self.port_var.set(self.ports[0])
        else:
            self.port_var.set("")
        self.port_menu = tk.OptionMenu(root, self.port_var, *self.ports, command=self.start_serial)
        self.port_menu.configure(bg="lightyellow", fg="black")
        self.port_menu.pack()

        # Port status indicator
        self.port_status_label = tk.Label(root, text="Port: Closed", bg="red", fg="white")
        self.port_status_label.pack()

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
        self.input_entry.bind("<Return>", self.send_data_event)
        self.input_entry.bind("<KP_Enter>", self.send_data_event)
        self.input_entry.pack(side="left")

        self.send_checkbox = tk.Checkbutton(root, text="Keep sent data", variable=self.send_checkbox_var)
        self.send_checkbox.pack()

        self.send_button = tk.Button(self.entry_frame, text="Send", command=self.send_data)
        self.send_button.pack(side="left")

        self.cr_cb = tk.Checkbutton(root, text="CR (\\r)", variable=self.cr_var)
        self.cr_cb.pack(side="left")

        self.lf_cb = tk.Checkbutton(root, text="LF (\\n)", variable=self.lf_var)
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
            if not self.port_var.get():
                print("No serial port selected")
                return
            self.reader, self.protocol = await serial_asyncio.open_serial_connection(
                url=self.port_var.get(), baudrate=int(self.baudrate_var.get())
            )
            self.update_port_status("Open", "green")
            while self.running:
                data = await self.reader.read(1024)
                if data:
                    hex_line = ' '.join(f'{i:02x}' for i in data)
                    at_bottom = self.scrollbar.get()[1] == 1.0
                    self.hex_text.insert(tk.END, hex_line + "\n")
                    if at_bottom:
                        self.hex_text.see(tk.END)
                    try:
                        decoded_data = data.decode().strip()
                    except UnicodeDecodeError:
                        decoded_data = None
                    if decoded_data:
                        self.text.insert(tk.END, decoded_data + "\n")
                        if at_bottom:
                            self.text.see(tk.END)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error reading serial port: {e}")
            self.update_port_status("Closed", "red")
            if self.protocol:
                self.protocol.transport.close()
                self.protocol = None
                self.reader = None

    def start_serial(self, *args):
        if not self.port_var.get():
            print("No serial port selected")
            return
        if self.serial_task:
            self.serial_task.cancel()
            if self.protocol:
                self.protocol.transport.close()
                self.protocol = None
                self.reader = None
        self.running = True
        self.serial_task = self.serial_loop.create_task(self.read_serial())

    def send_data_event(self, event):
        self.send_data()

    def send_data(self, *args):
        data = self.input_entry.get()
        if self.protocol and data:
            if self.cr_var.get():
                data += '\r'
            if self.lf_var.get():
                data += '\n'
            self.protocol.write(data.encode())
            if not self.send_checkbox_var.get():
                self.input_entry.delete(0, tk.END)

    async def close_serial(self):
        self.running = False
        if self.serial_task:
            self.serial_task.cancel()
            try:
                await self.serial_task
            except asyncio.CancelledError:
                pass
        if self.protocol:
            self.protocol.transport.close()
            self.protocol = None
            self.reader = None
        self.update_port_status("Closed", "red")

    def on_closing(self):
        self.save_config()
        self.serial_loop.run_until_complete(self.close_serial())
        self.root.destroy()

    def save_config(self):
        config = configparser.ConfigParser()
        config['DEFAULT'] = {
            'port': self.port_var.get(),
            'baudrate': self.baudrate_var.get(),
            'cr': self.cr_var.get(),
            'lf': self.lf_var.get(),
            'keep_sent_data': self.send_checkbox_var.get()
        }
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

    def load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.port_name = config.get('DEFAULT', 'port', fallback=None)
        self.baudrate = config.get('DEFAULT', 'baudrate', fallback="9600")
        self.baudrate_var.set(self.baudrate)
        self.cr_var.set(int(config.get('DEFAULT', 'cr', fallback=0)))
        self.lf_var.set(int(config.get('DEFAULT', 'lf', fallback=0)))
        self.send_checkbox_var.set(config.getboolean('DEFAULT', 'keep_sent_data', fallback=False))

    def update_port_status(self, status, color):
        self.port_status_label.config(text=f"Port: {status}", bg=color)

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialReaderApp(root)
    root.mainloop()
