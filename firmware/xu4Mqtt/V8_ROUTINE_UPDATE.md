<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20) -->
# v8 Routine Update — What Changed and Why

This update adds [`runRoutineV8.py`](runRoutineV8.py), a routine that runs the MINTS-AI calibration programme **v8**
([`v8/schedule.tsv`](v8/schedule.tsv)) point by point. It is a simplified copy of Dr. Lary's chamber runner
(Calibration `tools/run_chamber_cycle.py` + `calib/chamber/`, about 2,900 lines). The runner needs live T640, IPS and
Influx data. This routine keeps the parts that need only the chamber, and it logs exactly as Lakitha's routines do,
so the data reaches Influx as the same `BTL433ESC001*` streams that the calibration pipeline already reads.

The request (Rittik Patra, 2026-10-20): start from the runner, copy it, simplify it as much as possible, and use
Lakitha's `runRoutineCustom.py` as the reference for simplicity and for the data pipeline. For the weekend run, the
points must be visited in the right order, and condensation must be avoided.

Calibration sources: commit `d4db474` (HEAD on 2026-10-20). `schedule.tsv` was last changed in `d809739`; the sha256
of its bytes is `9f59b5fbbedd238b…` ([v8/README.md](v8/README.md)).

---

## At a Glance

| Area | Lakitha's `runRoutineCustom.py` | Dr. Lary's runner | `runRoutineV8.py` (this update) |
|---|---|---|---|
| Points | Every T × RH grid combination | `schedule.tsv` v8 in file order | `v8/schedule.tsv` (verbatim copy, sha logged) in file order |
| Temperature change | Set point jumps to the target | Ramped at the row's rate, every 10 s, over the schedule's window D | Ramped at the row's rate, new set point every 60 s, until it reaches the target |
| Humidity on ramps | Always ON when reachable | Dew-point trajectory; dry warm-ups; resume rule | Same (copied) |
| Humidity OFF | Not possible | Yes | Yes (`set_humidity_enabled`) |
| Dry-air purge | Not controlled | Per row | Per row (`set_dry_air_purge`) |
| Soak | ±2 °C / ±2 %RH, then 120 s | Timed or guaranteed (band), 60-min give-up | Same (copied) |
| Dew-point cap | None | Chamber PV, T640 sample RH, T640 box T, tube heater | Chamber-PV dew point only (HOLD and ABORT), plus a cap on every RH set point sent |
| Abort rules | None | Abort list and excursion ABORT (chamber, T640, IPS) | The 4 chamber-only rules |
| Failure handling | Chamber stopped only after a normal end | SAFE dry-out, emergency STOP, watchdog | SAFE dry-out (fixed 60 min), emergency STOP |
| Logging | `BTL433ESC001*` via `sensorFinisher` | JSON-lines events file (writes no `BTL433ESC001*` stream) | `BTL433ESC001*` via `sensorFinisher`, plus `BTL433ESC001RTNV8` events |
| Size | 53 lines + `Chamber.Routine` | ~2,900 lines | 823 lines: 622 of code, 100 of comments and docstrings, 101 blank |

---

## How a Point Runs

The summary is read and logged every 10 s (`get_and_write_summary(expanded=True)`) in every phase.

