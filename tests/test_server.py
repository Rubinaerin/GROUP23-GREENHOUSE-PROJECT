"""Tests for the server rules. Run from the project folder with:  python -m unittest -v"""
import os, tempfile, time, unittest
from unittest import mock
import app as server

GOOD = {"temp": 25, "humidity": 60, "soil": 60, "light": 18000, "tank_low": 0}

class ServerTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        server.DB = self.path; server.init()
        self.c = server.app.test_client()
    def tearDown(self):
        os.remove(self.path)
    def send(self, **kw):
        r = self.c.post("/api/readings", json={**GOOD, **kw}); return r.status_code, r.get_json()
    def control(self, **kw):
        return self.c.post("/api/control", json=kw)

class ReadingValidation(ServerTest):
    def test_good_reading_is_accepted(self):
        code, body = self.send()
        self.assertEqual(code, 200); self.assertEqual(set(body), {"pump_seconds", "light", "fan", "heater"})
    def test_bad_readings_are_rejected_and_not_stored(self):
        bad = [{"humidity": 400}, {"temp": "hot"}, {"soil": -5}, {"tank_low": 2}, {"tank_low": "0"}, {"light": None}]
        for kw in bad:
            self.assertEqual(self.send(**kw)[0], 400, kw)
        r = self.c.post("/api/readings", json={"temp": 25}); self.assertEqual(r.status_code, 400)
        self.assertIn("humidity is missing", r.get_json()["problems"])
        self.assertEqual(self.c.post("/api/readings", data="not json").status_code, 400)
        self.assertEqual(self.c.get("/api/history").get_json(), [])
    def test_tank_low_is_optional(self):
        r = self.c.post("/api/readings", json={k: v for k, v in GOOD.items() if k != "tank_low"})
        self.assertEqual(r.status_code, 200)

class Rules(ServerTest):
    def test_fan_on_when_hot_or_humid_and_never_with_heater(self):
        self.assertEqual(self.send(temp=27)[1]["fan"], 1)
        self.assertEqual(self.send(temp=25, humidity=66)[1]["fan"], 1)
        self.assertEqual(self.send(temp=23, humidity=70)[1]["heater"], 0)    # fan is on, so no heater
    def test_fan_hysteresis(self):
        self.send(temp=27)
        self.assertEqual(self.send(temp=25.5, humidity=55)[1]["fan"], 1)     # still on
        self.assertEqual(self.send(temp=24.9, humidity=55)[1]["fan"], 0)     # now off
    def test_heater_on_when_cold(self):
        self.assertEqual(self.send(temp=23)[1]["heater"], 1)
        self.assertEqual(self.send(temp=25.5)[1]["heater"], 0)
    def test_pump_when_dry_with_cooldown(self):
        self.assertEqual(self.send(soil=20)[1]["pump_seconds"], 5)
        self.assertEqual(self.send(soil=20)[1]["pump_seconds"], 0)           # cooldown
    def test_no_pump_when_tank_low(self):
        self.assertEqual(self.send(soil=20, tank_low=1)[1]["pump_seconds"], 0)
    def test_water_now_button_is_one_shot_and_respects_tank(self):
        self.control(pump=1)
        self.assertEqual(self.send(tank_low=1)[1]["pump_seconds"], 0)        # blocked by empty tank
        self.control(pump=1)
        self.assertEqual(self.send()[1]["pump_seconds"], 5)
        self.assertEqual(self.send()[1]["pump_seconds"], 0)                  # not repeated
    def test_water_now_request_expires(self):
        with server.app.app_context():
            server.put("pump_request", time.time() - 120); server.db().commit()
        self.assertEqual(self.send()[1]["pump_seconds"], 0)
    def test_light_schedule(self):
        for hour, expected in ((12, 1), (5, 0), (20, 1), (23, 0)):           # default: on 06:00-21:00
            with mock.patch("app.time.localtime", return_value=time.struct_time((2026, 11, 20, hour, 0, 0, 0, 0, 0))):
                self.assertEqual(self.send()[1]["light"], expected, hour)
    def test_manual_mode(self):
        self.control(auto=0, light_manual=1, fan_manual=1)
        body = self.send(temp=20)[1]
        self.assertEqual((body["light"], body["fan"], body["heater"]), (1, 1, 0))

class Settings(ServerTest):
    def test_bad_settings_are_rejected_and_nothing_is_saved(self):
        before = self.c.get("/api/state").get_json()["settings"]
        for kw in ({"pump_seconds": 999}, {"soil_min": "abc"}, {"temp_min": 25, "temp_max": 26}, {"hum_min": 70}):
            self.assertEqual(self.control(**kw).status_code, 400, kw)
        self.assertEqual(self.control(soil_min=40, pump_seconds="x").status_code, 400)
        self.assertEqual(self.c.get("/api/state").get_json()["settings"], before)
    def test_valid_settings_are_saved(self):
        self.assertEqual(self.control(soil_min="40", temp_max=27).get_json()["soil_min"], 40)

