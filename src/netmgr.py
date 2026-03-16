import network
import time
from secrets import WIFI_SSID, WIFI_PASSWORD

def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        retries = 0
        while not wlan.isconnected():
            time.sleep(1)
            retries += 1
            if retries > 10:
                raise Exception("Could not connect to Wi-Fi")
    print("Connected! IP:", wlan.ifconfig()[0])
    return wlan.ifconfig()[0]  # return the assigned IP