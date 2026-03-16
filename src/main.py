import machine
from micropyserver import MicroPyServer
from mlx90640 import MLX90640, RefreshRate, init_float_array
from netmgr import NetManager  # Your new class
import json
import math

import secrets

# Wi-Fi / MQTT configuration
WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD
MQTT_BROKER = secrets.MQTT_BROKER
BASE_TOPIC = secrets.MQTT_BASE_TOPIC

class IrCameraServer:
    def __init__(self):
        # Initialize I2C for MLX90640
        i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=400000)
        print("I2C Devices Found:", i2c.scan())
        
        self.mlx = MLX90640(i2c)
        self.mlx.refresh_rate = RefreshRate.REFRESH_2_HZ
        self.frame = init_float_array(768)

        # Initialize NetManager
        self.net = NetManager(
            wifi_ssid=WIFI_SSID,
            wifi_pass=WIFI_PASSWORD,
            mqtt_broker=MQTT_BROKER,
            base_topic=BASE_TOPIC
        )

        # Wait for Wi-Fi connection
        print("Connecting to Wi-Fi...")
        while not self.net.connect_wifi():
            print("Retrying Wi-Fi...")
            machine.sleep(500)

        self.ip = self.net.wlan.ifconfig()[0]
        print(f"Connected! IP: {self.ip}")

        # Initialize HTTP server
        self.server = MicroPyServer(host=self.ip)
        self.server.add_route('/', self.show_index)
        self.server.add_route('/get_result_bytes', self.show_result)
        self.server.add_route('/get_temperature_array', self.show_temperature_json)
        self.server.add_route('/stats', self.show_stats)

    def show_temperature_json(self, request):
        # Get the latest frame
        self.mlx.get_frame(self.frame)

        # Convert 1D frame (768 values) to 2D (24 rows x 32 columns)
        temp_2d = [self.frame[i*32:(i+1)*32] for i in range(24)]

        # Send HTTP headers
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/json; charset=utf-8\r\n\r\n')

        # Convert 2D array to JSON and send
        self.server.send(json.dumps(temp_2d))

        # Optional: publish to MQTT
        self.net.publish("last_frame_json", json.dumps(temp_2d))

    def show_index(self, request):
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: text/html; charset=utf-8\r\n\r\n')

        with open('server.html', 'r') as file:
            self.server.send(file.read())

    def show_result(self, request):
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/octet-stream\r\n\r\n')
        self.mlx.get_frame(self.frame)
        self.server.send_bytes(bytes(self.frame))

        # Optional: publish frame over MQTT as raw bytes
        self.net.publish("last_frame", bytes(self.frame))

    def show_stats(self, request):
        # Get latest frame
        self.mlx.get_frame(self.frame)

        n = len(self.frame)
        if n == 0:
            stats = {"avg": 0, "stdev": 0, "min": 0, "max": 0}
        else:
            # Compute sum and min/max
            total = 0
            min_val = self.frame[0]
            max_val = self.frame[0]

            for val in self.frame:
                total += val
                if val < min_val:
                    min_val = val
                if val > max_val:
                    max_val = val

            avg = total / n

            # Compute standard deviation
            variance = 0
            for val in self.frame:
                variance += (val - avg) ** 2
            stdev = math.sqrt(variance / n)

            stats = {
                "avg": avg,
                "stdev": stdev,
                "min": min_val,
                "max": max_val
            }

        # Send HTTP response
        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/json; charset=utf-8\r\n\r\n')
        self.server.send(json.dumps(stats))

        # Optional: publish stats to MQTT
        self.net.publish("last_frame_stats", json.dumps(stats))

    def run(self):
        print(f"Starting server at http://{self.ip}/")
        self.server.start()


# Usage
camera_server = IrCameraServer()
camera_server.run()