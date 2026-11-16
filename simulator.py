"""Fake ESP32 for testing the server. It behaves the way the real device must.

Message format (the contract with the real device):
  Device -> server: POST <server>/api/readings  {"temp","humidity","soil","light","tank_low"}  every 5 s
  Server -> device: {"pump_seconds","light","fan","heater"}

Fake greenhouse (tomatoes + basil): grow light is the only light source (high intensity),
it also warms the air; the fan cools and dries; the heater warms. Target 25 C and 60 % humidity.

Usage:
  python simulator.py                              # server on this computer
  python simulator.py http://192.168.43.20:5000    # server on another computer
"""
import math
import random
import sys
import time

import requests

SERVER = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
URL = SERVER.rstrip("/") + "/api/readings"
INTERVAL = 5            # seconds between readings (the agreed format)
MAX_PUMP_SECONDS = 15   # the real device needs its own safety cap too
PUMP_ML_S = 20          # water used per pump second (same default as the server)
TANK_FULL_ML, TANK_LOW_ML = 1000, 200   # the float switch trips below TANK_LOW_ML
LAMP_LUX, DARK_LUX = 18000, 10          # placeholder values, to be measured on the real lamp

soil, tank, t0 = 60.0, TANK_FULL_ML, time.time()
temp, hum = 25.0, 60.0
cmd = {"light": 0, "fan": 0, "heater": 0}   # everything is OFF at start
pump_until = 0.0

while True:
    now = time.time()
    t = now - t0
    tank_low = int(tank < TANK_LOW_ML)
    # Temperature and humidity move gradually toward what the current outputs would produce.
    room = 22 + 2 * math.sin(t / 600)
    temp += (room + 3 * cmd["light"] + 3 * cmd["heater"] - 3 * cmd["fan"] - temp) * 0.2
    hum += (62 - (temp - 25) * 2 + 4 * math.sin(t / 400) - 10 * cmd["fan"] - hum) * 0.2
    lux = (LAMP_LUX if cmd["light"] else DARK_LUX) + random.uniform(-.02, .02) * LAMP_LUX * cmd["light"]
    data = {"temp": round(temp + random.uniform(-.1, .1), 1), "humidity": round(hum + random.uniform(-.5, .5), 1),
            "soil": round(soil, 1), "light": round(lux), "tank_low": tank_low}
    try:
        r = requests.post(URL, json=data, timeout=3).json()
        cmd = {k: int(r[k]) for k in cmd}
        secs = min(int(r["pump_seconds"]), MAX_PUMP_SECONDS)
        # A pump command runs once, never while already running, never on a low tank.
        if secs > 0 and now >= pump_until and not tank_low:
            pump_until = now + secs
            soil = min(80, soil + 5 * secs)
            tank -= secs * PUMP_ML_S
            print(f"PUMP runs {secs}s")
        print(data, cmd)
    except (requests.RequestException, KeyError, ValueError) as e:
        # Same as the real device: pump stays off, the other outputs keep their last state.
        print("no valid reply from server:", e)
    soil = max(0, soil - random.uniform(.2, .6) * INTERVAL / 2)   # soil slowly dries
    if tank_low and random.random() < .03:
        tank = TANK_FULL_ML
        print("tank refilled")
    time.sleep(INTERVAL)
