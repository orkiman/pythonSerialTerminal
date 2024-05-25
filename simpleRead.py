import serial

def read_serial_port(port, baudrate=115200, timeout=2):
    ser = serial.Serial(port, baudrate, timeout=timeout)
    ser.reset_input_buffer()
    try:
        while True:
            line = ser.readline().decode().strip()
            print(line)
    except KeyboardInterrupt:
        ser.close()

if __name__ == "__main__":
    port = "/dev/ttyUSB0"  # Change this to the correct serial port on your system
    read_serial_port(port)
