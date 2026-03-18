from flask import Flask, render_template, Response, jsonify
import requests

app = Flask(__name__)

# Your Pico IP
PICO_BASE_URL = "http://192.168.0.90"   # <-- change this

# -------------------------
# MAIN PAGE
# -------------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------------
# RAW BYTE ARRAY PROXY
# -------------------------
@app.route("/byte_array")
def byte_array():
    r = requests.get(f"{PICO_BASE_URL}/byte_array")
    return Response(r.content, content_type="application/octet-stream")


# -------------------------
# JSON TEMP ARRAY PROXY
# -------------------------
@app.route("/temp_array")
def temp_array():
    r = requests.get(f"{PICO_BASE_URL}/temp_array")
    return jsonify(r.json())


# -------------------------
# RESET PROXY
# -------------------------
@app.route("/hw_reset")
def hw_reset():
    requests.get(f"{PICO_BASE_URL}/hw_reset")
    return "Reset triggered"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)