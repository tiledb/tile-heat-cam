import network
import time
import rp2 # For Pico W
rp2.country('SE') # Or your 2-letter country code (e.g., 'GB', 'DE')

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Scan for available networks
networks = wlan.scan()
# Entry format: (ssid, bssid, channel, RSSI, security, hidden)
for net in networks:
    ssid_found = net[0]
    # Check if the scanned SSID matches your target string
    if ssid_found.decode('utf-8', 'ignore').strip() == "PiroHome.NET (2.4GHz)":
        print("Found matching network! Attempting connection...")
        # Use the raw binary SSID directly from the scan
        t=0
        while not wlan.isconnected():
            wlan.connect(ssid_found, "the.pirohome.net")
            print("Trying to connect... Attempt", t)
            t+=1
            time.sleep(1)
        
