<!-- ADDED BY CLAUDE (v8 guide, 2026-10-23) -->
# v8 Routine Guide

This guide covers what [`runRoutineV8.py`](runRoutineV8.py) does to the chamber, step by step, and how long each step
takes. For why it was built this way and where each piece came from, see
[V8_ROUTINE_UPDATE.md](V8_ROUTINE_UPDATE.md).

- **What it runs:** the MINTS-AI calibration programme v8, [`v8/schedule.tsv`](v8/schedule.tsv). That file is a
  verbatim copy (sha256 `92ee4e08…`, Calibration `3ca7f85`, the Frog-line schedule), and the routine runs its rows in file order. No set point is typed into the Python.
- **How long:** **23 h 45 min (1,425 min)** from the start of pre1 to STOP. Pre-cycle answers and guaranteed soaks
  can make it longer; see [How long it really takes](#how-long-it-really-takes).
- **How many points:** 32, made up of 3 pre-cycle checks, 28 calibration points and the bake, then STOP.
- **Mode:** the chamber stays in CONSTANT mode throughout. The routine sends every set point itself; nothing is
  programmed on the panel.
- **Example:** start at 08:00 Saturday, and the chamber stops at about 07:45 Sunday.

Print the timed plan for the current clock without touching anything:

```bash
python3 runRoutineV8.py --plan
```

---

## The Full Routine

Times are elapsed from the start of pre1. **Trans** is the transition window, when T ramps and RH moves to the new
point. **Hold** is the soak at the set point, which starts at the end of the transition. **Td** is the dew point of
the set point.

**Soak:** *timed* means the hold lasts exactly its minutes. *gs ±x* is a guaranteed soak: only minutes with the
temperature PV within ±x °C of the set point count. The routine gives up 60 min after the hold time if the band never
holds long enough.

**Humidity** shows what happens during the transition. *trajectory* means the RH set point follows the dew point
linearly with the temperature. *linear* means an RH-only change spread evenly over the window. *dry warm-up* means
humidity stays OFF for the ramp and comes ON at the end of the transition, or 10 min after it where noted. *OFF*
means the humidity system is off for the whole point.

| # | Point | Tag | T (°C) | RH (%) | Td (°C) | Ramp rate (°C/min) | Trans (min) | Hold (min) | Soak | Humidity | Purge | Aerosol feed | Start | Hold starts | Ends |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|---:|
| 1 | **pre1** | precycle | 22 | 15 | −5.9 | — | 0 | 30 | timed | ON | ON | HEPA bypass | 0:00 | 0:00 | 0:30 |
| 2 | **pre2** | precycle | 20 | 80 | 16.4 | 0.6 | 11 | 25 | timed | trajectory | OFF | HEPA bypass | 0:30 | 0:41 | 1:06 |
| 3 | **pre3** | precycle | 22 | 15 | −5.9 | 1.0 | 26 | 25 | timed | trajectory | ON | **aerosol** | 1:06 | 1:32 | 1:57 |
| 4 | 1 | anchor | 22 | 15 | −5.9 | 0.6 | 2 | 25 | gs ±1 | linear | ON | aerosol | 1:57 | 1:59 | 2:24 |
| 5 | 2 | cold | −20 | OFF | — | 0.6 | 70 | 30 | gs ±2 | OFF | OFF | aerosol | 2:24 | 3:34 | 4:04 |
| 6 | 3 | cold | 0 | OFF | — | 1.0 | 20 | 30 | gs ±1 | OFF | OFF | aerosol | 4:04 | 4:24 | 4:54 |
| 7 | 4 | coldhumid_steam | −2.5 | 70 | −7.2 | 0.6 | 6 | 30 | timed | trajectory | OFF | aerosol | 4:54 | 5:00 | 5:30 |
| 8 | 5 | coldhumid_steam | −2.5 | 85 | −4.7 | 0.6 | 2 | 35 | timed | linear | OFF | aerosol | 5:30 | 5:32 | 6:07 |
| 9 | 6 | kappa | 5 | 85 | 2.7 | 1.0 | 8 | 48 | timed | dry warm-up, ON +10 min | OFF | aerosol | 6:07 | 6:15 | 7:03 |
| 10 | 7 | dry | 42 | 20 | 14.4 | 1.0 | 37 | 30 | timed | dry warm-up | ON | aerosol | 7:03 | 7:40 | 8:10 |
| 11 | 8 | humid | 30 | 30 | 10.5 | 0.6 | 20 | 30 | gs ±1 | trajectory | ON | aerosol | 8:10 | 8:30 | 9:00 |
| 12 | 9 | humid | 25 | 35 | 8.5 | 0.6 | 8 | 28 | gs ±1 | trajectory | ON | aerosol | 9:00 | 9:08 | 9:36 |
| 13 | 10 | floor | 20 | 35 | 4.1 | 0.6 | 9 | 28 | gs ±1 | trajectory | ON | aerosol | 9:36 | 9:45 | 10:13 |
| 14 | 11 | anchor | 20 | 15 | −7.5 | 0.6 | 13 | 35 | gs ±1 | linear | ON | aerosol | 10:13 | 10:26 | 11:01 |
| 15 | 12 | humid | 35 | 35 | 17.3 | 1.0 | 15 | 30 | gs ±1 | trajectory | OFF | aerosol | 11:01 | 11:16 | 11:46 |
| 16 | 13 | kappa | 30 | 50 | 18.4 | 0.6 | 8 | 28 | gs ±1 | trajectory | OFF | aerosol | 11:46 | 11:54 | 12:22 |
| 17 | 14 | kappa | 25 | 65 | 18.0 | 0.6 | 9 | 28 | gs ±1 | trajectory | OFF | aerosol | 12:22 | 12:31 | 12:59 |
| 18 | 15 | kappa | 20 | 45 | 7.7 | 0.6 | 8 | 28 | gs ±1 | trajectory | OFF | aerosol | 12:59 | 13:07 | 13:35 |
| 19 | 16 | kappa | 20 | 60 | 12.0 | 0.6 | 2 | 35 | gs ±1 | linear | OFF | aerosol | 13:35 | 13:37 | 14:12 |
| 20 | 17 | kappa | 20 | 70 | 14.4 | 0.6 | 2 | 35 | gs ±1 | linear | OFF | aerosol | 14:12 | 14:14 | 14:49 |
| 21 | 18 | kappa | 20 | 80 | 16.4 | 0.6 | 2 | 35 | gs ±1 | linear | OFF | aerosol | 14:49 | 14:51 | 15:26 |
| 22 | 19 | kappa | 20 | 90 | 18.3 | 0.6 | 2 | 35 | gs ±1 | linear | OFF | aerosol | 15:26 | 15:28 | 16:03 |
| 23 | 20 | dry | 15 | 30 | −2.5 | 0.6 | 20 | 30 | gs ±1 | trajectory | ON | aerosol | 16:03 | 16:23 | 16:53 |
| 24 | 21 | kappa | 15 | 65 | 8.5 | 0.6 | 6 | 35 | gs ±1 | linear | OFF | aerosol | 16:53 | 16:59 | 17:34 |
| 25 | 22 | kappa | 15 | 90 | 13.4 | 0.6 | 4 | 35 | gs ±1 | linear | OFF | aerosol | 17:34 | 17:38 | 18:13 |
| 26 | 23 | humid | 10 | 35 | −4.8 | 0.6 | 10 | 30 | timed | trajectory | ON | aerosol | 18:13 | 18:23 | 18:53 |
| 27 | 24 | kappa | 10 | 65 | 3.7 | 0.6 | 4 | 35 | timed | linear | OFF | aerosol | 18:53 | 18:57 | 19:32 |
| 28 | 25 | coldhumid | 5 | OFF | — | 0.6 | 9 | 28 | timed | OFF | OFF | aerosol | 19:32 | 19:41 | 20:09 |
| 29 | 26 | kappa | 10 | 90 | 8.4 | 1.0 | 5 | 46 | timed | dry warm-up, ON +10 min | OFF | aerosol | 20:09 | 20:14 | 21:00 |
| 30 | 27 | fog | 10 | 95 | 9.2 | 0.6 | 2 | 30 | timed | linear | OFF | aerosol | 21:00 | 21:02 | 21:32 |
| 31 | 28 | anchor | 22 | 15 | −5.9 | 1.0 | 28 | 60 | timed | dry warm-up | ON | aerosol | 21:32 | 22:00 | 23:00 |
| 32 | **bake** | bake | 45 | 15 | 12.4 | 1.0 | 23 | 22 | timed | trajectory | ON | aerosol | 23:00 | 23:23 | 23:45 |
| — | **stop** | stop | — | OFF | — | — | — | — | — | OFF | OFF | — | 23:45 | — | — |

Notes on the table:

- **pre1** has no transition: it starts from the chamber's current temperature, assumed here to be the lab's 22 °C.
  If the chamber starts elsewhere, pre1 first ramps at 1.0 °C/min up or 0.6 °C/min down and the whole run shifts
  later by that ramp.
- **Trans is usually longer than the ramp.** pre3's ramp needs 2 min, but its window is 26 min. T reaches its target
  early, and the hold still starts at the end of the window. That gap is RH settling time built into the schedule.
- **Point 2 (−20 °C) is the longest transition, at 70 min.** The chamber must pull down to −18 °C within 90 min of
  the point's start, or the run aborts to SAFE.
- **The bake** lasts 45 min in total after point 28 (23-min heat-up plus 22-min hold), as the schedule's text
  requires.
- Every RH set point has its dew point at or below the 19 °C cap. `--plan` checks this, and the run refuses to start
  if any point is above it.
- **The 19 °C cap protects the unheated Palas Frog line** (Calibration `3ca7f85`, 2026-10-23): the chamber dew point
  stays at least 3 °C under the line temperature, taken as 22 °C. If the line is colder than about 22 °C the cap is
  too high for it; this routine does not measure the line, so check the lab temperature before a run. The warm humid
  points of the earlier 23 °C schedule (35/45 to 20/90, dew points up to 22.7 °C) are replaced by the 20 °C ladder,
  points 15–19.

---

## The Routine in Blocks

| Block | Points | Elapsed | Length | What the chamber does |
|---|---|---|---:|---|
| Pre-cycle checks | pre1–pre3 | 0:00–1:57 | 1 h 57 | Dry blank, humid blank at 80 %, then a loading check with aerosol. An operator answers each one. |
| Anchor A | 1 | 1:57–2:24 | 27 min | 22 °C / 15 %, the dry reference |
| Cold, dry | 2, 3 | 2:24–4:54 | 2 h 30 | −20 °C, then 0 °C, with humidity OFF |
| Cold, humid (steam) | 4, 5 | 4:54–6:07 | 1 h 13 | −2.5 °C at 70 %, then 85 % |
| Warm out of the cold | 6, 7 | 6:07–8:10 | 2 h 03 | 5 °C / 85 %, then 42 °C / 20 %. Both are dry warm-ups, so the sensors warm above the dew point first. |
| Humid, falling T | 8–10 | 8:10–10:13 | 2 h 03 | 30 → 25 → 20 °C at 30–35 % |
| Anchor | 11 | 10:13–11:01 | 48 min | 20 °C / 15 % |
| High dew point, falling T | 12–14 | 11:01–12:59 | 1 h 58 | 35 → 25 °C, RH rising 35 → 65 %, Td 17.3–18.4 °C, under the 19 °C cap |
| 20 °C humidity ladder (kappa) | 15–19 | 12:59–16:03 | 3 h 04 | 20 °C at 45, 60, 70, 80 and 90 %, Td 7.7 → 18.3 °C |
| 15 °C sweep | 20–22 | 16:03–18:13 | 2 h 10 | 15 °C at 30, 65 and 90 % |
| 10 °C / 5 °C | 23–25 | 18:13–20:09 | 1 h 56 | 10 °C at 35 and 65 %, then 5 °C with humidity OFF |
| Humid and fog | 26, 27 | 20:09–21:32 | 1 h 23 | 10 °C at 90 %, then 95 % fog |
| Closing anchor | 28 | 21:32–23:00 | 1 h 28 | Back to 22 °C / 15 % with a dry warm-up and purge |
| Bake | bake | 23:00–23:45 | 45 min | 45 °C / 15 % with purge, to dry the chamber and the lines |
| Stop | stop | 23:45 | — | Humidity OFF, then STOP. **Open the door.** |

The order is set by physics. The cold points run while the chamber is still dry, the highest dew points come in the
middle, and the fog comes last before the dry anchor and the bake.

---

## What Happens Inside Every Point

The routine reads the chamber summary every **10 s** and logs it. It reads the T640 every **10 s** in a background
thread over Modbus/TCP, and every safety rule is checked at every tick. The temperature set point is updated every
**60 s**.

1. **Aerosol feed check** (only between pre2 and pre3). The routine asks the operator to switch the feed from HEPA
   bypass to aerosol and answer `go`. The previous point's set points stay in force while it waits. If nobody answers
   in 30 min, the run goes to SAFE.
2. **Transition (Trans column).** These happen together:
   - T ramps from the previous set point at the row's rate.
   - The humidity follows the **Humidity** column.
   - The purge switches to the row's setting at the first tick.
   - At the end of the window T is set exactly to its target.
3. **Hold (Hold column).** The routine logs *Routine Holding* (`RTNCHG` 10) and starts the soak. Timed rows hold for
   exactly their minutes. Guaranteed rows count only in-band minutes, and they are abandoned at hold + 60 min with a
   warning (`RTNCHG` 11).
   - For dry warm-ups, humidity switches ON at the row's RH at the end of the transition, or 10 min after it for
     points 6 and 26.
4. **Pre-cycle answer** (pre1–pre3 only). At the end of the hold the routine runs its automatic checks and then asks
   `pass` or `fail`. See [Pre-cycle checks](#pre-cycle-checks).
5. The next point starts straight away.

**First point of a run, or a resumed run.** The first point has no schedule window. It ramps from the chamber PV at
1.0 °C/min up or 0.6 °C/min down. Two extra rules apply:
- A rise of 5 °C or more from a chamber RH of 40 % or more ramps dry and adds humidity 10 min after arrival.
- A pull-down below 0 °C ramps dry.

---

## Pre-cycle Checks

These three checks gate the calibration. Point 1 does not start until pre3 passes.

| Check | When asked | The routine checks | The operator checks |
|---|---|---|---|
| **pre1** zero / LOD blank | ~0:30 | T640 PM2.5 mean over the last 5 min ≤ 0.3 µg/m³ | IPS blank sd → LOD = 3 sd |
| **pre2** humid blank | ~1:06 | T640 PM2.5 ≤ 0.3 µg/m³; chamber RH within 80 ± 5 % within 15 min of arrival; *provisional*: T640 sample RH ≤ 40 % (log only, never SAFE) | — |
| **pre3** loading check | ~1:57 | T640 PM2.5 ≥ 3 µg/m³; chamber RH ≤ 20 % within 25 min of the step start | Record the IPS/T640 PM2.5 ratio as the anchor-A reference |

- If an automatic item fails, the run aborts to SAFE at once.
- Otherwise the routine waits for an answer, with every rule still running. Answer `pass` or `fail` in its terminal,
  or from any shell:

  ```bash
  python3 runRoutineV8.py --operator pass
  ```

- `fail`, or no answer within **30 min**, sends the run to SAFE.
- Each wait adds the operator's time to the run, up to 30 min per check.

---

## When the Operator Is Needed

| Elapsed | What to do |
|---|---|
| Before 0:00 | Water tank filled with distilled water at 18 psi and the pump on. Dry-air purge supply on. T640 running. Aerosol feed on **HEPA bypass**. See the checklist in [V8_ROUTINE_UPDATE.md](V8_ROUTINE_UPDATE.md#weekend-operator-checklist). |
| ~0:30 | pre1: check the IPS blank, then answer `pass` / `fail` |
| ~1:06 | pre2: answer `pass` / `fail` |
| ~1:06 | Switch the aerosol feed to **aerosol**, then answer `go` |
| ~1:57 | pre3: record the IPS/T640 ratio, then answer `pass` / `fail` |
| 1:57–23:45 | Nothing scheduled. Someone checks in overnight with `journalctl -fu runRoutineV8`, `status.sh` or Grafana `BTL433ESC001*`. |
| 23:45 | **Open the chamber door.** |

With `--no-t640` the T640 rules are off. Someone must then watch the T640 sample RH during **pre2 (0:30–1:06)** and
**points 12–14 (11:01–12:59) and 18–19 (14:49–16:03)**, and send `--operator safe` when the printed threshold is crossed.

---

## How Long It Really Takes

**The plan is 23 h 45 min.** Three things can add to it:

| Cause | Adds | Worst case |
|---|---|---|
| Operator answers (3 checks and 1 feed change) | The time until each answer | 30 min each, then SAFE instead of the run |
| Guaranteed soaks (points 1–3 and 8–22, 18 points) | The minutes the T PV spends outside its band | 60 min per point, then the soak is given up |
| First-point ramp, if the chamber is not at 22 °C | Distance ÷ 1.0 °C/min (up) or ÷ 0.6 °C/min (down) | — |
| A transition whose ramp needs more than its window + 0.5 min | The extra ramp time, printed | None in v8 at 22 °C start |

In practice, expect about **24–25 h** with a prompt operator and a chamber that tracks its set points.

---

## Safety: What Can Stop the Run

### Condensation guard (every 10 s)

- **Cap:** no RH set point is ever sent whose dew point is above **19 °C** at the T being sent.
- **HOLD** lowers RH to an 18 °C dew point for the rest of the point, and never raises it again within that point. It
  fires on any of these:
  - chamber dew point > 20 °C for 2 min;
  - T640 sample RH > 45 % for 5 min while the ASC heater duty is ≥ 95 %;
  - chamber dew point > T640 box T − 3 °C.
- **ABORT to SAFE** on any of these:
  - T640 sample RH > 75 % for 2 min, > 60 % for 5 min, or > 60 % for 10 min;
  - chamber dew point > 21 °C for 2 min (checked before the HOLD, so a jump straight past 21 °C aborts without one);
  - chamber dew point ≥ T640 box T;
  - T640 fault bit set for 5 min while sample RH > 45 %.

### Other abort rules

- A pre-cycle check failed or was not answered within 30 min.
- No valid chamber reading for 5 min.
- A set point not confirmed by the read-back for 5 min.
- Point 2 has not reached −18 °C within 90 min.
- No T640 reading for 5 min. A run with no T640 reading in its first 60 s is refused before anything is sent.
- At a humid soak (T ≥ 15 °C, purge OFF), RH PV stays more than 10 % below its set point for 15 min. The water or
  steam supply is short.

**Flag only (no abort):** with the purge ON, RH PV more than 5 % above its set point for 15 min means the purge or the
compressed air is short. The routine prints and logs this.

### SAFE (after any abort)

| Step | Lasts |
|---|---|
| 1. Humidity OFF | Immediately |
| 2. Ramp T to the PV clamped to 22–30 °C (1.0 °C/min up, 0.6 °C/min down) | Up to 42 min (from −20 °C) |
| 3. Dry-out: humidity ON at 15 %, purge ON | Ends once the chamber dew point is ≤ 5 °C and the T640 sample RH is ≤ 35 % for 10 min; otherwise at 60 min if dry by then; never longer than 90 min (always 90 with `--no-t640`) |
| 4. Humidity OFF, STOP | The routine waits up to 20 s for the summary to report `standby` |

After SAFE the **door stays closed** until someone checks the chamber. The next start needs:

```bash
python3 runRoutineV8.py --clear-abort "<what was checked>"
```

### Every other way the run can end

| How it ends | What the chamber gets |
|---|---|
| Normal end | Humidity OFF, STOP, `standby` confirmed (up to 20 s), "open the door" |
| Ctrl-C, `systemctl stop`, closed terminal | Humidity OFF, then STOP, at once |
| Crash, kill or hang under systemd | Restarted after 15 s with `--resume`: it resumes at the same point, or continues SAFE |
| systemd gives up (more than 5 starts in 30 min) | `parkChamberV8.py`: humidity OFF, then STOP |
| Host power loss | At the next boot, `v8-park-on-boot.service`: humidity OFF, then STOP |
| The chamber leaves CONSTANT by itself (alarm, water out, panel STOP) | Nothing more is sent; the chamber's interlock wins. The run is logged and exits. |

**Exit codes:** 0 complete, 2 refused, 3 SAFE completed, 4 the chamber left CONSTANT, 5 failure, 130 interrupted.

---

## Running It

From `firmware/xu4Mqtt`:

| Command | What it does |
|---|---|
| `python3 runRoutineV8.py --plan` | Print this timetable with wall-clock times; contacts nothing |
| `python3 runRoutineV8.py --t640-check` | Read the T640 three times, 10 s apart |
| `sudo systemctl start runRoutineV8` | Start the run under systemd (recommended: restarts and parking work) |
| `journalctl -fu runRoutineV8` | Follow the run's output |
| `python3 runRoutineV8.py --operator pass\|fail\|go\|safe` | Answer the running routine, or send it to SAFE now |
| `python3 runRoutineV8.py --resume` | Resume at the point the state file names |
| `--start-point <name>` / `--skip-precycle` / `--skip-bake` | Run part of the schedule |
| `--no-t640` | Run without reading the T640 (a person watches it instead) |

Under systemd, options go in `v8/state/run.env`, for example `V8_ARGS=--skip-precycle --start-point 1`.

Every status line shows the point, its phase, T and RH (set and PV), the purge, time in the point, total run time and
**time left**. For example:

```text
Point 12 (15/32, soak) | T set 35.0 -> 35 (PV 34.9) | RH set 35.0 (PV 35.2) | purge OFF | point 0:21 | run 11:22, about 12:23 left | T640 sample RH 31.0 %, box 38.4 C
```

---

## What Gets Logged

All records go through the normal `sensorFinisher` pipeline as `BTL433ESC001*` streams. `publishV8.py` sends them to
MQTT from its own process.

| Stream | When |
|---|---|
| `BTL433ESC001STATUS`, `TMPRT`, `HMDTY`, `DAP`, `PRGRM` | Every 10 s |
| `BTL433ESC001CHNG` | Every command sent |
| `BTL433ESC001RTNCHG` | Run started, each hold start (*Routine Holding*, iteration = position 1–32), a guaranteed soak given up, run ended |
| `BTL433ESC001RTNPRGV2` | Once per point, at the start of its transition |
| `BTL433ESC001RTNV8` | Events: transition started, hold start, humidity on after a dry warm-up, dew-point HOLD, abort, SAFE, pre-cycle answers, flags, run ended |

The full field and event lists are in [V8_ROUTINE_UPDATE.md](V8_ROUTINE_UPDATE.md#logging).
<!-- END ADDED BY CLAUDE -->
