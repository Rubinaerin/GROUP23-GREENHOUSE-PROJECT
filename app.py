# pylint: disable=missing-function-docstring,missing-module-docstring,multiple-statements,line-too-long,multiple-imports
import csv, io, math, sqlite3, time
from flask import Flask, Response, abort, jsonify, request, g, send_from_directory

app = Flask(__name__)
DB = "greenhouse.db"
DEFAULTS = {"auto": 1, "soil_min": 35, "pump_seconds": 5, "pump_cooldown": 60,
            "light_start": 6, "light_hours": 15, "time_scale": 1,
            "temp_min": 24, "temp_max": 26, "hum_max": 65, "hum_min": 55,
            "temp_target": 25, "temp_tol": 1, "hum_target": 60, "hum_tol": 5,   # used by /api/indicators
            "light_manual": 0, "fan_manual": 0, "heater_manual": 0, "pump_request": 0,
            "last_pump": 0, "light_on": 0, "fan_on": 0, "heater_on": 0,
            "pump_ml_s": 20, "pump_watts": 6, "light_watts": 12, "fan_watts": 3, "heater_watts": 50,
            "maintenance": 0, "maintenance_minutes": 15, "maintenance_start": 0,   # maintenance mode (0 minutes = no timeout)
            "values_measured": 0}   # set to 1 once pump_ml_s and the watts are real, measured values
EDITABLE = set(DEFAULTS) - {"pump_request", "last_pump", "light_on", "fan_on", "heater_on", "maintenance_start"}
OFFLINE_S = 30          # no reading for this long = device offline
PUMP_REQUEST_TTL = 60   # a "Water now" press is forgotten if the device doesn't pick it up in time

# What a reading from the device may contain (min, max).
READING_LIMITS = {"temp": (-40, 85), "humidity": (0, 100), "soil": (0, 100), "light": (0, 120000)}
# Allowed range of each setting; settings not listed here must be between 0 and 100000.
BOUNDS = {"auto": (0, 1), "maintenance": (0, 1), "maintenance_minutes": (0, 480), "light_manual": (0, 1), "fan_manual": (0, 1), "heater_manual": (0, 1), "values_measured": (0, 1),
          "soil_min": (0, 100), "pump_seconds": (0, 60), "pump_cooldown": (0, 3600),
          "light_start": (0, 23.99), "light_hours": (0, 24), "time_scale": (1, 1000),
          "temp_min": (-10, 60), "temp_max": (-10, 60), "temp_target": (-10, 60), "temp_tol": (0, 20),
          "hum_max": (0, 100), "hum_min": (0, 100), "hum_target": (0, 100), "hum_tol": (0, 50)}

