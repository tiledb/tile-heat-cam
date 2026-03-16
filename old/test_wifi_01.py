from wifi_manager import WifiManager
import wifi_manager

wifi_manager.DEBUG = True

wifi = WifiManager("dummy","dummy")

wifi.wlan.active(True)

nets = wifi.wlan.scan()

for n in nets:
    print(n[0].decode(), "RSSI:", n[3])
    
wifi_manager.DEBUG = True  # Enable Wi-Fi debug output

SSID = "PiroHome"
PASSWORD = "the.pirohome.net"  # your network password

wifi = WifiManager(SSID, PASSWORD)

if not wifi.connect():
    print("Failed to connect, starting AP fallback...")
    wifi.start_ap()

print("Device IP:", wifi.ip())