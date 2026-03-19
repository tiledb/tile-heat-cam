from flask import Flask, render_template, Response, jsonify
import requests
import paho.mqtt.client as mqtt
import json
import time
import the_secrets
import numpy as np
import threading
import struct
from influxdb import InfluxDBClient

# ==========================================================
# GLOBAL SHARED DATA
# ==========================================================
latest_frame = None
frame_lock = threading.Lock()

# ==========================================================
# INFLUXDB SETUP (v1)
# ==========================================================
influxdb = InfluxDBClient(
    host=the_secrets.INFLUXDB_HOST,
    port=the_secrets.INFLUXDB_PORT,
    username=the_secrets.INFLUXDB_USERNAME,
    password=the_secrets.INFLUXDB_PASSWORD,
    database=the_secrets.INFLUXDB_DATABASE
)

# ==========================================================
# MQTT PUBLISHER
# ==========================================================
class MQTTPublisher:
    def __init__(self):
        self.client = mqtt.Client()

        if the_secrets.MQTT_USER:
            self.client.username_pw_set(the_secrets.MQTT_USER, the_secrets.MQTT_PASS)

        self.client.connect(the_secrets.MQTT_BROKER, the_secrets.MQTT_PORT, 60)
        self.client.loop_start()

        self.discovery_sent = False

    def publish_stats(self, data):

        for key, value in data.items():

            state_topic = f"{the_secrets.MQTT_BASE_TOPIC}/thermal/{key}"
            self.client.publish(state_topic, str(value))

            if not self.discovery_sent:
                sensor_id = f"{the_secrets.BOARD_ID}_{key}"
                discovery_topic = f"{the_secrets.DISCOVERY_PREFIX}/sensor/{sensor_id}/config"

                payload = {
                    "name": f"Thermal {key.capitalize()}",
                    "state_topic": state_topic,
                    "unit_of_measurement": "°C" if key not in ["hot_pixels"] else "",
                    "unique_id": sensor_id,
                    "device": {
                        "identifiers": [the_secrets.BOARD_ID],
                        "name": the_secrets.BOARD_NAME,
                        "manufacturer": "ThermalCam",
                        "model": "MLX90640"
                    }
                }

                self.client.publish(discovery_topic, json.dumps(payload), retain=True)

        self.discovery_sent = True

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


# ==========================================================
# FLASK APP
# ==========================================================
app = Flask(__name__)
PICO_DATA_URL = "http://192.168.0.90/byte_array"

# ==========================================================
# FETCH FRAME
# ==========================================================
def fetch_frame():
    r = requests.get(PICO_DATA_URL, timeout=2)
    return struct.unpack('<768f', r.content)


# ==========================================================
# STATS COMPUTATION
# ==========================================================
def compute_stats(frame):
    arr = np.array(frame, dtype=np.float32)

    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    avg = float(np.mean(arr))
    median = float(np.median(arr))
    stdev = float(np.std(arr))

    range_val = max_val - min_val
    hotspot_strength = max_val - median

    burn_in_low = 65.0
    burn_in_high = 70.0
    overtemp_threshold = 70.0

    burn_in_pixels = int(np.sum((arr >= burn_in_low) & (arr <= burn_in_high)))
    overtemp_pixels = int(np.sum(arr > overtemp_threshold))

    max_idx = int(np.argmax(arr))
    min_idx = int(np.argmin(arr))

    h_y, h_x = divmod(max_idx, 32)
    c_y, c_x = divmod(min_idx, 32)

    center = arr[12 * 32 + 16]

    p10 = float(np.percentile(arr, 10))
    p90 = float(np.percentile(arr, 90))

    hot_area = int(np.sum(arr > (max_val - 2.0)))

    return {
        "min": round(min_val, 2),
        "max": round(max_val, 2),
        "avg": round(avg, 2),
        "median": round(median, 2),
        "stdev": round(stdev, 2),
        "range": round(range_val, 2),
        "hotspot_strength": round(hotspot_strength, 2),
        "burn_in_pixels": burn_in_pixels,
        "overtemp_pixels": overtemp_pixels,
        "center": round(float(center), 2),
        "hotspot_x": h_x,
        "hotspot_y": h_y,
        "coldspot_x": c_x,
        "coldspot_y": c_y,
        "p10": round(p10, 2),
        "p90": round(p90, 2),
        "hot_area": hot_area,
        "overheat": int(overtemp_pixels > 0),
        "burn_in_risk": int(burn_in_pixels > 0),
    }


