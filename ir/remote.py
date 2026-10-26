"""
Fan remote colors. Wiring: infrared/wiring.svg.

KY-022 S to GP11. Point the fan remote at the dome.
WS2812B DIN to GP6, 5V to VBUS, GND to GND.
No KY-005.

Run: ../pico.sh run infrared/remote.py
Each address 0x80 command lights the strip a different color.
The color stays until the next known button.
"""
import array
import time
from machine import Pin, time_pulse_us
import rp2

PIN_RX = 11
PIN_STRIP = 6
LED_COUNT = 1

# Address 0x80. The command is what changes from button to button.
COLORS = {
    0x01: ("red", (255, 0, 0)),
    0x05: ("green", (0, 255, 0)),
    0x1B: ("blue", (0, 0, 255)),
    0x0A: ("yellow", (255, 180, 0)),
    0x03: ("purple", (160, 0, 255)),
    0x1F: ("cyan", (0, 255, 255)),
    0x07: ("orange", (255, 80, 0)),
    0x09: ("white", (255, 255, 255)),
}


def read_frame(pin):
    """Mark and space widths in microseconds. The KY-022 pin is low during a mark."""
    while True:
        mark = time_pulse_us(pin, 0, 1_000_000)
        if mark < 400:
            continue
        pulses = [mark]
        while len(pulses) < 100:
            space = time_pulse_us(pin, 1, 20_000)
            if space < 0:
                break
            pulses.append(space)
            mark = time_pulse_us(pin, 0, 20_000)
            if mark < 0:
                break
            pulses.append(mark)
        if len(pulses) >= 3:
            return pulses


def decode_nec(pulses):
    """NEC address and command, a 32-bit raw value, or 'repeat'."""
    if len(pulses) < 3 or not (7000 <= pulses[0] <= 12000):
        return None
    if 1500 <= pulses[1] <= 3000 and len(pulses) <= 4:
        return "repeat"
    if not (3500 <= pulses[1] <= 6000):
        return None
    bits = []
    index = 2
    while index + 1 < len(pulses) and len(bits) < 32:
        mark = pulses[index]
        space = pulses[index + 1]
        if not (250 <= mark <= 1000):
            return None
        if space < 1000:
            bits.append(0)
        elif space < 2500:
            bits.append(1)
        else:
            return None
        index += 2
    if len(bits) != 32:
        return None
    value = 0
    for shift, bit in enumerate(bits):
        value |= bit << shift
    addr = value & 0xFF
    addr_inv = (value >> 8) & 0xFF
    cmd = (value >> 16) & 0xFF
    cmd_inv = (value >> 24) & 0xFF
    if (addr ^ addr_inv) == 0xFF and (cmd ^ cmd_inv) == 0xFF:
        return ("nec", addr, cmd)
    if (cmd ^ cmd_inv) == 0xFF:
        return ("nec16", value & 0xFFFF, cmd)
    return ("raw", value, None)


def data_bits(pulses):
    """Bit string for a frame that is not NEC. 1 is the longer pulse."""
    marks = pulses[0::2]
    spaces = pulses[1::2]
    if marks and marks[0] > 2000 and spaces:
        marks = marks[1:]
        spaces = spaces[1:]

    def spread(values):
        if len(values) < 2:
            return 0
        return max(values) - min(values)

    if spread(spaces) >= spread(marks) and len(spaces) >= 4:
        data = spaces
    elif len(marks) >= 4:
        data = marks
    else:
        return None
    low = min(data)
    high = max(data)
    if high < low * 3 // 2:
        return None
    mid = (low + high) // 2
    return "".join("1" if width > mid else "0" for width in data)


def format_frame(pulses):
    nec = decode_nec(pulses)
    if nec == "repeat":
        return "repeat"
    if nec is not None:
        kind, addr, cmd = nec
        if kind == "nec":
            return "addr 0x{:02X} cmd 0x{:02X}".format(addr, cmd)
        if kind == "nec16":
            return "addr 0x{:04X} cmd 0x{:02X}".format(addr, cmd)
        return "code 0x{:08X}".format(addr)
    bits = data_bits(pulses)
    if bits:
        return "code 0x{:X}".format(int(bits, 2))
    shown = " ".join(str((width + 25) // 50 * 50) for width in pulses[:40])
    return "pulses " + shown


@rp2.asm_pio(
    sideset_init=rp2.PIO.OUT_LOW,
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=24,
)
def ws2812():
    T1 = 2
    T2 = 5
    T3 = 3
    wrap_target()
    label("bitloop")
    out(x, 1).side(0)[T3 - 1]
    jmp(not_x, "do_zero").side(1)[T1 - 1]
    jmp("bitloop").side(1)[T2 - 1]
    label("do_zero")
    nop().side(0)[T2 - 1]
    wrap()


def fill(sm, color):
    level = 0.1
    red, green, blue = color
    packed = (int(green * level) << 16) | (int(red * level) << 8) | int(blue * level)
    frame = array.array("I", [packed] * LED_COUNT)
    sm.put(frame, 8)
    time.sleep_ms(1)


def main():
    print("remote")
    print("press a button")
    sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(PIN_STRIP))
    sm.active(1)
    fill(sm, (0, 0, 0))
    rx = Pin(PIN_RX, Pin.IN)
    last = None
    last_at = time.ticks_ms()
    try:
        while True:
            pulses = read_frame(rx)
            now = time.ticks_ms()
            nec = decode_nec(pulses)
            if nec == "repeat":
                last_at = now
                continue
            text = format_frame(pulses)
            if text == last and time.ticks_diff(now, last_at) < 250:
                last_at = now
                continue
            shown = text
            if nec is not None and nec[0] == "nec" and nec[1] == 0x80 and nec[2] in COLORS:
                name, color = COLORS[nec[2]]
                fill(sm, color)
                shown = text + " " + name
            print(shown)
            last = text
            last_at = now
    finally:
        fill(sm, (0, 0, 0))


main()