@app.errorhandler(400)
def bad_request(e):
    return jsonify(error=getattr(e, "description", "bad request")), 400

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
        light_on INT, fan_on INT, heater_on INT, maintenance INT DEFAULT 0);
    CREATE TABLE IF NOT EXISTS pump_runs(ts REAL, seconds REAL, source TEXT);
    CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v REAL);
    CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);""")
    if "maintenance" not in [r[1] for r in c.execute("PRAGMA table_info(readings)")]:   # old database: add the column
        c.execute("ALTER TABLE readings ADD COLUMN maintenance INT DEFAULT 0")
    for k, v in DEFAULTS.items():                      # new settings are added to old databases too
        c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    c.commit(); c.close()

def settings():
    return {r["k"]: r["v"] for r in db().execute("SELECT k, v FROM settings")}

def put(k, v):
    db().execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (k, v))

def maintenance_status(s, now):
    """Returns (active, seconds_left). Maintenance ends by itself when its timeout has passed."""
    if not s["maintenance"]: return False, None
    if s["maintenance_minutes"] <= 0: return True, None          # 0 = no timeout
    left = s["maintenance_start"] + s["maintenance_minutes"] * 60 - now
    if left <= 0:
        put("maintenance", 0); db().commit(); s["maintenance"] = 0
        return False, None
    return True, left

def num_arg(name, default, lo, hi):
    try: v = float(request.args.get(name, default))
    except ValueError: abort(400, f"{name} must be a number")
    if not lo <= v <= hi: abort(400, f"{name} must be between {lo} and {hi}")
    return v

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def check_reading(d):
    """Returns a list of problems; an empty list means the reading is fine."""
    if not isinstance(d, dict): return ["body must be a JSON object"]
    problems = []
    for k, (lo, hi) in READING_LIMITS.items():
        if k not in d: problems.append(f"{k} is missing")
        elif not is_num(d[k]): problems.append(f"{k} must be a number")
        elif not lo <= d[k] <= hi: problems.append(f"{k} must be between {lo} and {hi} (got {d[k]})")
    if "tank_low" in d and not (is_num(d["tank_low"]) and d["tank_low"] in (0, 1)): problems.append("tank_low must be 0 or 1")
    return problems

def parse_settings(d):
    clean, problems = {}, []
    for k, v in d.items():
        if k not in EDITABLE: continue
        try: x = float(v)
        except (TypeError, ValueError): problems.append(f"{k} must be a number"); continue
        lo, hi = BOUNDS.get(k, (0, 100000))
        if math.isfinite(x) and lo <= x <= hi: clean[k] = x
        else: problems.append(f"{k} must be between {lo} and {hi}")
    return clean, problems

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
    d = request.get_json(silent=True)
    problems = check_reading(d)
    if problems:                                       # a bad reading is never stored or acted on
        return jsonify(error="reading rejected", problems=problems), 400
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
    if now - s["pump_request"] < PUMP_REQUEST_TTL:                     # "Water now" button (one-shot, expires)
        pump, source = s["pump_seconds"], "manual"; put("pump_request", 0)
    active, _ = maintenance_status(s, now)
    if active: fan = heater = pump = 0        # maintenance: fan, heater and pump paused; the light is not touched
    if tank_low: pump = 0                                              # never run the pump on an empty tank
    if pump:
        db().execute("INSERT INTO pump_runs VALUES(?,?,?)", (now, pump, source)); put("last_pump", now)
    put("light_on", light); put("fan_on", fan); put("heater_on", heater)
    db().execute("INSERT INTO readings(ts,temp,humidity,soil,light,tank_low,light_on,fan_on,heater_on,maintenance) "
                 "VALUES(?,?,?,?,?,?,?,?,?,?)",
                 (now, d["temp"], d["humidity"], d["soil"], d["light"], tank_low, light, fan, heater, int(active)))
    db().commit()
    return jsonify(pump_seconds=pump, light=int(light), fan=int(fan), heater=int(heater))

def alerts(l, s, now, maint=False):
    a = ["Maintenance mode ON: fan, heater and pump are paused"] if maint else []
    if not l or now - l["ts"] > OFFLINE_S: return a + ["Device offline"]
    if maint: return a + (["Water tank is low"] if l["tank_low"] else [])   # other alerts are expected while a hatch is open
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
    active, left = maintenance_status(s, now)
    return jsonify(latest=l, settings=s, now=now, alerts=alerts(l, s, now, active), maintenance=active,
                   maintenance_remaining_s=None if left is None else round(left))

# ?n=60 gives the last n readings (as before); ?hours=24 gives a time window, thinned to at most max_points.
@app.get("/api/history")
def history():
    if "hours" in request.args:
        since = time.time() - num_arg("hours", 24, 0.01, 8760) * 3600
        rows = db().execute("SELECT * FROM readings WHERE ts>? ORDER BY ts", (since,)).fetchall()
        step = max(1, math.ceil(len(rows) / int(num_arg("max_points", 500, 10, 5000))))
        return jsonify([dict(r) for r in rows[::step]])
    n = int(num_arg("n", 60, 1, 5000))
    rows = db().execute("SELECT * FROM readings ORDER BY ts DESC LIMIT ?", (n,)).fetchall()
    return jsonify([dict(r) for r in reversed(rows)])

@app.get("/api/export.csv")
def export_csv():
    since = time.time() - num_arg("hours", 24, 0.01, 8760) * 3600
    rows = db().execute("SELECT * FROM readings WHERE ts>? ORDER BY ts", (since,)).fetchall()
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["time", "temp_c", "humidity_pct", "soil_pct", "light_lux", "tank_low", "light_on", "fan_on", "heater_on", "maintenance"])
    for r in rows:
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), r["temp"], r["humidity"], r["soil"],
                    r["light"], r["tank_low"], r["light_on"], r["fan_on"], r["heater_on"], r["maintenance"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=greenhouse-readings.csv"})

@app.post("/api/control")
def control():
    d = request.get_json(silent=True)
    if not isinstance(d, dict): return jsonify(error="body must be a JSON object"), 400
    clean, problems = parse_settings(d)
    if any(k in clean for k in ("temp_min", "temp_max", "hum_min", "hum_max")):
        m = {**settings(), **clean}
        if m["temp_max"] - m["temp_min"] < 2: problems.append("temp_max must be at least 2 above temp_min")
        if m["hum_min"] >= m["hum_max"]: problems.append("hum_min must be below hum_max")
    if problems: return jsonify(error="settings rejected", problems=problems), 400   # nothing is saved
    now = time.time()
    for k, v in clean.items(): put(k, v)
    if clean.get("maintenance") == 1: put("maintenance_start", now); put("pump_request", 0)   # (re)starts the timeout
    db().commit()
    active, _ = maintenance_status(settings(), now)
    if d.get("pump") and not active: put("pump_request", now)           # "Water now" is ignored during maintenance
    db().commit()
    return jsonify(settings())

def on_hours(col, since):
    rows = db().execute(f"SELECT ts, {col} FROM readings WHERE ts>? ORDER BY ts", (since,)).fetchall()
    return sum(b["ts"] - a["ts"] for a, b in zip(rows, rows[1:]) if a[col] and b["ts"] - a["ts"] < 300) / 3600

def usage(since, s):
    pr = db().execute("SELECT COUNT(*) n, COALESCE(SUM(seconds),0) sec FROM pump_runs WHERE ts>?", (since,)).fetchone()
    h = {n: on_hours(n + "_on", since) for n in ("light", "fan", "heater")}
    wh = pr["sec"] / 3600 * s["pump_watts"] + sum(h[n] * s[n + "_watts"] for n in h)
    return dict(pump_runs=pr["n"], water_ml=pr["sec"] * s["pump_ml_s"], light_hours=h["light"], fan_hours=h["fan"],
                heater_hours=h["heater"], energy_wh=wh, values_are_estimates=not s["values_measured"])

@app.get("/api/stats")
def stats():
    hours = num_arg("hours", 24, 0.01, 8760)
    return jsonify(hours=hours, **usage(time.time() - hours * 3600, settings()))

# Numbers for the report: how well the greenhouse held its targets, and how reliably the device reported.
@app.get("/api/indicators")
def indicators():
    hours = num_arg("hours", 24, 0.01, 8760)
    now = time.time(); since = now - hours * 3600
    s = settings()
    rows = db().execute("SELECT * FROM readings WHERE ts>? ORDER BY ts", (since,)).fetchall()
    out = dict(hours=hours, readings=len(rows), temp_target=s["temp_target"], temp_tol=s["temp_tol"],
               hum_target=s["hum_target"], hum_tol=s["hum_tol"], temp_in_range_pct=None, hum_in_range_pct=None,
               uptime_pct=None, maintenance_min=0, **usage(since, s))
    if not rows: return jsonify(out)
    span = online = maint = ok_t = ok_h = 0.0          # time-weighted: each reading counts for the time until the next one
    for a, b in zip(rows, rows[1:]):
        gap = b["ts"] - a["ts"]
        if gap > OFFLINE_S: continue                      # device was offline, so this gap is not counted
        online += gap
        if a["maintenance"]: maint += gap; continue   # hatch open = room air, not counted against the targets
        span += gap
        ok_t += gap * (abs(a["temp"] - s["temp_target"]) <= s["temp_tol"])
        ok_h += gap * (abs(a["humidity"] - s["hum_target"]) <= s["hum_tol"])
    out["maintenance_min"] = round(maint / 60, 1)
    if span: out.update(temp_in_range_pct=round(ok_t / span * 100, 1), hum_in_range_pct=round(ok_h / span * 100, 1))
    online += now - rows[-1]["ts"] if now - rows[-1]["ts"] <= OFFLINE_S else 0
    if now - rows[0]["ts"] > 0: out["uptime_pct"] = round(min(100.0, online / (now - rows[0]["ts"]) * 100), 1)
    normal = [r for r in rows if not r["maintenance"]]
    for name, col, target in (("temp", "temp", "temp_target"), ("hum", "humidity", "hum_target")) if normal else ():
        vals = [r[col] for r in normal]
        out.update({name + "_avg": round(sum(vals) / len(vals), 2), name + "_min": min(vals), name + "_max": max(vals),
                    name + "_avg_error": round(sum(abs(v - s[target]) for v in vals) / len(vals), 2)})
    return jsonify(out)

if __name__ == "__main__":
    init()
    app.run(host="0.0.0.0", port=5000, debug=False)  # debug=True only while developing on your own computer
