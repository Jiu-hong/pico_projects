# IR-Controlled WS2812 Smart Light

[code](ir/remote.py)

[wiring](ir/wiring.svg)

hardware

- Raspberry Pi Pico — runs the program
- WS2812B — color LED, one wire sets red, green, and blue
- KY-022 — infrared receiver, the dark dome reads the remote
- Any infrared remote — buttons choose the light color

# Fingertip Heartbeat Trace

[code](heartbeat/main.py)

[wiring](heartbeat/wiring.svg)

hardware

- Raspberry Pi Pico — runs the program
- Heartbeat sensor — fingertip covers it, the pulse is the signal
- OLED — 0.96 inch screen, draws the scrolling trace