# ==========================================================
# INFLUXDB STORAGE
# ==========================================================
def store_stats(stats):
    json_body = [
        {
            "measurement": "Heat-Camera",
            "tags": {
                "type": f"{the_secrets.BOARD_ID}-stats"
            },
            "fields": {k: float(v) for k, v in stats.items()}
        }
    ]

    influxdb.write_points(json_body)


def store_frame(frame, reason="periodic"):
    temp_2d = [list(map(float, frame[i*32:(i+1)*32])) for i in range(24)]

    json_body = [
        {
            "measurement": "Heat-Camera",
            "tags": {
                "type": f"{the_secrets.BOARD_ID}-frame",
                "reason": reason
            },
            "fields": {
                "frame": json.dumps(temp_2d)
            }
        }
    ]

    influxdb.write_points(json_body)


@app.route("/history")
def history():
    try:
        frames_query = f"""
        SELECT frame FROM "Heat-Camera"
        WHERE "type" = '{the_secrets.BOARD_ID}-frame'
        ORDER BY time DESC
        LIMIT 1000
        """
        stats_query = f"""
        SELECT * FROM "Heat-Camera"
        WHERE "type" = '{the_secrets.BOARD_ID}-stats'
        ORDER BY time DESC
        LIMIT 1000
        """

        frames_res = influxdb.query(frames_query)
        stats_res = influxdb.query(stats_query)

        frames = []
        frame_times = []
        for p in frames_res.get_points():
            frames.append(json.loads(p["frame"]))
            frame_times.append(p["time"])

        stats = [p for p in stats_res.get_points()]

        # reverse to chronological order
        frames.reverse()
        stats.reverse()
        frame_times.reverse()

        return jsonify({
            "frames": frames,
            "stats": stats,
            "times": frame_times  # <--- send timestamps
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ==========================================================
# BACKGROUND WORKER
# ==========================================================
def data_worker():
    global latest_frame

    mqtt_pub = MQTTPublisher()
    last_frame_store = 0

    while True:
        try:
            frame = fetch_frame()

            with frame_lock:
                latest_frame = frame

            stats = compute_stats(frame)

            # Every 2 seconds
            mqtt_pub.publish_stats(stats)
            store_stats(stats)

            now = time.time()

            # Every 60 seconds
            if now - last_frame_store > 60:
                store_frame(frame, reason="periodic")
                last_frame_store = now

            # Event-triggered
            if stats["overheat"] or stats["burn_in_risk"]:
                store_frame(frame, reason="event")

        except Exception as e:
            print("Worker error:", e)

        time.sleep(2)


# ==========================================================
# ROUTES
# ==========================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/byte_array")
def byte_array():
    with frame_lock:
        if latest_frame is None:
            return Response(status=503)

        packed = struct.pack('<768f', *latest_frame)

    return Response(packed, content_type="application/octet-stream")


@app.route("/temp_array")
def temp_array():
    with frame_lock:
        if latest_frame is None:
            return jsonify({"error": "no data"}), 503

        temp_2d = [latest_frame[i*32:(i+1)*32] for i in range(24)]

    return jsonify(temp_2d)


@app.route("/hw_reset")
def hw_reset():
    try:
        requests.get("http://192.168.0.90/hw_reset", timeout=2)
        return "Reset triggered"
    except:
        return "Reset failed", 500


# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    t = threading.Thread(target=data_worker, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=8080, debug=True)