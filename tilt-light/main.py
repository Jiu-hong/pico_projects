"""
Shake rainbow. Wiring: wiring-sw18010.svg.

SW-18010P has two pins and no polarity.
One pin to GP15, the other pin to GND.
It closes only while it is shaken.
WS2812B: DIN to GP6, 5V to VBUS, GND to GND.

Shaken: the LEDs step through several colors.
Still: every LED stays green.
"""
import array
import time
from machine import Pin
import rp2

LED_COUNT = 29
BRIGHT = 0.25
HOLD_MS = 600
COLORS = (
    (255, 0, 0),
    (255, 120, 0),
    (255, 220, 0),
    (0, 200, 80),
    (0, 160, 255),
    (140, 0, 255),
)


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


def show(sm, colors):
    packed = array.array("I", [0] * LED_COUNT)
    for index, (red, green, blue) in enumerate(colors):
        red = int(red * BRIGHT)
        green = int(green * BRIGHT)
        blue = int(blue * BRIGHT)
        packed[index] = (green << 16) | (red << 8) | blue
    sm.put(packed, 8)
    time.sleep_ms(1)


def main():
    print("shake light")
    sm = rp2.StateMachine(0, ws2812, freq=8_000_000, sideset_base=Pin(6))
    sm.active(1)
    sensor = Pin(15, Pin.IN, Pin.PULL_UP)
    shaken_until = time.ticks_add(time.ticks_ms(), -HOLD_MS)

    def on_shake(pin):
        nonlocal shaken_until
        shaken_until = time.ticks_add(time.ticks_ms(), HOLD_MS)

    sensor.irq(on_shake, Pin.IRQ_FALLING)
    green = ((0, 180, 0),) * LED_COUNT
    show(sm, green)
    offset = 0
    shown = None

    while True:
        now = time.ticks_ms()
        shaken = sensor.value() == 0 or time.ticks_diff(shaken_until, now) > 0
        if shaken != shown:
            shown = shaken
            print("shake" if shaken else "still")
        if shaken:
            colors = []
            for index in range(LED_COUNT):
                colors.append(COLORS[(index + offset) % len(COLORS)])
            show(sm, colors)
            offset = (offset + 1) % len(COLORS)
        else:
            show(sm, green)
        time.sleep_ms(20)


main()
