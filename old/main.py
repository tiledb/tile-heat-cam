import wifi_manager
import mlx90640
import webserver
from machine import Pin, I2C

# =========================
# DEBUG FLAGS
# =========================

wifi_manager.DEBUG = True
mlx90640.DEBUG = True
webserver.DEBUG = True

# =========================
# WIFI CONFIG
# =========================

# SSID = r"PiroHome.NET"
# PASSWORD = r"the.pirohome.net"

PASSWORD = 'pironetw'  # Update with your actual password
SSID = 'PiroNetW'

print("Initializing Wi-Fi connection...")
print(f"Attempting to connect to SSID: {SSID}")

wifi = wifi_manager.WifiManager(SSID, PASSWORD)

# if not wifi.connect():
#     wifi.start_ap()

print("Device IP:", wifi.ip())

# =========================
# MLX90640 INIT
# =========================

i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=800000)

camera = mlx90640.MLX90640(i2c)

# =========================
# START SERVER
# =========================

server = webserver.WebServer(camera, wifi)

server.start()