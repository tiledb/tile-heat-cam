import machine
from micropyserver import MicroPyServer
from mlx90640 import MLX90640, RefreshRate, init_float_array
from netmgr import NetManager  # Your new class
import json
import math
import time
import os
import usocket as socket
import sys
import _thread


import ubinascii  # MicroPython base64

import secrets

# Wi-Fi / MQTT configuration
WIFI_SSID = secrets.WIFI_SSID
WIFI_PASSWORD = secrets.WIFI_PASSWORD
MQTT_BROKER = secrets.MQTT_BROKER
BASE_TOPIC = secrets.MQTT_BASE_TOPIC


class IrCameraServer:
    def __init__(self):
        # Initialize I2C for MLX90640
        i2c = machine.I2C(1, sda=machine.Pin(2), scl=machine.Pin(3), freq=400000)
        # i2c = machine.I2C(0, sda=machine.Pin(4), scl=machine.Pin(5), freq=100000)
        print("I2C Devices Found:", [hex(dev) for dev in i2c.scan()])

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
        print(f"MAC Address: {self.net.mac_addr}")
        while not self.net.connect_wifi():
            print("Retrying Wi-Fi...")
            time.sleep(5)

        self.ip = self.net.wlan.ifconfig()[0]
        print(f"Connected! IP: {self.ip}")
        

        # --- START WebREPL ---
        # try:
        #     self.start_socket_repl()
        # except Exception as e:
        #     print("WebREPL failed to start:", e)
        # --- END WebREPL ---


        # Initialize HTTP server
        self.server = MicroPyServer(host=self.ip)

        # File manager routes
        self.server.add_route('/fm', self.file_manager_page)
        
        self.server.add_route('/files', self.list_files)
        self.server.add_route('/download', self.download_file)
        self.server.add_route('/upload', self.upload_file)
        self.server.add_route('/delete', self.delete_file)
        self.server.add_route('/save', self.save_file)
        self.server.add_route('/reboot', self.reboot)
        
        

        self.server.add_route('/', self.show_index)
        self.server.add_route('/byte_array', self.show_result)
        self.server.add_route('/temp_array', self.show_temperature_json)
        self.server.add_route('/stats', self.compute_std_thermal_stats)
        self.server.add_route('/adv_stats', self.compute_adv_thermal_stats)



    def start_socket_repl(self, port=23):
        def repl_thread():
            s = socket.socket()
            s.bind(('0.0.0.0', port))
            s.listen(1)
            print(f"Socket REPL listening on port {port}...")
            while True:
                try:
                    conn, addr = s.accept()
                    print("Client connected from", addr)
                    conn_in = conn.makefile('r')
                    conn_out = conn.makefile('w')
                    sys.stdin = conn_in
                    sys.stdout = conn_out
                    sys.stderr = conn_out

                    while True:
                        cmd = sys.stdin.readline()
                        if cmd:
                            exec(cmd)
                except Exception as e:
                    print("REPL thread error:", e)

        _thread.start_new_thread(repl_thread, ())

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

    def compute_std_thermal_stats(self, request):
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

    def compute_adv_thermal_stats(self, request):

        hot_threshold =60.0

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
        
    
    def run(self):
        print(f"Starting server at http://{self.ip}/")
        self.server.start()

    def file_manager_page(self, request):

        try:
            with open("file_manager.html") as f:
                html = f.read()
        except:
            html = "<h1>file_manager.html missing</h1>"

        self.server.send("HTTP/1.0 200 OK\r\n")
        self.server.send("Content-Type: text/html\r\n\r\n")
        self.server.send(html)


    def list_files(self, request):

        try:
            files = os.listdir()
        except:
            files = []

        self.server.send("HTTP/1.0 200 OK\r\n")
        self.server.send("Content-Type: application/json\r\n\r\n")
        self.server.send(json.dumps(files))


    def download_file(self, request):

        filename = self.get_query_param(request, "file")

        if not filename:
            self.server.send("HTTP/1.0 400 Bad Request\r\n\r\n")
            return

        try:
            with open(filename, "rb") as f:

                self.server.send("HTTP/1.0 200 OK\r\n")
                self.server.send("Content-Type: application/octet-stream\r\n")
                self.server.send("Content-Disposition: attachment\r\n\r\n")

                while True:
                    chunk = f.read(512)
                    if not chunk:
                        break
                    self.server.send_bytes(chunk)

        except Exception as e:

            print("Download error:", e)
            self.server.send("HTTP/1.0 404 Not Found\r\n\r\n")




    def upload_file(self, request):
        try:
            header, body = request.split("\r\n\r\n", 1)

            # parse urlencoded body
            params = {}
            for pair in body.split("&"):
                if "=" in pair:
                    k,v = pair.split("=",1)
                    params[k] = v

            filename = params.get("filename")
            content_b64 = params.get("content","")

            if not filename:
                raise Exception("Filename missing")

            # decode Base64
            content_bytes = ubinascii.a2b_base64(content_b64)

            # write file
            with open(filename, "wb") as f:
                f.write(content_bytes)

            print("Uploaded:", filename)

            self.server.send("HTTP/1.0 200 OK\r\n")
            self.server.send("Content-Type: text/plain\r\n\r\n")
            self.server.send("OK")

        except Exception as e:
            print("Upload error:", e)
            try:
                self.server.send("HTTP/1.0 500 Internal Server Error\r\n\r\n")
            except:
                pass

    def delete_file(self, request):

        filename = self.get_query_param(request, "file")

        if not filename:
            self.server.send("HTTP/1.0 400 Bad Request\r\n\r\n")
            return

        try:
            os.remove(filename)
            print("Deleted:", filename)

        except Exception as e:
            print("Delete error:", e)

        self.server.send("HTTP/1.0 200 OK\r\n\r\n")


    def save_file(self, request):
        try:
            header, body = request.split("\r\n\r\n", 1)

            # parse urlencoded body
            params = {}
            for pair in body.split("&"):
                if "=" in pair:
                    k,v = pair.split("=",1)
                    params[k] = v

            filename = params.get("filename")
            content = params.get("content","")

            if not filename:
                raise Exception("Filename missing")

            # write file
            with open(filename, "w") as f:
                f.write(content)

            print("Saved:", filename)

            self.server.send("HTTP/1.0 200 OK\r\n")
            self.server.send("Content-Type: text/plain\r\n\r\n")
            self.server.send("OK")

        except Exception as e:
            print("Save error:", e)
            try:
                self.server.send("HTTP/1.0 500 Internal Server Error\r\n\r\n")
            except:
                pass

    def get_query_param(self, request, name):

        try:

            line = request.split("\r\n")[0]
            path = line.split(" ")[1]

            if "?" not in path:
                return None

            params = path.split("?",1)[1]

            for p in params.split("&"):
                k,v = p.split("=",1)
                if k == name:
                    return v

        except:
            pass

        return None


    def reboot(self, request):

        self.server.send("HTTP/1.0 200 OK\r\n\r\n")

        time.sleep(1)
        machine.reset()
        
# Usage
if __name__ == "__main__":
    camera_server = IrCameraServer()
    camera_server.run()