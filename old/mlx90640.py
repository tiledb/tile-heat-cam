import struct

DEBUG = False

def debug(*msg):
    if DEBUG:
        print("[MLX90640]", *msg)

MLX_ADDR = 0x33

class MLX90640:

    def __init__(self, i2c):

        debug("Initializing MLX90640")

        self.i2c = i2c
        self.frame = [0]*768

    def getFrame(self):

        debug("Reading frame")

        data = bytearray(1664)

        self.i2c.readfrom_mem_into(MLX_ADDR, 0x0400, data)

        raw = struct.unpack(">"+"H"*832, data)

        for i in range(768):

            val = raw[i]

            if val > 32767:
                val -= 65536

            self.frame[i] = val * 0.01 + 25

        debug("Frame complete")

        return self.frame