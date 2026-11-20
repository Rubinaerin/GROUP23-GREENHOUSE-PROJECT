# Mini Greenhouse — User Guide

Welcome to the **Smart Mini Greenhouse** dashboard (designed for growing **tomatoes and basil**). This guide explains how to access the web/mobile app, read sensor charts, control devices, and configure automation settings.

---

## 1. Accessing the Dashboard (Computer & Phone)

### On Your Computer
1. Start the server (`python app.py`) and the device/simulator (`python simulator.py`).
2. Open your web browser and go to: `http://localhost:5000`

### On Your Phone (Mobile App View)
1. Connect your phone and computer to the **same Wi-Fi network** (or use a phone hotspot).
2. Find the local IP address printed in the server terminal (for example: `http://10.10.150.35:5000`).
3. Open **Safari** (iOS) or **Chrome** (Android) on your phone and type that address into the URL bar.
4. *(Optional)* **Add to Home Screen:** In Safari, tap the **Share** button and select **Add to Home Screen** (in Chrome, tap the menu `⋮` and select **Install app / Add to Home Screen**) to launch the dashboard like a standalone mobile app.

---

## 2. Understanding the Dashboard

### Connection Status & Live Alerts
- **Status Indicator (Top Right):**
  - 🟢 **device online:** Live sensor data is arriving normally (updated every 5 seconds).
  - 🔴 **Device offline / last data X s ago:** No sensor reading has been received for more than 15–30 seconds. Check your ESP32 board, Wi-Fi connection, or `simulator.py`.
- **Alert Banners (Top):** Red warning boxes appear automatically when attention is needed:
  - `⚠ Water tank is low` — Refill the water reservoir immediately. Automatic watering is paused until refilled.
  - `⚠ Temperature / Humidity out of range` — Current climate values have crossed your configured safety thresholds.

### Live Sensor Cards & Charts
Each of the four top cards displays the current reading and a live trend chart of the last 60 readings, including **min** and **max** values:
1. **Temperature (`°C`):** Target range for tomatoes & basil is **24–26 °C** (optimal **25 °C**).
2. **Humidity (`%`):** Target is around **60%**. High humidity triggers the fan; low humidity triggers a visual alert.
3. **Soil Moisture (`%`):** Measures substrate wetness (`0%` = completely dry, `100%` = fully wet).
4. **Light (`lux`):** Monitors grow-light intensity.

---

## 3. Controls & Operating Modes

### Automatic vs. Manual Mode
- **Mode: automatic (Default):**
  - The server automatically controls the **Light**, **Fan**, and **Heater** based on your configured limits.
  - Individual device buttons (`Light`, `Fan`, `Heater`) are locked and display `(auto)` alongside their current state.
- **Mode: manual:**
  - Tap the **Mode** button to switch to manual control.
  - You can now tap **Light**, **Fan**, or **Heater** directly to turn them **on** or **off** at any time.
  - Automatic watering is disabled in manual mode; watering only happens when you press **Water now**.

### Manual Watering
- **Water now:** Triggers a single watering cycle for the configured pump duration (`Pump run (s)`). *(Note: For safety, the pump will not run if the water tank is empty).*

---

## 4. Automation Settings

Scroll down to the **Controls** form to customize how the greenhouse behaves in **Automatic Mode**:

| Setting | Default | Description |
| :--- | :---: | :--- |
| **Water below soil (%)** | `35` | Triggers the water pump when soil moisture drops below this percentage (maximum once per minute). |
| **Light on from (hour)** | `6` | The hour of the day (`0–23`) when the grow light turns on (e.g., `6` = 06:00). |
| **Light hours per day** | `15` | Total hours the grow light stays on each day (default: 15h on, 9h off). |
| **Pump run (s)** | `5` | How many seconds the water pump runs per watering cycle. |
| **Min temp (°C)** | `18` | Turns the **Heater** on if temperature falls below this limit. |
| **Max temp (°C)** | `28` | Turns the **Fan** on if temperature rises above this limit. |
| **Max humidity (%)** | `80` | Turns the **Fan** on to ventilate if humidity exceeds this limit. |
| **Min humidity (%)** | `55` | Displays a low-humidity alert if air becomes drier than this threshold. |
| **Time speed-up (1 = real)** | `1` | Simulation multiplier (`1` = real-time; set to `60` during demos to simulate 24 hours in 24 minutes). |

After changing any number, tap **Save settings** to apply your changes immediately.

---

## 5. Last 24 Hours Summary

At the bottom of the dashboard, the **Last 24 hours** panel tracks resource usage over the past day:
- **Water Consumption:** Total milliliters (`ml`) of water used and total number of pump runs.
- **Light / Fan / Heater Active:** Total operating hours (`h`) for each actuator.
- **Est. Energy:** Estimated total electricity consumption in Watt-hours (`Wh`).

---

## 6. Quick Troubleshooting

- **Page won't load on phone:** Make sure your phone is on the exact same Wi-Fi network as the server computer and that you typed `:5000` at the end of the IP address (e.g., `http://10.10.150.35:5000`).
- **Buttons don't respond:** Check if the system is in **Mode: automatic**. Switch to **Mode: manual** to toggle Light, Fan, or Heater manually.
- **Pump won't start when pressing "Water now":** Verify that the `Water tank is low` alert is not active.