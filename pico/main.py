import machine
from micropyserver import MicroPyServer
from mlx90640 import MLX90640, RefreshRate, init_float_array
from netmgr import NetManager
import json
import math
import time
import secrets


# Wi-Fi / MQTT configuration
WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD
MQTT_BROKER = secrets.MQTT_BROKER
BASE_TOPIC = secrets.MQTT_BASE_TOPIC


class IrCameraServer:

    def __init__(self):

        # ---- RESET PIN SETUP ----
        # GP22 connected to RUN
        # Keep high impedance normally
        self.reset_pin = machine.Pin(22, machine.Pin.IN)

        # ---- I2C SETUP ----
        i2c = machine.I2C(1, sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)
        print("I2C Devices Found:", [hex(dev) for dev in i2c.scan()])

        self.mlx = MLX90640(i2c)
        self.mlx.refresh_rate = RefreshRate.REFRESH_2_HZ
        self.frame = init_float_array(768)

        # ---- NETWORK ----
        self.net = NetManager(
            wifi_ssid=WIFI_SSID,
            wifi_pass=WIFI_PASSWORD,
            mqtt_broker=MQTT_BROKER,
            base_topic=BASE_TOPIC
        )

        print("Connecting to Wi-Fi...")
        print(f"MAC Address: {self.net.mac_addr}")

        while not self.net.connect_wifi():
            print("Retrying Wi-Fi...")
            time.sleep(5)

        self.ip = self.net.wlan.ifconfig()[0]
        print(f"Connected! IP: {self.ip}")

        # ---- HTTP SERVER ----
        self.server = MicroPyServer(host=self.ip)

        self.server.add_route('/', self.show_index)
        self.server.add_route('/byte_array', self.show_result)
        self.server.add_route('/temp_array', self.show_temperature_json)
        self.server.add_route('/stats', self.compute_std_thermal_stats)
        self.server.add_route('/adv_stats', self.compute_adv_thermal_stats)

        # Hardware reset endpoint
        self.server.add_route('/hw_reset', self.hw_reset)


    # ---------------------------------------------------
    # INDEX PAGE
    # ---------------------------------------------------

    def show_index(self, request):

        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: text/html; charset=utf-8\r\n\r\n')

        try:
            with open('server.html', 'r') as file:
                self.server.send(file.read())
        except:
            self.server.send("<h1>server.html missing</h1>")


    # ---------------------------------------------------
    # RAW FRAME
    # ---------------------------------------------------

    def show_result(self, request):

        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/octet-stream\r\n\r\n')

        self.mlx.get_frame(self.frame)
        self.server.send_bytes(bytes(self.frame))

        self.net.publish("last_frame", bytes(self.frame))


    # ---------------------------------------------------
    # TEMPERATURE JSON
    # ---------------------------------------------------

    def show_temperature_json(self, request):

        self.mlx.get_frame(self.frame)

        temp_2d = [self.frame[i*32:(i+1)*32] for i in range(24)]

        payload = json.dumps(temp_2d)

        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/json; charset=utf-8\r\n\r\n')
        self.server.send(payload)

        self.net.publish("last_frame_json", payload)


    # ---------------------------------------------------
    # STANDARD STATS
    # ---------------------------------------------------

    def compute_std_thermal_stats(self, request):

        self.mlx.get_frame(self.frame)

        n = len(self.frame)

        if n == 0:
            stats = {"avg": 0, "stdev": 0, "min": 0, "max": 0}
        else:

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

        payload = json.dumps(stats)

        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/json; charset=utf-8\r\n\r\n')
        self.server.send(payload)

        self.net.publish("last_frame_stats", payload)


    # ---------------------------------------------------
    # ADVANCED STATS
    # ---------------------------------------------------

    def compute_adv_thermal_stats(self, request):

        hot_threshold = 60.0

        self.mlx.get_frame(self.frame)
        n = len(self.frame)

        total = 0.0
        min_val = self.frame[0]
        max_val = self.frame[0]
        hot_pixels = 0

        center_pixel = self.frame[12 * 32 + 16]

        for v in self.frame:

            total += v

            if v < min_val:
                min_val = v

            if v > max_val:
                max_val = v

            if v > hot_threshold:
                hot_pixels += 1

        avg = total / n

        var = 0.0
        for v in self.frame:
            d = v - avg
            var += d * d

        stdev = math.sqrt(var / n)

        sorted_frame = sorted(self.frame)

        median = sorted_frame[n // 2]
        p10 = sorted_frame[int(n * 0.10)]
        p90 = sorted_frame[int(n * 0.90)]
        p25 = sorted_frame[int(n * 0.25)]
        p75 = sorted_frame[int(n * 0.75)]

        stats = {
            "avg": avg,
            "median": median,
            "stdev": stdev,
            "min": min_val,
            "max": max_val,
            "range": max_val - min_val,
            "p10": p10,
            "p90": p90,
            "iqr": p75 - p25,
            "center": center_pixel,
            "hot_pixels": hot_pixels,
            "hotspot_strength": max_val - median
        }

        self.server.send('HTTP/1.0 200 OK\r\n')
        self.server.send('Content-Type: application/json\r\n\r\n')
        self.server.send(json.dumps(stats))


    # ---------------------------------------------------
    # HARDWARE RESET
    # ---------------------------------------------------

    def hw_reset(self, request):

        self.server.send("HTTP/1.0 200 OK\r\n")
        self.server.send("Content-Type: text/plain\r\n\r\n")
        self.server.send("Hardware reset triggered")

        time.sleep(0.2)

        print("Pulling RUN low...")

        # Switch pin to output low to reset Pico
        self.reset_pin.init(machine.Pin.OUT)
        self.reset_pin.value(0)

        # MCU resets immediately, code never continues


    # ---------------------------------------------------
    # RUN SERVER
    # ---------------------------------------------------

    def run(self):

        print(f"Starting server at http://{self.ip}/")
        self.server.start()


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

if __name__ == "__main__":

    camera_server = IrCameraServer()
    camera_server.run()