1. **Transition.** The T set point ramps from where the chamber is to the row's `T_set_C` at the row's
   `ramp_rate_C_per_min`. A new set point is sent every 60 s. The first point of a run ramps at the SAFE rates
   (1.0 °C/min up, 0.6 °C/min down), as the runner does. From the first tick:
   - the purge follows the row's `dry_air_purge`;
   - humidity follows the row (see [Condensation guard](#condensation-guard)).
2. **Arrival.** The ramp has reached `T_set_C` and the summary reads it back. The routine writes `RTNCHG` change 10
   (*Routine Holding*) with `iteration` = the point's position in this run, and prints the row's `check_or_rule` text.
   For pre1–pre3 the text is printed as an **operator checklist**: those checks need T640 / IPS data and are not
   automated here.
3. **Soak.**
   - Timed rows (`none(timed)`) hold `hold_min_at_setpoint` from arrival.
   - Guaranteed rows count hold time only while |T_pv − T_set| ≤ the row's band. If the band has not held long
     enough 60 min after the hold time, the soak is given up: `RTNCHG` change 11 and a printed warning.
4. **Aerosol feed.** When a row's `aerosol_feed` differs from the previous row's (only pre2 → pre3 in v8), the routine
   prints an operator message and waits for Enter (unless `--no-operator-wait`). It never waits anywhere else.

After the last point (bake, or 30 with `--skip-bake`) the **stop row** runs: humidity OFF, STOP, read back
`standby`, and a printed "open the door" message.

**Timing.** `--plan` prints the exact plan: **23.2 h** including the pre-cycle and the bake, against 24.8 h for the
runner. The difference comes from the runner's transition window D. The schedule gives each transition a window that
also covers RH changes (for example 13 min for 20 °C / 35 % → 20 °C / 15 % at point 11). Here the hold starts when the
temperature has arrived, so after an RH-only change the first minutes of the hold include the RH settling. The point
order, temperatures and RH set points are identical to the runner's `--plan` (checked on 2026-10-20, 34 points).

---

## Condensation Guard

Water condenses when moist air meets a surface colder than its dew point. The surfaces at risk are the sensors and
the sample tube: they lag the air, especially when warming into humid air or cooling while humid. Everything below
needs only the chamber's T and RH and the Magnus formulas copied from Calibration `calib/chamber/psychro.py`.

1. **Dew-point trajectory on humid ramps.** When `ramp_humidity_system` is ON and T changes, every 60-s update sets
   RH = `dp_trajectory_rh(T_now, T_from, T_target, Td_from, Td_target)`. The dew point moves linearly with the
   temperature progress, so it is never ahead of the air temperature.
   - `Td_from` is the dew point of the RH set point in force, or of the chamber PV if humidity was off.
   - `Td_target` is the row's `dew_point_C`.
2. **Dry warm-ups.** When `ramp_humidity_system` is OFF, humidity stays OFF for the whole ramp. It switches ON with
   the row's RH `humidify_after_min` after arrival, so the units warm above the coming dew point first (points 6, 7,
   16, 28, 30). Rows with `humidity_system` OFF (2, 3, 27) stay OFF throughout.
3. **First step / resume rule** (host duty 7). On the first point of a run, including `--start-point`:
   - a rise of ≥ 5 °C from a chamber RH PV ≥ 40 % ramps dry and adds humidity 10 min after arrival (the schedule's
     longest `humidify_after_min`);
   - a pull-down below 0 °C to a humid target ramps dry and adds humidity at arrival.
4. **Dew-point cap (23 °C, the `excursion` row).**
   - No RH set point is ever sent whose dew point at the T set point being sent is above 23 °C.
   - `--plan` checks every point and the routine refuses to start if one is above it.
   - Every 10 s the dew point of the chamber PV is computed. If it stays above 24 °C (cap + 1) for 2 min, the RH
     set point steps down to the RH whose dew point is 22 °C (cap − 1) at the current T set point. It stays there for
     the rest of the point and is never raised again within the point. The event is logged (`RTNV8` event 4).
   - If the chamber-PV dew point stays above 26 °C (cap + 3) for 5 min anyway, the run aborts to SAFE (the
     chamber-PV part of the excursion ABORT).
5. **Order.** The points run exactly in TSV order. The schedule puts the cold points while the chamber is dry and the
   fog last. Skipped points (by `--start-point`, `--skip-precycle`, `--skip-bake`) are printed.

---

## Safety

**However the script ends, the chamber is left safe.**

| How it ends | What the routine does |
|---|---|
| Normal end | Stop row: humidity OFF, STOP, read back `standby`, "open the door" |
| Ctrl-C or SIGTERM | Humidity OFF, then STOP, at once (each tried twice) |
| Abort rule, or an unexpected error once in CONSTANT | Simplified SAFE (below) |
| Error before CONSTANT | Humidity OFF, then STOP |
| The chamber leaves CONSTANT by itself (alarm, water out, panel STOP) | Nothing more is sent: log, print, exit. The interlock wins. |
| The chamber is in program mode at start | Refused, nothing is sent |

**Simplified SAFE** (from the `safe` row):

1. humidity OFF;
2. ramp T to the PV clamped to 22–30 °C (1.0 °C/min up, 0.6 °C/min down);
3. on arrival, humidity ON at 15 % with the purge ON for 60 min;
4. humidity OFF and STOP, door closed (the next person opens it).

If the chamber cannot be read, or a command is not confirmed, for 5 min during SAFE, the routine sends humidity OFF
and STOP and exits.

**Abort rules kept** (chamber data only, from the `abort` row):

- no valid chamber summary for 5 min;
- a set point not confirmed by the summary read-back for 5 min (an unconfirmed set point is re-sent at every 60-s
  update);
- the pull-down to −18 °C not reached within 90 min at the −20 °C point;
- the chamber-PV dew point above 26 °C (cap + 3 °C) for 5 min (from the `excursion` row).

**Read-back.** After each command the routine reads the summary again and compares the set value or state with what
it sent. `Chamber` now has `request_timeout`; the routine uses 10 s, so a hung request cannot freeze the run.

---

## Logging

All records go through `mSR.sensorFinisher` (CSV + MQTT), like every other stream.

| Stream | When | Fields |
|---|---|---|
| `BTL433ESC001STATUS`, `TMPRT`, `HMDTY`, `DAP`, `PRGRM` | Every 10 s (expanded summary) | Unchanged (`Chamber.write_*`) |
| `BTL433ESC001CHNG` | Every command | Unchanged; new change IDs 13 *Humidity System Set*, 14 *Dry Air Purge Set* |
| `BTL433ESC001RTNCHG` | 1 *Routine Started* (iteration 0) at the start; 10 *Routine Holding* at each arrival (iteration 1…N); 11 at a guaranteed-soak give-up; 2 *Routine Ended* at the end | `dateTime`, `changeID`, `changeLabel`, `iteration`, `success` (as `run_routine`) |
| `BTL433ESC001RTNPRGV2` | Once per point, at its transition start | As `run_routine`; humidity OFF → `entryHumidity` −100, `entryHC` 0 |
| `BTL433ESC001RTNV8` (new) | Events only | `dateTime`, `eventID`, `eventLabel`, `point`, `tag`, `temperatureSet`, `humiditySet` (−100 = OFF), `humiditySystem`, `dryAirPurge`, `aerosolFeed`, `holdMin`, `rampRate` (−1 = none), `gsBand` (−1 = timed), `scheduleSha` |

`RTNV8` events: 0 run started, 1 transition started, 2 arrived, 3 humidity enabled after a dry warm-up, 4 dew-point
hold, 5 guaranteed soak given up, 6 soak ended, 7 aborted, 8 SAFE started, 9 SAFE ended, 10 run ended, 11 chamber left
CONSTANT, 12 emergency stop. The `BTL433ESC001` prefix keeps the stream in the pipeline's `REF_MEAS_PREFIXES`.

The `iteration` restarts at 1 for every new run, including a `--start-point` restart (`calib/fit/diagnostics.py`
reads it as the step counter).

The summary is now expanded on every read. `run_routine` expanded it only at start-up, so `DAP.enabled` (the purge
column) was barely refreshed.

---

## Usage

From `firmware/xu4Mqtt`, like the other routine scripts:

```bash
python3 runRoutineV8.py --plan
```

```bash
python3 runRoutineV8.py
```

| Option | Meaning |
|---|---|
| `--plan` | Print the table of points (ramp and hold minutes, planned start / arrival / end, the clock time if started now, the total) and the dew point of every RH set point. Contacts nothing. Refuses (exit 2) if a dew point is above the cap. |
| `--start-point <name>` | Resume at that point (`pre1`–`pre3`, `1`–`30`, `bake`). |
| `--skip-precycle` | Skip pre1–pre3. |
| `--skip-bake` | Stop after point 30. |
| `--chamber-url` | Web Controller base URL (default `http://192.168.20.121`). |
| `--no-operator-wait` | Do not wait for Enter at the aerosol-feed change. |

Exit code 0 when the run completed and the STOP was confirmed, 1 otherwise, 2 when refused by the cap check. The last
line printed says how to resume (`--start-point <point>`).

Tests (hermetic: simulated chamber, fake clock, no network, no MQTT, `credentials.yml` never read):

```bash
python3 -m unittest discover -s tests -v
```

---

## Kept / Simplified / Dropped

| Runner feature | Here | Why |
|---|---|---|
| Points from `schedule.tsv` in order | **Kept** (verbatim copy, sha logged) | One source of truth; the order is physics |
| Ramps at the row's rate; dew-point trajectory; dry warm-ups; resume rule | **Kept** | Condensation |
| Dew-point cap / excursion HOLD | **Simplified**: chamber-PV dew point only | The T640 sample-RH / box-T / tube-heater parts need Influx |
| Excursion ABORT | **Simplified**: chamber-PV Td > cap + 3 °C for 5 min only | The sample-RH, Td ≥ box T and fault-bit parts need the T640 from Influx |
| Guaranteed soaks, 60-min give-up | **Kept** | Simple, and part of the protocol |
| Schedule-exact transition window D | **Simplified**: ramp until T arrives | Lakitha-style; total 23.2 h instead of 24.8 h |
| T set point every 10-s tick; RH-only change spread over D | **Simplified**: T every 60 s; RH-only change at once | The controller ramps RH itself; the air is already at T |
| First-step RH-only rate limit (6 %/min) | **Dropped** | Same reason; only the first step of a run |
| Pre-cycle checks pre1–pre3 | **Simplified**: timed holds plus a printed checklist | Need T640 / IPS data from Influx |
| Abort list: T640 stale, humid-soak RH shortfall, IPS/T640 ratio; purge-excess flag | **Dropped** | Need Influx feeds (the RH shortfall could be chamber-only; see open questions) |
| Abort list: no reading, unconfirmed, pull-down | **Kept** | Chamber data only |
| SAFE dry-out | **Simplified**: fixed 60 min, no T640 early end, no 90-min hard limit | Chamber data only |
| Chamber left CONSTANT → hands off | **Kept** | Interlock wins |
| Command client with retries and back-off (`espec.py`) | **Simplified**: `Chamber` + one read-back; unconfirmed set points re-sent every 60 s | Lakitha's pipeline; the 5-min unconfirmed abort still applies |
| Influx / JSONL feeds, notifications, systemd watchdog, `--resume` from an events log, `--simulate`, chained cycles | **Dropped** | Not needed for a supervised weekend run; `--start-point` covers restarts |
| Gate G0 start checks | **Dropped** (operator checklist below) | Need Influx, NTP and T640 registers |
| Events JSON-lines file | **Replaced** by `BTL433ESC001RTNV8` plus the existing streams | Lakitha's data pipeline |

---

## Changed

| File | Change | Why |
|---|---|---|
| `runRoutineV8.py` | New: the v8 routine | The deliverable |
| `v8/schedule.tsv`, `v8/README.md`, `v8/.gitattributes` | New: verbatim schedule copy, its provenance and sha256, kept byte for byte | One source of truth |
| `benchTestV8.py` | New: operator-present bench test of humidity ON/OFF and purge ON/OFF, with a cable-pull mode | Host duty 10 before the first run |
| `tests/` | New: hermetic tests | Section 7 of the task |
| `mintsXU4/especChamber/chamber.py` | Added `set_humidity_enabled` (CHNG 13), `set_dry_air_purge` (CHNG 14), their two `change_mapping` labels, and the optional `request_timeout` passed to the two `requests` calls | The v8 routine needs humidity OFF, the purge and a timeout; old callers are unchanged (`None` = no timeout) |
| `status.sh` | Also reports `runRoutineV8.py` | `pgrep -f 'runRoutine.py'` does not match it |
| `README.md` | Short "v8 routine" section | Points here |

## Left Alone on Purpose

| What | Why |
|---|---|
| `mintsSensorReader.py`, `mintsDefinitions.py`, `mintsLatest.py`, MQTT settings | The data pipeline stays as it is |
| Every `write_*` method (stream names, field names, order, types) | Calibration's `build_dataset.py` reads them |
| `write_time_signal_set` writing to `DAP` | Changing it changes a stream the pipeline reads; reported below |
| The existing `set_*` methods, `get_and_write_summary`, `get_available_chamber_index`, `execute_command`'s request and response handling | Pipeline; only the timeout argument was added |
| `credentials.yml` | Never opened, staged or committed; reported below |
| `runRoutine.py`, `runRoutineCustom.py`, `stopChamber.py`, `Chamber.Routine` / `run_routine` | The old grid routines and the manual STOP keep working |
| The default chamber URL `http://192.168.20.121` | Lakitha's; `--chamber-url` overrides it |
| Everything in the Calibration repository | Read and copied from only |

## Provenance

Every block in the new and changed files carries one tag: `ORIGINAL (Lakitha)`, `COPIED (Dr. Lary)` or
`ADDED BY CLAUDE`. `grep -rn -E "ORIGINAL \(Lakitha\)|COPIED \(Dr. Lary\)|ADDED BY CLAUDE" firmware/` lists them.
Calibration line numbers are at `d4db474`; Lakitha's at main `ccc8ab8`.

| File | Block | Origin | Source |
|---|---|---|---|
| `runRoutineV8.py` | Default URL `url` | Lakitha | `runRoutineCustom.py:17` |
| `runRoutineV8.py` | Credentials, chamber index, `Chamber(...)` in `main` | Lakitha (lazy import, `--chamber-url`, `request_timeout` by Claude) | `runRoutineCustom.py:7-27` |
| `runRoutineV8.py` | `routine_mapping` | Lakitha | `chamber.py:483-489` |
| `runRoutineV8.py` | `log_rtnchg` body | Lakitha (helper wrapper by Claude) | `chamber.py:891-903` |
| `runRoutineV8.py` | `log_rtnprg` body | Lakitha (OFF values −100 / 0 by Claude, as V7) | `chamber.py:833-848` |
| `runRoutineV8.py` | `GS_GIVE_UP_MIN`, `RESUME_RISE_*` | Dr. Lary | `cycle.py:78-80` |
| `runRoutineV8.py` | `RH_RANGE`, `SET_TOL` | Dr. Lary | `espec.py:47-48` |
| `runRoutineV8.py` | `es_hpa`, `dew_point`, `rh_for_dew`, `dp_trajectory_rh` | Dr. Lary (verbatim) | `psychro.py:15-37` |
| `runRoutineV8.py` | Rule-text patterns `grab`, `parse_rules` | Dr. Lary (simplified) | `schedule.py:230-307` |
| `runRoutineV8.py` | `apply` | Dr. Lary (simplified) | `cycle.py:545-570` |
| `runRoutineV8.py` | `check_rules`, `hold` | Dr. Lary (simplified) | `cycle.py:603-609, 626, 631-634, 637-639, 653-684` |
| `runRoutineV8.py` | `startup` | Dr. Lary | `cycle.py:776-802` |
| `runRoutineV8.py` | `run_point` (transition, resume rule, Td_from/Td_target, soak, give-up) | Dr. Lary (simplified) | `cycle.py:809-936` |
| `runRoutineV8.py` | `stop`, `emergency_stop` | Dr. Lary (simplified) | `cycle.py:210-232, 938-946` |
| `runRoutineV8.py` | `safe`, `safe_guarded` | Dr. Lary (simplified) | `cycle.py:948-1062` |
| `runRoutineV8.py` | `run` | Dr. Lary (simplified) | `cycle.py:1097-1184` |
| `runRoutineV8.py` | Settings, `Point`, `load_schedule`, `--plan`, exceptions, `read`, `confirmed`, `td_pv`, `capped_rh`, `loop`, `status`, `log_event` (RTNV8), `feed_change`, CLI, SIGTERM | Claude | — |
| `benchTestV8.py` | Credentials, chamber index, `Chamber(...)` | Lakitha | `runRoutineCustom.py:7-27` |
| `benchTestV8.py` | Everything else | Claude | — |
| `chamber.py` | Whole file except the blocks below | Lakitha | main `ccc8ab8` |
| `chamber.py` | `request_timeout`, labels 13/14, `set_humidity_enabled`, `set_dry_air_purge` | Claude (payloads from Dr. Lary's `espec.py:10-11, 243-255`) | — |
| `status.sh`, `README.md` | Whole file except the marked block | Lakitha | main `ccc8ab8` |
| `status.sh`, `README.md` | v8 block | Claude | — |
| `v8/schedule.tsv` | Whole file | Dr. Lary (verbatim) | Calibration `Docs/protocol/schedule.tsv` at `d809739` |
| `V8_ROUTINE_UPDATE.md`, `v8/README.md`, `v8/.gitattributes`, `tests/*` | Whole files | Claude | — |

---

## Bench Test (before the first v8 run)

Operator at the chamber, chamber at lab conditions, door closed:

```bash
python3 benchTestV8.py --i-am-at-the-chamber
```

It starts CONSTANT at the current temperature, switches the humidity system ON / OFF and the purge ON / OFF, reads
each one back, prints PASS or FAIL, and always ends with humidity OFF and STOP. Without `--i-am-at-the-chamber` it
refuses and sends nothing.

**Cable-pull check** (shows the timeout and the no-reading abort working):

1. Run `python3 benchTestV8.py --i-am-at-the-chamber --cable-pull`.
2. After 3 valid reads, pull the chamber's network cable.
3. Each failed read must print "NO VALID READING" within about 20 s (10-s connect + 10-s read timeout), never hang.
4. After 3 failed reads, plug the cable back. The reads must become valid again, then the test stops the chamber.
5. In a real run the same outage, if it lasts 5 min, aborts to SAFE; if SAFE cannot reach the chamber for 5 more min,
   the routine tries humidity OFF and STOP and exits. **With the cable out these commands cannot arrive: stop the
   chamber at the panel.**

---

## Weekend Operator Checklist

Before the start:

- [ ] Water tank filled (distilled water) and pressurised (18 psi), pump switched on.
- [ ] Dry-air purge: air supply on, purge unit plugged in.
- [ ] T640 running and logging to Influx; IPS units logging.
- [ ] `python3 runRoutineV8.py --plan` reviewed: points, total, "at or below the 23 C tube cap".
- [ ] Bench test passed (first v8 run only).
- [ ] Aerosol feed on **HEPA bypass** for pre1 and pre2.
- [ ] Run inside `screen` or `tmux`, so it survives a dropped SSH session.

During the run:

- [ ] pre1–pre3: check the printed T640 / IPS checklist by hand (blanks, LOD, loading check). If a check fails,
      press Ctrl-C (humidity OFF + STOP) and fix it first.
- [ ] At the pre2 → pre3 prompt, switch the aerosol feed to **aerosol** and press Enter.
- [ ] Someone checks in overnight (console, `status.sh`, Grafana `BTL433ESC001*`).

After the stop row:

- [ ] Open the chamber door (the routine prints this).
- [ ] After a SAFE end the door stays closed until someone checks the chamber.

---

## Findings (reported, not fixed)

1. **The time signal is written to the purge stream.** `write_time_signal_set` uses `sensorIDPost = "DAP"`, like
   `write_dap_set`. Each expanded summary therefore writes two `BTL433ESC001DAP` records with the same timestamp and a
   field `enabled` that means different things (time signal 1 / purge). The CSV files have both rows. In Influx, if
   both points land on the same timestamp, the later write (the purge) wins for `enabled`; if not, the column
   alternates. The pipeline reads `DAP.enabled` as the purge. Proposed fix: give the time signal its own suffix (for
   example `BTL433ESC001TMSIG`), and in the pipeline keep only `DAP` rows that carry `dapGroup`. Not applied, because
   it changes a stream the pipeline reads.
2. **`credentials.yml` is tracked in git** (`firmware/xu4Mqtt/mintsXU4/credentials.yml`) although `.gitignore` has
   `*.yml`. The ignore rule does not apply to a tracked file. It was not opened, printed, edited or staged here. It
   should be removed from the index (`git rm --cached`) and its secrets rotated, by the repository owner.
3. **`Chamber.default_if_empty` compares with `is " "`** (`chamber.py`, `write_status`). Python 3.8+ warns about it
   (`SyntaxWarning: "is" with 'str' literal`); the value is almost never the same object, so the field is always −1.
   Harmless for the pipeline; left alone.

## Open Questions for Dr. Lary

1. Is this simplified copy acceptable for the weekend run, given the dropped T640-based rules (pre-cycle checks,
   T640 stale, the sample-RH / box-T excursion parts, the IPS/T640 ratio)?
2. Should gate G0 become a pre-start script (`--plan` plus the Influx / NTP / T640 checks)?
3. The `DAP` issue (finding 1): new suffix for the time signal, or a pipeline-side filter?
4. The tracked `credentials.yml` (finding 2).
5. The new stream name `BTL433ESC001RTNV8`: acceptable, or another name?
6. Arrival is "T has arrived". After an RH-only change (points 11, 23, 24, 26, 29, and pre2/pre3/30) the hold starts
   while RH still settles; the schedule allowed 2–29 min for it. Should arrival also wait for |RH PV − set| ≤ 5 %
   (as Lakitha's humidity-controlled branch does with ±2 %), or for the schedule's window D?
7. The humid-soak RH-shortfall abort (RH PV < set − 10 % for 15 min) needs only chamber data. Should it be added back?
<!-- END ADDED BY CLAUDE -->
