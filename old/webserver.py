import socket
import palette

DEBUG = False

def debug(*msg):
    if DEBUG:
        print("[SERVER]", *msg)

WIDTH = 32
HEIGHT = 24

class WebServer:

    def __init__(self, camera, wifi):

        self.camera = camera
        self.wifi = wifi

    def start(self):

        addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]

        s = socket.socket()
        s.bind(addr)
        s.listen(5)

        debug("Server listening")

        while True:

            cl, addr = s.accept()

            debug("Client", addr)

            req = cl.recv(1024)

            req = req.decode()

            if "/stream" in req:

                self.stream(cl)

            elif "/status" in req:

                self.status(cl)

            else:

                self.page(cl)

            cl.close()

    def page(self, cl):

        with open("index.html") as f:
            html = f.read()

        cl.send("HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n")
        cl.send(html)

    def status(self, cl):

        import json

        data = json.dumps(self.wifi.status())

        cl.send("HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n")
        cl.send(data)

    def stream(self, cl):

        debug("Starting stream")

        cl.send("HTTP/1.0 200 OK\r\n")
        cl.send("Content-Type: text/plain\r\n\r\n")

        frame = self.camera.getFrame()

        vmin = min(frame)
        vmax = max(frame)

        for y in range(HEIGHT):

            line = ""

            for x in range(WIDTH):

                val = frame[y*WIDTH+x]

                r,g,b = palette.color_map(val,vmin,vmax)

                line += "%d,%d,%d " % (r,g,b)

            cl.send(line+"\n")