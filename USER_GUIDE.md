# Mini Greenhouse – User Guide

Welcome to the **Mini Greenhouse** web and mobile dashboard. This guide explains how to access the interface, read live sensor data, switch between automatic and manual modes, and configure environmental thresholds for your plants (tomatoes and basil).

---

## 1. Accessing the Dashboard

### On a Computer (Local)
1. Ensure the server (`python app.py`) is running in your terminal.
2. Open any web browser and go to:  
   `http://localhost:5000` (or `http://127.0.0.1:5000`)

### On a Mobile Phone (Same Wi-Fi / Hotspot)
1. Connect your phone and the host computer to the **same Wi-Fi network** (or personal hotspot).
2. Check the local IP address printed in the server terminal (e.g., `http://10.10.150.35:5000` or `http://192.168.1.x:5000`).
3. Open **Safari** (iOS) or **Chrome** (Android) and enter that exact address including `:5000`.
4. *(Optional)* Tap **Share → Add to Home Screen** on iOS (or **Menu → Install app** on Android) to use the dashboard like a standalone mobile app.

---

## 2. Monitoring Sensors & Charts

At the top of the screen, the status indicator shows whether the greenhouse hardware/simulator is actively sending readings (`device online` in green) or disconnected (`device offline` / `last data X s ago`). Use the **5 min / 24 h** toggle in the header to switch the sensor trend charts between the last 5 minutes (60 readings) and the last 24 hours.

Below the status bar, four live sensor cards display current readings alongside trend charts:
* **Temperature (°C):** Air temperature inside the greenhouse with `min` and `max` range markers.
* **Humidity (%):** Relative air humidity inside the enclosure.
* **Soil moisture (%):** Substrate moisture level (`0%` = completely dry, `100%` = fully wet).
* **Light (lux):** Ambient/grow-light intensity measured by the light sensor.

---

## 3. Controls: Automatic vs. Manual Mode

In the **Controls** card, you can choose how actuators (Light, Fan, Heater, Water Pump) are operated:

* **Mode: automatic (Default)**  
  The server automatically turns the light, fan, heater, and water pump on or off based on your configured limits. Manual toggle buttons for Light, Fan, and Heater are locked (`(auto)`).
* **Mode: manual**  
  Tap the mode button to switch to manual control. You can now tap **Light**, **Fan**, or **Heater** directly to toggle them `on` or `off`. Automatic watering is paused in manual mode.
* **Water now**  
  Triggers a single watering cycle for the configured `Pump run (s)` duration, regardless of whether automatic or manual mode is active. *(The button is only disabled during maintenance mode. If the water tank is empty, the button remains clickable, the pump will not run, and the `Water tank is low` alert is shown.)*

### Maintenance mode
When someone opens a hatch to work inside the greenhouse, press **Start maintenance**:
* It pauses the **fan**, **heater**, and **pump** (manual buttons show `paused` and **Water now** is disabled).
* The **light** keeps following its normal schedule.
* Maintenance mode ends automatically after **15 minutes** (configurable via `Maintenance timeout`), or you can press **End maintenance** to resume normal operation right away. Starting maintenance again begins a fresh 15-minute timer.

---

## 4. Adjusting Automation Settings

You can customize the target thresholds in the **Controls** form and tap **Save settings** to apply them immediately:

| Setting | Description | Default |
| :--- | :--- | :---: |
| **Water below soil (%)** | Soil moisture threshold that triggers automatic watering. | `35` |
| **Light on from (hour)** | Hour of the day (0–23) when the grow light turns on. | `6` |
| **Light hours per day** | Total hours the grow light stays on each day. | `15` |
| **Pump run (s)** | Duration (in seconds) the water pump runs per watering cycle. | `5` |
| **Min temp (°C)** | Temperature below which the heater turns on. | `24` |
| **Max temp (°C)** | Temperature above which the cooling/ventilation fan turns on. | `26` |
| **Max humidity (%)** | Humidity level above which the fan turns on to ventilate. | `65` |
| **Min humidity (%)** | Low-humidity alert threshold. | `55` |
| **Maintenance timeout (min)** | Auto-exit timer for maintenance mode (`0` = no timeout). | `15` |
| **Time speed-up (1 = real)** | Simulation speed multiplier (`1` = real-time; `60` = 1 day in 24 min). | `1` |

---

## 5. Alerts, 24-Hour Statistics & Export

* **Active Alerts:** Warning banners appear automatically at the top of the dashboard when attention is needed (such as low water tank, dry soil, low humidity, or extreme temperatures).
* **Last 24 hours:** Summarizes total water consumed (`ml` and number of pump runs), active operating hours for the light, fan, and heater, and estimated energy usage (`Wh`). *(Note: Until actual pump flow rate and device wattage are measured on hardware, these figures are shown as estimates.)* Use **Download CSV (24 h)** to export the last 24 hours of sensor readings.
* **24h Performance:** Shows the percentage of time temperature and humidity stayed within the target range, overall device uptime percentage, 24-hour averages, and total reading count (displays `–` when there are not enough readings yet).

---

## 6. Quick Troubleshooting

* **Page won't load on phone:** Ensure your phone is connected to the exact same Wi-Fi network as the server computer and that `:5000` is included at the end of the IP address (e.g., `http://10.10.150.35:5000`).
* **Dashboard shows "Device offline":** Check that `simulator.py` or the ESP32 hardware is running and sending sensor readings every 5 seconds.
* **Buttons don't respond:** Verify whether the system is in **Mode: automatic** or **Maintenance mode**. Switch to **Mode: manual** (and end maintenance if active) to toggle Light, Fan, or Heater manually.
* **Pump doesn't run when pressing "Water now":** Check if the `Water tank is low` alert is active at the top of the page (the pump will not run when the tank is empty) or if maintenance mode is active.
