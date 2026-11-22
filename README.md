# Greenhouse software v2

Server, dashboard and fake device for the smart mini greenhouse (tomatoes + basil).
> 📖 **User Guide:** See [USER_GUIDE.md](USER_GUIDE.md) for instructions on using the mobile/web dashboard, charts, controls, and automation settings.

## First-time setup
1. Install Python (on the first installer screen tick "Add python.exe to PATH"), then open a terminal in this folder.
2. Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. Install the packages: `pip install -r requirements.txt`

The database `greenhouse.db` is created automatically the first time you run `app.py`.

## Run it (two terminals)
Each program keeps running until you stop it, so use one terminal for each, and activate the virtual environment in BOTH.
1. Terminal 1, start this first: `python app.py` (the server). Leave it running.
2. Terminal 2: `python simulator.py` (the fake device, sends data every 5 s). Leave it running.
3. Open http://localhost:5000 in your browser.

Stop either one with `Ctrl+C` in its terminal.

On a phone (same Wi-Fi as the computer): open `http://<computer-ip>:5000`. You can check your computer ip with Windows + R, then cmd, then type `ipconfig`. It changes depending on the Wi-Fi connection, so check it again each session.

## Message format (ESP32 <-> server)

```
FORMAT BETWEEN THE ESP32 AND THE SERVER

Device -> server: every 5 s, HTTP POST to http://<SERVER-IP>:5000/api/readings
Header: Content-Type: application/json
Body:
{"temp": 24.1, "humidity": 55, "soil": 48, "light": 1800, "tank_low": 0}

temp = °C, humidity = %, soil = 0-100 % (calibrated by the device team), light = lux,
tank_low = 0 (water OK) or 1 (water low)

Server -> device (the reply to that POST):
{"pump_seconds": 5, "light": 1, "fan": 0, "heater": 0}

pump_seconds = run the pump for this many seconds, then stop (0 = do nothing)
light, fan, heater = 1 (on) or 0 (off)
If the server answers 400, the reading was rejected: the reply lists the "problems". Do not act on it, keep the last states and send the next reading.
Readings are checked: temp -40..85, humidity 0..100, soil 0..100, light 0..120000, tank_low 0 or 1.

WHAT THE SERVER DECIDES (defaults, can be changed in the dashboard)
The server makes all the decisions. The device only reads the sensors and does what the reply says.
- Plants: tomatoes and basil. Target 25 °C and 60 % humidity.
- Light: a daily schedule, 15 h on and 9 h off. It does NOT depend on the light reading.
- Fan: on when temp > 26 °C or humidity > 65 %; off again when temp < 25 °C and humidity < 60 %.
- Heater: on when temp < 24 °C; off again above 25 °C. The fan and the heater are never on together.
- Pump: runs pump_seconds when soil < 35 % (at most once per minute) and never when tank_low = 1.
Accuracy goal: temperature within ±1 °C and humidity within ±5 %, so please check the sensors against a reference.

SAFETY RULES FOR THE DEVICE
- Everything is OFF when the board starts.
- If the server doesn't answer, the pump stays off and the others keep their last state.
- The pump has its own maximum run time and never runs when tank_low is 1.

NOTES FOR THE DEVICE TEAM
- Please tell us which Wi-Fi the device will use (we recommend one person's phone hotspot) and which of these values you will actually send.
- How each device is switched (relay, pin, HIGH/LOW logic) is up to you; the server only sends on/off commands.
- Light sensor: the light is high intensity, so use a sensor that can read tens of thousands of lux without saturating, and place it where it sees the lamp's light. The server only monitors this value. Recommended BH1750 but decision is yours.
- Soil calibration: 0 means completely dry (sensor in air) and 100 means fully wet (sensor in water). Please measure both ends rather than guess.
- Tank sensor: please test that a really low tank sends 1. Float switches can be wired either way, so it's easy to get it backwards.
- A pump command is one-time: when the reply says pump_seconds: 5, the pump runs once for 5 seconds. It must not restart itself while it's already running.
- If a sensor fails, don't send fake values. Skip that reading. The dashboard shows "Device offline" after about 30 seconds without data, which is the right behavior.
- Don't freeze while waiting: use a short network timeout (about 3 seconds) and a timer for the pump, so a slow server never leaves the pump on.
- Wi-Fi: the device should reconnect by itself if the hotspot drops. It must use 2.4 GHz, since the ESP32 can't join 5 GHz.
- Analog pins: on the ESP32, analog readings from some pins stop working while Wi-Fi is on. Analog sensors should be on ADC1 pins (GPIO 32-39); please verify this for your board.
- Testing without hardware: run our simulator, python simulator.py http://<SERVER-IP>:5000
```


