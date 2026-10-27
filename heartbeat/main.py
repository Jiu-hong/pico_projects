"""
Heartbeat light. Wiring: wiring.svg.

Heartbeat sensor: S to GP26, + to 3V3, - to GND. Cover it with a fingertip.
OLED: VCC to 3V3, GND to GND, SDA to GP4, SCL to GP5.

The OLED draws the signal as a scrolling trace while a finger covers the sensor.
The trace goes flat when the finger leaves.
"""
import framebuf
import time
from machine import ADC, I2C, Pin


class OLED:
    def __init__(self, i2c, addr=0x3C):
        self.i2c = i2c
        self.addr = addr
        self.buffer = bytearray(128 * 64 // 8)
        self.fb = framebuf.FrameBuffer(self.buffer, 128, 64, framebuf.MONO_VLSB)
        self.ys = [32] * 128
        self.head = 0
        for cmd in (
            0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40,
            0x8D, 0x14, 0x20, 0x00, 0xA1, 0xC8, 0xDA, 0x12,
            0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF,
        ):
            i2c.writeto(addr, bytes((0x80, cmd)))

    def plot(self, wave, label):
        y = 32 - int(wave / 18)
        if y < 1:
            y = 1
        elif y > 62:
            y = 62
        self.ys[self.head] = y
        self.head = (self.head + 1) % 128
        self.fb.fill(0)
        for x in range(0, 128, 4):
            self.fb.pixel(x, 32, 1)
        start = (self.head + 2) % 128
        for i in range(125):
            a = (start + i) % 128
            b = (a + 1) % 128
            self.fb.line(i, self.ys[a], i + 1, self.ys[b], 1)
        if label:
            self.fb.text(label, 72, 0, 1)
        for cmd in (0x21, 0, 127, 0x22, 0, 7):
            self.i2c.writeto(self.addr, bytes((0x80, cmd)))
        for page in range(8):
            block = self.buffer[page * 128:(page + 1) * 128]
            self.i2c.writeto(self.addr, b"\x40" + block)


def main():
    print("heartbeat")
    print("leave the sensor uncovered")
    adc = ADC(Pin(26))
    try:
        oled = OLED(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000))
        print("OLED ok")
    except OSError as err:
        oled = None
        print("OLED not found", err)

    baseline = float(adc.read_u16())
    peak = 800.0
    contact = False
    now = time.ticks_ms()
    good_since = now
    armed = True
    pending = False
    pending_at = now
    last_beat = time.ticks_add(now, -1000)
    started = now
    next_print = now
    next_plot = now
    last_raw = int(baseline)
    hist = [int(baseline)] * 80
    intervals = []
    bpm_text = ""

    while True:
        raw = adc.read_u16()
        delta = raw - last_raw
        last_raw = raw
        hist.append(raw)
        hist.pop(0)
        span = max(hist) - min(hist)
        now = time.ticks_ms()
        # A fingertip makes a small repeating rise. A lift makes a huge jump.
        if 150 <= span <= 2200:
            if time.ticks_diff(now, good_since) > 300:
                if not contact:
                    contact = True
                    print("finger")
                    baseline = float(raw)
                    peak = 800.0
                    intervals = []
        else:
            good_since = now
            if contact:
                contact = False
                print("off")
                pending = False
                armed = False
                baseline = float(raw)
                peak = 800.0
                intervals = []
                bpm_text = ""

        baseline += (raw - baseline) * 0.005
        wave = raw - baseline
        if wave > peak:
            peak = wave
        else:
            peak = peak * 0.995
        if peak < 250:
            peak = 250

        ready = contact and time.ticks_diff(now, started) > 1500
        if abs(delta) > 2000:
            pending = False
            armed = False
            baseline = float(raw)
            peak = 800.0
        elif pending and contact:
            age = time.ticks_diff(now, pending_at)
            if wave < peak * 0.35 and age >= 40:
                pending = False
                gap = time.ticks_diff(pending_at, last_beat)
                last_beat = pending_at
                if 320 < gap < 1500:
                    intervals.append(gap)
                    intervals = intervals[-6:]
                    bpm = int(60000 / (sum(intervals) / len(intervals)))
                    bpm_text = str(bpm)
                    print("beat", bpm)
                else:
                    print("beat")
            elif age > 280:
                pending = False
                armed = False
                baseline = float(raw)
                peak = 800.0
        elif (
            ready
            and armed
            and wave > peak * 0.6
            and time.ticks_diff(now, last_beat) > 320
        ):
            pending = True
            pending_at = now
            armed = False
        if wave < peak * 0.35 and not pending:
            armed = True

        if oled and time.ticks_diff(now, next_plot) >= 50:
            if contact:
                oled.plot(wave, bpm_text)
            else:
                oled.ys = [32] * 128
                oled.head = 0
                oled.plot(0, "")
            next_plot = now
        if time.ticks_diff(now, next_print) >= 1000:
            print("span", span)
            next_print = now
        time.sleep_ms(10)


main()
