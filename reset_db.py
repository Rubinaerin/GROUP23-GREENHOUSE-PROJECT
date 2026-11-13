import sqlite3
from app import init, DB

# NOTE: if you add a new table in init() (app.py), add its name to the list below,
# otherwise the old table will survive a reset.

# 1. Remove the old tables (and all data in them)
c = sqlite3.connect(DB)
for table in ("readings", "pump_runs", "settings"):
    c.execute(f"DROP TABLE IF EXISTS {table}")
c.commit()
c.execute("VACUUM")
c.close()

# 2. Rebuild everything exactly like the first run
init()

# 3. Show what you ended up with
c = sqlite3.connect(DB)
print("readings:", c.execute("SELECT COUNT(*) FROM readings").fetchone()[0], "rows")
print("pump_runs:", c.execute("SELECT COUNT(*) FROM pump_runs").fetchone()[0], "rows")
print("settings:", c.execute("SELECT COUNT(*) FROM settings").fetchone()[0], "rows")
c.close()