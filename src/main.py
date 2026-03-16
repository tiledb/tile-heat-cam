import machine
from micropyserver import MicroPyServer
from mlx90640 import MLX90640, RefreshRate, init_float_array
import netmgr  # Your Wi-Fi manager

class IrCameraServer:
    def __init__(self):
        # Initialize I2C for MLX90640
        i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=1000000)
        print("I2C Devices Found:", i2c.scan())
        
        self.mlx = MLX90640(i2c)
        self.mlx.refresh_rate = RefreshRate.REFRESH_8_HZ
        self.frame = init_float_array(768)

        # Connect to Wi-Fi
        self.ip = netmgr.connect()  # Should return assigned IP

        # Initialize MicroPyServer with Wi-Fi IP
        self.server = MicroPyServer(host=self.ip)
        self.server.add_route('/', self.show_index)
        self.server.add_route('/result.bytes', self.show_result)

    def show_index(self, request):
        # Serve HTML content
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: text/html; charset=utf-8\r\n\r\n')

        with open('renderer.html', 'r') as file:
            self.server.send(file.read())

    def show_result(self, request):
        # Serve thermal image data
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/octet-stream\r\n\r\n')
        self.mlx.get_frame(self.frame)
        self.server.send_bytes(bytes(self.frame))

    def run(self):
        print(f"Starting server at http://{self.ip}/")
        self.server.start()


# Usage
camera_server = IrCameraServer()
camera_server.run()