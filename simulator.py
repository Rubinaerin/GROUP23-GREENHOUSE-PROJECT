# Pretends to be the device. Fan cools, heater warms, pump drains the tank, tank refills now and then.
import math, random, time, requests
URL = "http://localhost:5000/api/readings"
soil, tank, cmd, t0 = 60.0, 1000, {"light": 0, "fan": 0, "heater": 0}, time.time()
while True:
    t = time.time() - t0
    temp = 23 + 6 * math.sin(t / 150) - 2 * cmd["fan"] + 2 * cmd["heater"] + random.uniform(-.2, .2)
    hum = 55 - (temp - 23) * 2 - 5 * cmd["fan"] + random.uniform(-1, 1)
    lux = max(0, 6000 * math.sin(t / 120)) + (300 if cmd["light"] else 0) + random.uniform(-30, 30)
    data = {"temp": round(temp, 1), "humidity": round(hum, 1), "soil": round(soil, 1),
            "light": round(lux), "tank_low": int(tank < 200)}
    try:
        r = requests.post(URL, json=data, timeout=3).json()
        cmd = {k: r[k] for k in cmd}
        if r["pump_seconds"]:
            soil, tank = min(80, soil + 25), tank - 100; print(f"PUMP ran {r['pump_seconds']}s")
        print(data, cmd)
    except requests.RequestException as e:
        print("server not reachable:", e)
    soil = max(0, soil - random.uniform(.2, .6))
    if tank < 200 and random.random() < .03: tank = 1000; print("tank refilled")
    time.sleep(2)
