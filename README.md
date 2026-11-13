# Greenhouse software v2
Run: `pip install -r requirements.txt`, then `python app.py` and `python simulator.py`, open those 2 in different terminals. Open http://localhost:5000 (on a phone: http://<computer-ip>:5000). You can check your computer ip with Windows + R then cmd then type ipconfig, it will show you your computer ip, it changes depending on wi-fi connection
**Delete greenhouse.db if you have an old one** (the tables changed). you can delete the database with command python reset_db.py on TERMINAL

Device -> server: POST /api/readings {"temp","humidity","soil","light","tank_low"(0/1, optional)}
Server -> device: {"pump_seconds":n,"light":0/1,"fan":0/1,"heater":0/1}
Other endpoints: GET /api/state (latest + settings + alerts), /api/history?n=60, /api/stats?hours=24, POST /api/control.
Rules (add_reading in app.py): soil low -> pump (cooldown, never with empty tank); lux low -> light; temp/humidity high -> fan; temp low -> heater (never with fan).
Alerts are computed live in alerts(). Defaults (limits, watts, flow) are in DEFAULTS and must be measured/agreed with the team.

Tell me when you want to edit something, so that we don't edit the same thing at the same time. You can just let me know by sending me a message on WhatsApp I have it open all the time when I'm coding, if I'm not responding it means I'm not editing basically.

## Reset the database
Stop the server, then run `python reset_db.py` in the project folder. This deletes all readings, pump runs and settings, and recreates the tables with the default settings.