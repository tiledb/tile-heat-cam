import network
import time
import rp2

DEBUG = False

def debug(*msg):
    if DEBUG:
        print("[WIFI]", *msg)


class WifiManager:

    def __init__(self, ssid, password, timeout=20):
        self.ssid = ssid.strip()
        self.password = password.strip()
        self.timeout = timeout
        self.wlan = network.WLAN(network.STA_IF)

        # Ensure correct Wi-Fi country
        rp2.country('SE')  # Change as needed

    def connect(self):
        debug("Activating STA")
        self.wlan.active(True)

        if self.wlan.isconnected():
            debug("Already connected:", self.wlan.ifconfig())
            return True

        # Scan for available networks
        debug("Scanning for networks...")
        networks = self.wlan.scan()
        ssid_bytes = None
        for net in networks:
            scanned_ssid = net[0]  # bytes
            ssid_str = scanned_ssid.decode('utf-8', 'ignore').strip()
            if ssid_str == self.ssid:
                ssid_bytes = scanned_ssid
                debug(f"Found target network: '{self.ssid}'")
                break

        if ssid_bytes is None:
            debug(f"Network '{self.ssid}' not found!")
            return False

        debug("Attempting connection using raw SSID bytes...")
        self.wlan.connect(ssid_bytes, self.password)

        start = time.time()
        while not self.wlan.isconnected():
            elapsed = time.time() - start
            status = self.wlan.status()
            debug(f"Waiting... {elapsed:.1f}s -> Status code: {status}")
            if elapsed > self.timeout:
                debug("Connection timeout")
                return False
            time.sleep(1)

        debug("Connected successfully")
        debug("IP config:", self.wlan.ifconfig())
        return True

    def start_ap(self, name="ThermalCam", password="12345678"):
        debug("Starting AP")
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid=name, password=password)
        debug("AP started:", ap.ifconfig())
        return ap

    def ip(self):
        if self.wlan.isconnected():
            return self.wlan.ifconfig()[0]
        return "192.168.0.1"

    def status(self):
        if not self.wlan.isconnected():
            return {"connected": False}
        return {
            "connected": True,
            "ip": self.wlan.ifconfig()[0],
            "rssi": self.wlan.status("rssi")
        }

    def disconnect(self):
        debug("Disconnecting")
        self.wlan.disconnect()

    def reconnect(self):
        debug("Reconnecting")
        self.disconnect()
        time.sleep(1)
        return self.connect()