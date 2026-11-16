# pylint: disable=missing-function-docstring,missing-module-docstring,multiple-statements,line-too-long,multiple-imports
import sqlite3, time
from flask import Flask, jsonify, request, g, send_from_directory

app = Flask(__name__)
DB = "greenhouse.db"
DEFAULTS = {"auto": 1, "soil_min": 35, "pump_seconds": 5, "pump_cooldown": 60,
            "light_start": 6, "light_hours": 15, "time_scale": 1,
            "temp_min": 24, "temp_max": 26, "hum_max": 65, "hum_min": 55,
            "light_manual": 0, "fan_manual": 0, "heater_manual": 0, "pump_request": 0,
            "last_pump": 0, "light_on": 0, "fan_on": 0, "heater_on": 0,
            "pump_ml_s": 20, "pump_watts": 6, "light_watts": 12, "fan_watts": 3, "heater_watts": 50}
EDITABLE = set(DEFAULTS) - {"pump_request", "last_pump", "light_on", "fan_on", "heater_on"}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB); g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close(_):
    d = g.pop("db", None)
    if d: d.close()

def init():
    c = sqlite3.connect(DB)
    c.executescript("""
    CREATE TABLE IF NOT EXISTS readings(ts REAL, temp REAL, humidity REAL, soil REAL, light REAL, tank_low INT,
        light_on INT, fan_on INT, heater_on INT);
    CREATE TABLE IF NOT EXISTS pump_runs(ts REAL, seconds REAL, source TEXT);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v REAL);""")
    for k, v in DEFAULTS.items():
        c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    c.commit(); c.close()

def settings():
    return {r["k"]: r["v"] for r in db().execute("SELECT k, v FROM settings")}

def put(k, v):
    db().execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))

@app.get("/")
def index():
    return send_from_directory("static", "index.html")

def light_schedule_on(s):
    # Tomatoes + basil: light on for light_hours from light_start, then off for the rest of the 24 h.
    # time_scale > 1 speeds the clock up for demos (60 = a whole day in 24 minutes).
    lt = time.localtime()
    seconds = lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec
    hour = (seconds * s["time_scale"] / 3600) % 24
    return 1 if (hour - s["light_start"]) % 24 < s["light_hours"] else 0

# The device sends a reading; the reply says what to switch. All automation rules live here.
@app.post("/api/readings")
def add_reading():
    d = request.get_json(force=True)
    if not all(k in d for k in ("temp", "humidity", "soil", "light")):
        return jsonify(error="need temp, humidity, soil, light"), 400
    tank_low = int(d.get("tank_low", 0))
    s, now = settings(), time.time()
    pump, source = 0, "auto"
    light, fan, heater = s["light_on"], s["fan_on"], s["heater_on"]
    if s["auto"]:
        if d["soil"] < s["soil_min"] and now - s["last_pump"] > s["pump_cooldown"]:
            pump = s["pump_seconds"]
        light = light_schedule_on(s)
        if d["temp"] > s["temp_max"] or d["humidity"] > s["hum_max"]: fan = 1
        elif d["temp"] < s["temp_max"] - 1 and d["humidity"] < s["hum_max"] - 5: fan = 0
        if d["temp"] < s["temp_min"]: heater = 1
        elif d["temp"] > s["temp_min"] + 1: heater = 0
        if fan: heater = 0                                             # never heat and ventilate together
    else:
        light, fan, heater = s["light_manual"], s["fan_manual"], s["heater_manual"]
    if s["pump_request"]:
        pump, source = s["pump_seconds"], "manual"; put("pump_request", 0)
    if tank_low: pump = 0                                              # never run the pump on an empty tank
    if pump:
        db().execute("INSERT INTO pump_runs VALUES(?,?,?)", (now, pump, source)); put("last_pump", now)
    put("light_on", light); put("fan_on", fan); put("heater_on", heater)
    db().execute("INSERT INTO readings VALUES(?,?,?,?,?,?,?,?,?)",
                 (now, d["temp"], d["humidity"], d["soil"], d["light"], tank_low, light, fan, heater))
    db().commit()
    return jsonify(pump_seconds=pump, light=int(light), fan=int(fan), heater=int(heater))

def alerts(l, s, now):
    if not l or now - l["ts"] > 30: return ["Device offline"]
    a = []
    if l["temp"] > s["temp_max"]: a.append("Temperature above limit")
    if l["temp"] < s["temp_min"]: a.append("Temperature below limit")
    if l["humidity"] > s["hum_max"]: a.append("Humidity above limit")
    if l["humidity"] < s["hum_min"]: a.append("Humidity below limit")
    if l["soil"] < s["soil_min"] - 10: a.append("Soil is too dry")
    if l["tank_low"]: a.append("Water tank is low")
    return a

@app.get("/api/state")
def state():
    r = db().execute("SELECT * FROM readings ORDER BY ts DESC LIMIT 1").fetchone()
    l, s, now = (dict(r) if r else None), settings(), time.time()
    return jsonify(latest=l, settings=s, now=now, alerts=alerts(l, s, now))

@app.get("/api/history")
def history():
    n = int(request.args.get("n", 60))
    rows = db().execute("SELECT * FROM readings ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    return jsonify([dict(r) for r in reversed(rows)])

@app.post("/api/control")
def control():
    d = request.get_json(force=True)
    for k, v in d.items():
        if k in EDITABLE: put(k, float(v))
    if d.get("pump"): put("pump_request", 1)
    db().commit()
    return jsonify(settings())

def on_hours(col, since):
    rows = db().execute(f"SELECT ts, {col} FROM readings WHERE ts>? ORDER BY ts", (since,)).fetchall()
    return sum(b["ts"] - a["ts"] for a, b in zip(rows, rows[1:]) if a[col] and b["ts"] - a["ts"] < 300) / 3600

@app.get("/api/stats")
def stats():
    hours = float(request.args.get("hours", 24)); since = time.time() - hours * 3600
    s = settings()
    pr = db().execute("SELECT COUNT(*) n, COALESCE(SUM(seconds),0) sec FROM pump_runs WHERE ts>?", (since,)).fetchone()
    h = {n: on_hours(n + "_on", since) for n in ("light", "fan", "heater")}
    wh = pr["sec"] / 3600 * s["pump_watts"] + sum(h[n] * s[n + "_watts"] for n in h)
    return jsonify(hours=hours, pump_runs=pr["n"], water_ml=pr["sec"] * s["pump_ml_s"],
                   light_hours=h["light"], fan_hours=h["fan"], heater_hours=h["heater"], energy_wh=wh)

if __name__ == "__main__":
    init()
    app.run(host="0.0.0.0", port=5000, debug=False)  # debug=True only while developing on your own computer
