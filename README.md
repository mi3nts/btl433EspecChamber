<!-- v8 routine update: this file is ORIGINAL (Lakitha) text except the blocks marked ADDED BY CLAUDE. -->
# BTL433 ESPEC Chamber

This repository contains the firmware and operational guidelines for managing the **ESPEC BTL433 environmental chamber**.

---

<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20) -->
## v8 routine

`firmware/xu4Mqtt/runRoutineV8.py` runs the MINTS-AI calibration programme v8 (`firmware/xu4Mqtt/v8/schedule.tsv`,
a verbatim copy from the Calibration repository) point by point in CONSTANT mode, with the dew-point guard against
condensation, and logs through the same `BTL433ESC001*` streams as the other routines. See
[firmware/xu4Mqtt/V8_ROUTINE_UPDATE.md](firmware/xu4Mqtt/V8_ROUTINE_UPDATE.md) for what it does, how to run it and the
weekend operator checklist.

```bash
cd firmware/xu4Mqtt && python3 runRoutineV8.py --plan
```

`runRoutine.py` and `runRoutineCustom.py` are the older temperature × humidity grid routines (`Chamber.Routine`); they
are kept unchanged.

---
<!-- END ADDED BY CLAUDE -->

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

