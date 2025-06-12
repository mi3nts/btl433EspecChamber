# BTL433 ESPEC Chamber

This repository contains the firmware and operational guidelines for managing the **ESPEC BTL433 environmental chamber**.

---

## 🔧 Operation Overview

The BTL433 chamber supports two primary modes:

1. **Static Mode** – Set a fixed temperature and humidity target.
2. **Programmable Mode** – Define a time-based recipe to transition through multiple climate conditions dynamically.

> ⚠️ **Important:** Ensure that *humidity control mode* is enabled if the recipe or static setting involves humidity control.

---

## 💧 Water Supply Setup

To prepare the water system for humidity control:

- Pressurize the water tank to **18 psi** using an air pump.
- Fill the tank with **5% distilled water**.
- Connect the tubing to the chamber's humidifier input.
- Use the **toggle switch** on top of the tank to power on the internal pump.

---

## 🌬️ Dry Air Purge Setup

The dry air purge system ensures stable operation under low humidity or dehumidification conditions:

- Turn on the **air supply** feeding the dry air purge system.
- Plug in the **dry air purge unit** for active operation.

---

## 🔌 Chamber Operation Procedures

### ✅ Startup Procedure

1. **Dry Air Purge**
   - Activate the air supply line.
   - Plug in the purge unit.

2. **Water Tank**
   - Verify the water level.
   - Plug in and power on the pressurized tank.

3. **Chamber Power**
   - Plug in the chamber.
   - Log into the interface via the **Single Board Computer (SBC)**.
   - Upload and execute the desired temperature/humidity **recipe**.

---

### ⛔ Shutdown Procedure

1. **Stop Recipe**
   - Log in via SBC and stop any running recipe.

2. **Power Down**
   - Turn off the pressurized water tank.
   - Unplug the water tank.
   - Unplug the dry air purge unit.
   - Unplug the chamber.

---

## 🖥️ Firmware and Logging

- Firmware logs are essential for tracking chamber behavior and identifying data points for InfluxDB integration.
- Use logs to understand how the chamber transitions between target climate zones.
- Implement controlled recipes to simulate **walk-in temperature-humidity profiles**.

---

Let me know if you'd like a downloadable `.md` version or GitHub-ready `README.md` style layout.