class Data(ServerTest):
    def test_history_window_and_csv(self):
        for _ in range(3): self.send()
        self.assertEqual(len(self.c.get("/api/history?hours=1").get_json()), 3)
        self.assertEqual(len(self.c.get("/api/history?n=2").get_json()), 2)
        lines = self.c.get("/api/export.csv?hours=1").data.decode().strip().splitlines()
        self.assertTrue(lines[0].startswith("time,temp_c")); self.assertEqual(len(lines), 4)
        r = self.c.get("/api/history?hours=abc"); self.assertEqual(r.status_code, 400); self.assertIn("error", r.get_json())
    def test_indicators(self):
        now = time.time()
        with server.app.app_context():
            for i in range(21):       # 5 s apart; the first 10 readings in range, the rest 3 degrees too warm
                server.db().execute("INSERT INTO readings(ts,temp,humidity,soil,light,tank_low,light_on,fan_on,heater_on) VALUES(?,?,?,?,?,?,?,?,?)",
                                    (now - 100 + 5 * i, 25 if i < 10 else 28, 60, 50, 1000, 0, 0, 0, 0))
            server.db().commit()
        r = self.c.get("/api/indicators?hours=1").get_json()
        self.assertEqual(r["readings"], 21); self.assertEqual(r["temp_in_range_pct"], 50.0)
        self.assertEqual(r["hum_in_range_pct"], 100.0); self.assertAlmostEqual(r["uptime_pct"], 100, delta=2)
        self.assertTrue(r["values_are_estimates"])
    def test_indicators_with_no_data(self):
        r = self.c.get("/api/indicators").get_json()
        self.assertEqual(r["readings"], 0); self.assertIsNone(r["uptime_pct"])

class Maintenance(ServerTest):
    def test_pauses_fan_heater_and_pump_but_not_light(self):
        self.control(maintenance=1)
        with mock.patch("app.time.localtime", return_value=time.struct_time((2026, 11, 20, 12, 0, 0, 0, 0, 0))):
            hot = self.send(temp=30, soil=10)[1]
            cold = self.send(temp=15, soil=10)[1]
        self.assertEqual((hot["fan"], hot["pump_seconds"]), (0, 0))
        self.assertEqual((cold["heater"], cold["pump_seconds"]), (0, 0))
        self.assertEqual(hot["light"], 1)                                    # light keeps its schedule
    def test_water_now_is_ignored_and_not_remembered(self):
        self.control(maintenance=1); self.control(pump=1)
        self.assertEqual(self.send()[1]["pump_seconds"], 0)
        self.control(maintenance=0)
        self.assertEqual(self.send()[1]["pump_seconds"], 0)                  # not fired afterwards
    def test_normal_control_returns_when_switched_off(self):
        self.control(maintenance=1); self.assertEqual(self.send(temp=30)[1]["fan"], 0)
        self.control(maintenance=0); self.assertEqual(self.send(temp=30)[1]["fan"], 1)
    def test_timeout_ends_maintenance_by_itself(self):
        self.control(maintenance=1)
        with server.app.app_context():
            server.put("maintenance_start", time.time() - 20 * 60); server.db().commit()    # started 20 min ago, limit 15
        st = self.c.get("/api/state").get_json()
        self.assertFalse(st["maintenance"]); self.assertEqual(st["settings"]["maintenance"], 0)
        self.assertEqual(self.send(temp=30)[1]["fan"], 1)
    def test_zero_minutes_means_no_timeout(self):
        self.control(maintenance=1, maintenance_minutes=0)
        with server.app.app_context():
            server.put("maintenance_start", time.time() - 99999); server.db().commit()
        self.assertTrue(self.c.get("/api/state").get_json()["maintenance"])
    def test_state_shows_remaining_time_and_alert(self):
        self.control(maintenance=1); self.send(temp=40)
        st = self.c.get("/api/state").get_json()
        self.assertTrue(0 < st["maintenance_remaining_s"] <= 900)
        self.assertEqual(st["alerts"], ["Maintenance mode ON: fan, heater and pump are paused"])
    def test_bad_values_are_rejected(self):
        self.assertEqual(self.control(maintenance=2).status_code, 400)
        self.assertEqual(self.control(maintenance_minutes=1000).status_code, 400)
    def test_maintenance_time_is_left_out_of_indicators(self):
        now = time.time()
        with server.app.app_context():
            for i in range(21):       # first 10 readings normal and in range, the rest during maintenance and far off target
                server.db().execute("INSERT INTO readings(ts,temp,humidity,soil,light,tank_low,light_on,fan_on,heater_on,maintenance) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                    (now - 100 + 5 * i, 25 if i < 10 else 35, 60, 50, 1000, 0, 0, 0, 0, 0 if i < 10 else 1))
            server.db().commit()
        r = self.c.get("/api/indicators?hours=1").get_json()
        self.assertEqual(r["temp_in_range_pct"], 100.0); self.assertAlmostEqual(r["maintenance_min"], 50 / 60, delta=0.2)
        self.assertEqual(r["temp_max"], 25)
    def test_old_database_is_upgraded(self):
        import sqlite3
        os.remove(self.path)
        c = sqlite3.connect(self.path)
        c.execute("CREATE TABLE readings(ts REAL, temp REAL, humidity REAL, soil REAL, light REAL, tank_low INT, light_on INT, fan_on INT, heater_on INT)")
        c.commit(); c.close()
        server.init()
        self.assertEqual(self.send()[0], 200)

if __name__ == "__main__":
    unittest.main()