Other endpoints: GET /api/state (latest + settings + alerts), /api/history?n=60 or ?hours=24&max_points=500, /api/stats?hours=24, /api/indicators?hours=24 (temperature and humidity in range, uptime, usage), /api/export.csv?hours=24 (download readings), POST /api/control.

## Rules (add_reading in app.py)
Soil low -> pump (cooldown, never with an empty tank); light follows a daily schedule (15 h on / 9 h off); temperature or humidity high -> fan; temperature low -> heater (never together with the fan). Alerts are computed live in alerts(). Defaults (limits, watts, flow) are in DEFAULTS and must be measured/agreed with the team.

## Plants and targets (tomatoes + basil)
Light: 15 h on, 9 h off every day (default 06:00-21:00, settings `light_start` and `light_hours`). Temperature 24-26 C (target 25). Humidity: fan runs above 65 % until it falls to 60 %; alert below 55 % (there is no humidifier). All of this can be changed in the dashboard. Defaults only apply to a fresh database, so run `python reset_db.py` after changing DEFAULTS.
Demo: set "Time speed-up" to 60 in the dashboard to watch a whole day pass in 24 minutes (set it back to 1 afterwards).

## For the ESP32 / firmware team
- Run the server (steps above); the ESP32 posts to `http://<server-ip>:5000/api/readings` every 5 s.
- Test without hardware: `python simulator.py` (or `python simulator.py http://<server-ip>:5000` if the server runs on another computer).
- Allow Python through the Windows firewall (private networks) when asked.

## Maintenance mode (when someone works inside a hatch)
Button on the dashboard = `POST /api/control` with `{"maintenance": 1}` (on) or `{"maintenance": 0}` (off). While it is on, the server replies `fan: 0, heater: 0, pump_seconds: 0` (the light keeps its normal schedule), "Water now" is ignored, and the alerts show only "Maintenance mode ON" (plus device offline / tank low). The device needs no change: it just applies the 0 values. It ends by itself after `maintenance_minutes` (default 15; 0 = no timeout); sending `{"maintenance": 1}` again restarts the timer. `GET /api/state` returns `maintenance` (true/false) and `maintenance_remaining_s` (seconds left, or null). Readings taken during maintenance are marked (`maintenance` column in history and CSV) and left out of the temperature/humidity statistics in `/api/indicators` (it reports `maintenance_min`).

## Tests
Run `python -m unittest -v` in the project folder (server not needed). They check the control rules and the input checks, using a temporary database. Run them before every commit that touches app.py.

## Reset the database
Stop the server, then run `python reset_db.py` in the project folder. This deletes all readings, pump runs and settings, and recreates the tables with the default settings.

## Troubleshooting
- Simulator prints "no valid reply from server": the server (`python app.py`) is not running, or the address is wrong.
- Phone or ESP32 cannot open the page: they must be on the same network as the computer; allow Python through the Windows firewall (private networks); check the IP again.
- Port 5000 already in use (common on macOS because of AirPlay Receiver): stop the other program or change the port at the bottom of `app.py`.
- Dashboard shows "Device offline": no reading arrived in the last 30 seconds.

## Known limits
There is no login: anyone on the same network can open the dashboard and control the greenhouse. Use a private network (for example a phone hotspot).
