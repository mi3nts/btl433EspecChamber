<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20; must-fix review, 2026-10-22) -->
# v8 Routine Update — What Changed and Why

This update adds [`runRoutineV8.py`](runRoutineV8.py), a routine that runs the MINTS-AI calibration programme **v8**
([`v8/schedule.tsv`](v8/schedule.tsv)) point by point. It is a simplified copy of Dr. Lary's chamber runner
(Calibration `tools/run_chamber_cycle.py` + `calib/chamber/`, about 2,900 lines). It reads the chamber over its Web
Controller and the T640 over Modbus/TCP, both on the lab LAN (no Influx), and it logs exactly as Lakitha's routines
do, so the data reaches Influx as the same `BTL433ESC001*` streams that the calibration pipeline already reads.

The request (Rittik Patra, 2026-10-20): start from the runner, copy it, simplify it as much as possible, and use
Lakitha's `runRoutineCustom.py` as the reference for simplicity and for the data pipeline. For the weekend run, the
points must be visited in the right order, and condensation must be avoided.

Calibration sources: commit `d4db474` (HEAD on 2026-10-20). `schedule.tsv` was last changed in `d809739`; the sha256
of its bytes is `9f59b5fbbedd238b…` ([v8/README.md](v8/README.md)).

### Must-fix review (2026-10-22)

The review of the first version found five must-fix items. All five are fixed on this branch:

| # | Finding | Fix |
|---|---|---|
| 1 | Holds started when T arrived, so the RH settling of the schedule's window was cut from the holds (pre2, pre3, 11, 22, 23, 24, 26, 30: 99 min of scoreable time) | The transition lasts the TSV window D as the runner does; an RH-only change goes linearly over D; the hold starts at its end ([How a point runs](#how-a-point-runs)) |
| 2 | No T640 protection: only the chamber dew-point rules, which cannot fire below the 24 °C hold threshold | The T640 is read locally over Modbus/TCP every 10 s; the sample-RH HOLD / ABORT, dew point against the box T, fault bit and stale-T640 rules are back ([Condensation guard](#condensation-guard)) |
| 3 | A failed pre-cycle check went to STOP (Ctrl-C), leaving the chamber humid after pre2 | The T640 PM2.5 and chamber RH items are checked by the routine (copied from the runner); then pass / fail is asked for the rest; a failure or no answer runs the guarded SAFE; all logged ([Pre-cycle checks](#pre-cycle-checks)) |
| 4 | MQTT to the UTD broker inside the 10-s control loop (blocking connect, up to 5 s per record) | The control process writes CSV and a local outbox only; `publishV8.py` publishes from its own process ([Logging](#logging)) |
| 5 | Nothing parked the chamber on SIGHUP, SIGKILL, out-of-memory or power loss, and a restart had no state | SIGHUP trapped; atomic state file at every event; systemd unit as the runner's: watchdog, restart with `--resume` (resumes the run, or continues an unfinished SAFE), `OnFailure=` park unit; plus a park-at-boot unit ([State, restarts and the park hook](#state-restarts-and-the-park-hook)) |

### Re-check against the runner (2026-10-22, Calibration `c082131`)

The first round of fixes was written without the runner's source (the local Calibration checkout predated it), so
parts of fixes 1–3 were reconstructed from the TSV's rule text. After the Calibration pull the runner
(`calib/chamber/cycle.py`, `schedule.py`) was read in full and those parts were replaced by copies of it:

| Area | Reconstructed first | Now (as the runner) | Runner source |
|---|---|---|---|
| Window D | Never shorter than the T ramp | Extended only when the ramp needs more than D + 0.5 min (the generator's whole-minute rounding); T set to its target at the end of D. Plan: 24.83 h = the TSV's 1,490 min exactly | `cycle.py:83, 329-346` |
| Humidity while T changes | Dew point spread over D (min / max of T and time progress) | Dew-point trajectory interpolated with T (`dp_trajectory_rh`), target dew point from the row's T and RH | `cycle.py:849, 871-885` |
| RH-only change | Linear in dew point over D | Linear in RH over D | `cycle.py:880-882` |
| Dry warm-ups | Humidity after `humidify_after_min` from T arrival | From arrival = the end of D | `cycle.py:901-911` |
| First step of a run | TSV window or ramp | Its own ramp from the PV at the SAFE rates; an RH-only first step at ≤ 6 %/min (`RH_RATE_MAX`) | `cycle.py:81, 825-830` |
| Pre-cycle checks | Operator answer only | T640 PM2.5 window mean, chamber RH PV condition and the provisional pre2 sample-RH bound checked by the routine; the operator answers for the IPS items | `cycle.py:719-773`, `schedule.py:311-351` |
| HOLD timers | Reset at each point | Kept across points (a condition still true at the next point holds it too) | `cycle.py:813-815` |
| Stale T640 | `>=` 5 min | `>` 5 min, counted from the run start at most | `cycle.py:610-613` |
| SAFE dry-out | Fixed 60 min | Ends early once Td_ch ≤ 5 °C and sample RH ≤ 35 % for 10 min; at 60 min only if dry; never over 90 min | `cycle.py:1012-1033`, `schedule.py:302-303` |
| Watchdog | None | `READY=1` / `WATCHDOG=1` to systemd (`sd_notify`), unit `Type=notify` with `WatchdogSec` | `cycle.py:274-287, 586, 802` |

Two Calibration rules from its findings log were applied as well: the owner's zero-internet directive of
2026-10-21 (the chamber control makes no Influx or internet calls; already the case after fixes 2 and 4) and the
owner's rule that no code deletes a variable-built path (`publishV8.py` no longer deletes old outbox files, and the
operator file is no longer deleted after it is read).

The runner's offline branch (`feat/chamber-offline-7.17`, which reads local sensor rows instead of Influx) has not
been pushed, so `main`'s runner, which reads Influx, is the reference; its rules and numbers are the same.

---

## At a Glance

| Area | Lakitha's `runRoutineCustom.py` | Dr. Lary's runner | `runRoutineV8.py` (this update) |
|---|---|---|---|
| Points | Every T × RH grid combination | `schedule.tsv` v8 in file order | `v8/schedule.tsv` (verbatim copy, sha logged) in file order |
| Temperature change | Set point jumps to the target | Ramped at the row's rate, every 10 s, over the schedule's window D | Ramped at the row's rate, new set point every 60 s; the transition lasts the window D |
| Humidity on ramps | Always ON when reachable | Dew-point trajectory; RH-only change linear over D; dry warm-ups; resume rule | Same (copied) |
| Humidity OFF | Not possible | Yes | Yes (`set_humidity_enabled`) |
| Dry-air purge | Not controlled | Per row | Per row (`set_dry_air_purge`) |
| Soak | ±2 °C / ±2 %RH, then 120 s | Timed or guaranteed (band), 60-min give-up, from the end of D | Same (copied) |
| Dew-point cap | None | Chamber PV, T640 sample RH, T640 box T, tube heater | Chamber PV, T640 sample RH, T640 box T, T640 fault bit (no tube heater, no WIMDA), plus a cap on every RH set point sent |
| Abort rules | None | Abort list and excursion ABORT (chamber, T640, IPS) | Chamber, T640 and stale-T640 rules; pre-cycle T640 / chamber items checked, IPS items answered by the operator |
| Failure handling | Chamber stopped only after a normal end | SAFE dry-out, emergency STOP, watchdog | SAFE dry-out (early end, 90-min limit), emergency STOP, watchdog, park hook after any end of the process |
| Logging | `BTL433ESC001*` via `sensorFinisher` (CSV + MQTT inline) | JSON-lines events file (writes no `BTL433ESC001*` stream) | `BTL433ESC001*` via `sensorFinisher` (CSV inline, MQTT from `publishV8.py`), plus `BTL433ESC001RTNV8` events |
| Size | 53 lines + `Chamber.Routine` | ~2,900 lines | `runRoutineV8.py` 1,698 lines, `publishV8.py` 128, `parkChamberV8.py` 118 |

---

## How a Point Runs

The summary is read and logged every 10 s (`get_and_write_summary(expanded=True)`) in every phase, and every rule
below is checked at every tick, including while the routine waits for the operator.

1. **Transition (window D).** D is the TSV's `expected_arrival_min_after_start` of the row minus the previous row's
   end (its arrival plus its hold). It is extended only when the T ramp at the row's rate needs more than D + 0.5 min
   (printed); otherwise T is set to its target at the end of D, as the runner does. Within D:
   - the T set point ramps from where the chamber is to the row's `T_set_C` at `ramp_rate_C_per_min` (a new set point
     every 60 s);
   - the humidity follows the row (see [Condensation guard](#condensation-guard));
   - the purge follows the row's `dry_air_purge` from the first tick.

   The first point of a run has no D: it lasts its own ramp from the chamber PV at the SAFE rates (1.0 °C/min up,
   0.6 °C/min down), and an RH-only first step at most 6 %/min.
2. **Hold start ("arrival").** At the end of D, with the T set point read back: `RTNCHG` change 10 (*Routine Holding*)
   with `iteration` = the point's position in this run, and `RTNV8` event 2. The row's `check_or_rule` is printed;
   for pre1–pre3 it is the operator checklist.
3. **Soak.**
   - Timed rows (`none(timed)`) hold `hold_min_at_setpoint` from the hold start.
   - Guaranteed rows count hold time only while |T_pv − T_set| ≤ the row's band. If the band has not held long
     enough 60 min after the hold time, the soak is given up: `RTNCHG` change 11 and a printed warning.
4. **Pre-cycle checks** (pre1–pre3 only): see [Pre-cycle checks](#pre-cycle-checks). The next point does not start
   before they pass.
5. **Aerosol feed.** When a row's `aerosol_feed` differs from the previous row's (only pre2 → pre3 in v8), the routine
   asks the operator to set it and answer `go`, while it keeps the previous point's set points and every rule
   running. No answer in 30 min = SAFE. `--no-operator-wait` only prints the message.

After the last point (bake, or 30 with `--skip-bake`) the **stop row** runs: humidity OFF, STOP, read back
`standby`, and a printed "open the door" message.

**Timing.** `--plan` prints the plan with a `ramp` and a `trans` (D) column: **24.83 h** including the pre-cycle and
the bake, the TSV's own 1,490 min from pre1 to the stop row. The first version ran 23.2 h because it started each hold
when T arrived; the 99 min it saved were all taken from the holds.

---

## Condensation Guard

Water condenses when moist air meets a surface colder than its dew point. The surfaces at risk are the sensors and
the sample tube: they lag the air, especially when warming into humid air or cooling while humid. The guard uses the
chamber's T and RH, the T640's sample RH, box temperature, ASC heater duty and fault bit, and the Magnus formulas
copied from Calibration `calib/chamber/psychro.py`.

1. **Dew-point trajectory, RH over the window D** (as the runner). When `ramp_humidity_system` is ON:
   - T and RH change together: every 60-s update sets RH = `dp_trajectory_rh(T_now, T_from, T_target, Td_from,
     Td_target)`, so the dew point moves linearly with the temperature progress and is never ahead of the air
     temperature;
   - an RH-only change (pre-cycle, 1, 5, 11, 23, 24, 26, 29): the RH set point goes linearly from the one in force to
     the row's over D.
   - `Td_from` is the dew point of the RH set point in force, or of the chamber PV if humidity was off; `Td_target` is
     the dew point of the row's T and RH.
2. **Dry warm-ups.** When `ramp_humidity_system` is OFF, humidity stays OFF during the transition and switches ON with
   the row's RH `humidify_after_min` after arrival (the end of D), so the units warm above the coming dew point first
   (points 6, 7, 16, 28, 30). Rows with `humidity_system` OFF (2, 3, 27) stay OFF throughout.
3. **First step / resume rule** (host duty 7). On the first point of a run, including `--start-point` and `--resume`:
   - a rise of ≥ 5 °C from a chamber RH PV ≥ 40 % ramps dry and adds humidity 10 min after T arrives (the
     schedule's longest `humidify_after_min`);
   - a pull-down below 0 °C to a humid target ramps dry and adds humidity when T arrives.
4. **Dew-point cap (23 °C) and the excursion rule** (the `excursion` row; every number is read from its text):
   - No RH set point is ever sent whose dew point at the T set point being sent is above 23 °C. `--plan` checks every
     point and the routine refuses to start if one is above it.
   - **HOLD** (step the RH set point to the RH whose dew point is 22 °C at the current T set point, for the rest of
     the point; never raised again within the point; `RTNV8` event 4 with the rule in `detail`; a condition still
     true when the next point starts holds that point too) when:
     the chamber-PV dew point > 24 °C for 2 min; or the T640 sample RH > 45 % for 5 min while the ASC heater duty is
     ≥ 95 %; or the chamber-PV dew point > T640 box T − 3 °C.
   - **ABORT to SAFE** when: the T640 sample RH > 60 % for 10 min, > 75 % for 2 min or > 60 % for 5 min; the
     chamber-PV dew point > 26 °C for 5 min; the chamber-PV dew point ≥ T640 box T; or the T640 fault bit
     (`WRNS.systemFaultWarning`) is set for 5 min while the sample RH is > 45 %.
   - Not checked: the tube-heater part ("when logged": it is not) and the WIMDA dew point (not read here).
5. **The T640** is read by its own thread every 10 s over Modbus/TCP (`--t640-host`, default `192.168.20.125`, the
   address of `teledyneSensing/firmware/xu4Mqtt/t640Reader.py`; input registers 8 PM2.5, 36 sample RH, 38 box T, 60
   ASC heater duty; discrete input 7 system fault), standard library only, one short connection per read with a 3-s
   timeout. The control loop takes its latest reading and never waits for it.
   - **Stale T640** (the `abort` row): no good reading for 5 min → ABORT to SAFE.
   - No T640 reading within 60 s of the start → the run is refused before anything is sent.
   - `--no-t640` turns the T640 rules off. A person must then watch the T640 sample RH at the points whose dew point
     is ≥ 15 °C (pre2 and 12–21). At each of them the routine prints the written threshold: SAFE now
     (`--operator safe`) if the sample RH is > 75 % for 2 min or > 60 % for 5 min, if the box T is at or below the
     chamber dew point, or if a T640 fault shows with sample RH > 45 %.
6. **Order.** The points run exactly in TSV order. The schedule puts the cold points while the chamber is dry and the
   fog last. Skipped points (by `--start-point`, `--skip-precycle`, `--skip-bake`) are printed.

---

## Pre-cycle Checks

pre1 (zero / LOD blank), pre2 (humid blank) and pre3 (loading check). The routine checks every item it can read,
with the numbers parsed from each row's text (copied from the runner's `_precheck_tick` / `_precheck_end`):

| Check | Checked by the routine | Left to the operator |
|---|---|---|
| pre1 | T640 PM2.5 mean over the last 5 min ≤ 0.3 µg/m³ | IPS blank sd → LOD |
| pre2 | T640 PM2.5 mean ≤ 0.3 µg/m³; chamber RH PV within 80 ± 5 % within 15 min of arrival; provisional: T640 sample RH mean ≤ 40 % (log only, event 18) | — |
| pre3 | T640 PM2.5 mean ≥ 3 µg/m³; chamber RH PV ≤ 20 % within 25 min of the step start | IPS/T640 ratio recorded as the anchor-A reference |

A failure of an automatic item is an ABORT at once (`RTNV8` event 14, `detail` "automatic: …") → SAFE, without a
question. With `--no-t640` the PM2.5 items are not checked and the operator's answer covers them. When the automatic
items pass, the routine asks at the end of the hold:

```text
PRE-CYCLE CHECK pre2: humid blank: T640 PM2.5 <= 0.3 ug/m3 (last 5 min); ...
Checked by the routine: T640 PM2.5 mean 0.08 ug/m3 over 5 min (n 30) OK; ...
Answer here (pass / fail), or from any shell in firmware/xu4Mqtt:
    python3 runRoutineV8.py --operator pass
    python3 runRoutineV8.py --operator fail
No answer within 30 min = SAFE. Any time: --operator safe.
```

- While it waits, the chamber holds the point and every rule keeps running.
- `pass` → `RTNV8` event 13 (with the automatic results in `detail`), next point. pre3's answer gates point 1: the
  cycle does not start before the loading check passes.
- `fail` → event 14, then ABORT → the guarded SAFE routine (dry-out, then STOP), as protocol section 4 and the
  `abort` row require. Ctrl-C is no longer the way to fail a check: it skips the dry-out.
- No answer in 30 min → event 15 and SAFE.
- The answer can be typed in the routine's terminal (when it has one) or sent with `--operator`, which writes
  `v8/state/operator.json`; the routine reads each answer once, within 10 s. Answers older than the question are
  dropped.

---

## Safety

**However the script ends, the chamber is left safe.**

| How it ends | What happens |
|---|---|
| Normal end | Stop row: humidity OFF, STOP, read back `standby`, "open the door" |
| Ctrl-C, SIGTERM (`systemctl stop`) or SIGHUP (closed terminal / dropped SSH without `screen`) | Humidity OFF, then STOP, at once (each tried twice) |
| Abort rule, failed or unanswered pre-cycle check, `--operator safe`, or an unexpected error once in CONSTANT | Simplified SAFE (below) |
| Error before CONSTANT | Humidity OFF, then STOP |
| SIGKILL, out-of-memory kill, interpreter crash, a hang (systemd watchdog, 300 s) | systemd restarts the routine after 15 s with `--resume`: it resumes at the point it was on, or continues SAFE if it died inside an abort / SAFE. When systemd gives up (more than 5 starts in 30 min, or a deliberate failure), `parkChamberV8.py` (`OnFailure=`): humidity OFF, then STOP over the LAN |
| Power loss or hard reset of the host | At the next boot, `v8-park-on-boot.service`: humidity OFF, then STOP |
| The chamber leaves CONSTANT by itself (alarm, water out, panel STOP) | Nothing more is sent: log, print, exit. The interlock wins (the park hook leaves it alone too). |
| The chamber is in program mode at start, or no T640 reading | Refused, nothing is sent |

The park hook needs the host and the LAN. If the host stays down, nothing on the host can park the chamber; the
chamber then holds its last set point until someone stops it at the panel.

**Simplified SAFE** (from the `safe` row):

1. humidity OFF;
2. ramp T to the PV clamped to 22–30 °C (1.0 °C/min up, 0.6 °C/min down);
3. on arrival, humidity ON at 15 % with the purge ON; the dry-out ends once the chamber dew point is ≤ 5 °C and the
   T640 sample RH ≤ 35 % for 10 min, at 60 min if it is dry then, and never later than 90 min (`RTNV8` event 9 says
   which; with `--no-t640` it is never "dry", so 90 min);
4. humidity OFF and STOP, door closed (the next person opens it).

If the chamber cannot be read, or a command is not confirmed, for 5 min during SAFE, the routine sends humidity OFF
and STOP and exits.

**Abort rules** (from the `abort` and `excursion` rows):

- a pre-cycle check failed (automatic item or operator) or not answered;
- no valid chamber summary for 5 min;
- a set point not confirmed by the summary read-back for 5 min (an unconfirmed set point is re-sent at every 60-s
  update);
- the pull-down to −18 °C not reached within 90 min at the −20 °C point;
- T640 data stale for 5 min;
- humidity ON at a humid soak (T ≥ 15 °C, purge OFF, past `humidify_after_min`) with the RH PV more than 10 % below its
  set point for 15 min: the water or steam supply is short (`cycle.py:689-695`);
- the excursion ABORT parts listed in the [Condensation guard](#condensation-guard).

**Flag, no abort:** at a purge-ON soak, an RH PV more than 5 % above its set point for 15 min (the purge or the
compressed air is short): printed and logged once per point as `RTNV8` event 19 (`cycle.py:696-702`).

**Read-back.** After each command the routine reads the summary again and compares the set value or state with what
it sent. `Chamber` has `request_timeout`; the routine uses 10 s, so a hung request cannot freeze the run.

### State, Restarts and the Park Hook

`v8/state/state.json` (git-ignored) is rewritten atomically (temporary file, `fsync`, rename) at every `RTNV8` event,
before the event is logged: run id, pid, host, boot id, schedule sha, point, position, phase, last event and its
detail, outcome (empty while the run is live), whether the routine confirmed its own STOP, and whether it must keep
its hands off.

A new start reads it first and decides as the runner's `_decide` (`cycle.py:1069-1095`):

| Last state | `python3 runRoutineV8.py` | `--resume` (always passed by the systemd unit) |
|---|---|---|
| A live run (same host and boot, pid alive) | Refused | Refused |
| Died or interrupted inside an abort / SAFE | SAFE is continued; the cycle is not restarted | Same (`--resume` / `--start-point` ignored) |
| A finished abort: `safe`, `safe_failed`, `left_constant`, `stop_unconfirmed`, `error, …` | Refused until `--clear-abort "<what was checked>"` | Refused |
| Unfinished: died (killed, crashed; parked or not) or `interrupted`, outside SAFE | Refused unless `--start-point` | Resumes at the point the state names (same schedule sha only), even if `run.env` has a `--start-point` |
| `complete`, `refused`, `error` before CONSTANT, or no state | Starts as asked | Starts as asked (nothing to resume) |

A resumed run starts from the chamber PV with the first-step rule. If it cannot read the chamber at start it aborts to
SAFE (the chamber may be humid at its last set point), as the runner does. A continued SAFE on a chamber that is
already stopped sends nothing ("nothing to dry out").

**Exit codes** (the runner's): 0 complete, 2 refused (cap check or state), 3 SAFE completed, 4 the chamber left
CONSTANT by itself, 5 a failure (SAFE failed, STOP unconfirmed, an error), 130 interrupted. systemd restarts on a crash
and on 5, never on 2, 3, 4 or 130.

`--clear-abort` keeps the previous state and the reason given inside the new run's state.

`parkChamberV8.py` (the `OnFailure=` unit `v8-park.service`, and `v8-park-on-boot.service`) reads the same file. It parks the chamber (humidity OFF, then STOP, each tried twice, read back
`standby`) only when the run has no outcome or ended without a confirmed STOP, and never while the run is alive,
after the chamber left CONSTANT by itself, or after a refused start. It records `died, parked` (or `died, park NOT
confirmed`), the systemd `SERVICE_RESULT` / `EXIT_STATUS`, and the previous outcome.

---

## Logging

All records go through `mSR.sensorFinisher`, like every other stream. In the routine's process MQTT is switched off
(`mintsSensorReader.mqttOn = False`, read at every call) and each record is also appended to a local outbox,
`<dataFolder>/<mac>/v8outbox/YYYY-MM-DD.jsonl` (one JSON line per record, which keeps every value's type).
`publishV8.py` runs as its own process, reads the outbox and publishes each record exactly as `sensorFinisher` would
have (topic `<mac>/<sensorName>`, payload `json.dumps(record)`, through `mintsLatest`'s connection). If the broker is
down it retries from the saved offset; the control loop never waits on the network beyond the chamber and the T640.
Nothing deletes outbox files (the Calibration owner's rule: no code deletes a variable-built path); about 15 MB a
day, cleared by a person like the old CSV files.

| Stream | When | Fields |
|---|---|---|
| `BTL433ESC001STATUS`, `TMPRT`, `HMDTY`, `DAP`, `PRGRM` | Every 10 s (expanded summary) | Unchanged (`Chamber.write_*`) |
| `BTL433ESC001CHNG` | Every command | Unchanged; new change IDs 13 *Humidity System Set*, 14 *Dry Air Purge Set* |
| `BTL433ESC001RTNCHG` | 1 *Routine Started* (iteration 0) at the start; 10 *Routine Holding* at each hold start (iteration 1…N); 11 at a guaranteed-soak give-up; 2 *Routine Ended* at the end | `dateTime`, `changeID`, `changeLabel`, `iteration`, `success` (as `run_routine`) |
| `BTL433ESC001RTNPRGV2` | Once per point, at its transition start | As `run_routine`; humidity OFF → `entryHumidity` −100, `entryHC` 0 |
| `BTL433ESC001RTNV8` (new) | Events only | `dateTime`, `eventID`, `eventLabel`, `point`, `tag`, `temperatureSet`, `humiditySet` (−100 = OFF), `humiditySystem`, `dryAirPurge`, `aerosolFeed`, `holdMin`, `rampRate` (−1 = none), `gsBand` (−1 = timed), `scheduleSha`, `detail` |

`RTNV8` events: 0 run started, 1 transition started, 2 arrived (hold start, end of D), 3 humidity enabled after a dry
warm-up, 4 dew-point hold, 5 guaranteed soak given up, 6 soak ended, 7 aborted, 8 SAFE started, 9 SAFE ended, 10 run
ended, 11 chamber left CONSTANT, 12 emergency stop, 13 / 14 / 15 pre-cycle check passed / failed (automatic or
operator) / unanswered, 16 operator confirmed the feed change, 17 operator requested SAFE, 18 the provisional pre2
sample-RH bound exceeded (log only), 19 purge-ON RH excess flag (log only). `detail` holds the rule that fired, the check results, the answer, the SAFE
dry-out's end or the outcome. The `BTL433ESC001` prefix keeps the stream in the pipeline's
`REF_MEAS_PREFIXES`.

The `iteration` restarts at 1 for every new run, including a `--start-point` / `--resume` restart
(`calib/fit/diagnostics.py` reads it as the step counter).

The summary is expanded on every read. `run_routine` expanded it only at start-up, so `DAP.enabled` (the purge column)
was barely refreshed.

---

## Usage

From `firmware/xu4Mqtt`, like the other routine scripts:

```bash
python3 runRoutineV8.py --plan
```

```bash
python3 runRoutineV8.py --t640-check
```

```bash
python3 runRoutineV8.py
```

| Option | Meaning |
|---|---|
| `--plan` | Print the table of points (ramp, window D, hold minutes, planned start / hold start / end, the clock time if started now, the total) and the dew point of every RH set point. Contacts nothing. Refuses (exit 2) if a dew point is above the cap. |
| `--t640-check` | Read the T640 three times, 10 s apart, and print sample RH, box T, ASC heater duty, fault bit and PM2.5. Contacts nothing else. |
| `--operator pass\|fail\|go\|safe` | Answer the running routine: a pre-cycle check, the feed change, or SAFE now. |
| `--resume` | Resume at the point `v8/state/state.json` names (after `interrupted`, or a death outside SAFE). |
| `--clear-abort "<what was checked>"` | Allow a start after an aborted / SAFE / unconfirmed run. |
| `--start-point <name>` | Start at that point (`pre1`–`pre3`, `1`–`30`, `bake`). |
| `--skip-precycle` | Skip pre1–pre3. |
| `--skip-bake` | Stop after point 30. |
| `--t640-host`, `--t640-port` | T640 Modbus/TCP address (default `192.168.20.125:502`). |
| `--no-t640` | Do not read the T640 (its rules are off; a person watches it, see above). |
| `--chamber-url` | Web Controller base URL (default `http://192.168.20.121`). |
| `--no-operator-wait` | Do not wait for the operator at the aerosol-feed change (the pre-cycle checks are still asked). |
| `--state-dir` | Where `state.json` and `operator.json` live (default `v8/state`). |

Exit codes: see [State, restarts and the park hook](#state-restarts-and-the-park-hook). The last line printed says
whether to `--resume` or to `--clear-abort`.

**Under systemd** (recommended for the weekend: a SIGKILL, out-of-memory kill, crash or hang is then restarted and
resumed, and the chamber is parked if systemd gives up). Paths in the unit
files assume `/home/teamlary/gitHubRepos/btl433EspecChamber` and user `teamlary`; edit them if the XU4 differs.

```bash
sudo cp v8/systemd/runRoutineV8.service v8/systemd/v8-park.service v8/systemd/v8-park-on-boot.service v8/systemd/publishV8.service /etc/systemd/system/
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now publishV8 && sudo systemctl enable v8-park-on-boot
```

```bash
sudo systemctl start runRoutineV8
```

```bash
journalctl -fu runRoutineV8
```

Options go in `v8/state/run.env` (for example `V8_ARGS=--skip-precycle --start-point 1`); `--resume` is always in the
unit's `ExecStart`. Under systemd the routine has no terminal: answer
with `python3 runRoutineV8.py --operator …`. `sudo systemctl stop runRoutineV8` is SIGTERM (humidity OFF, then STOP).
The unit is `Type=notify` with `WatchdogSec=300`, as the runner's: `systemctl start` returns once CONSTANT is reached,
and a routine that stops pinging for 300 s is killed and restarted. `Restart=on-failure` with `RestartSec=15`
restarts it after a crash; `RestartPreventExitStatus=2 3 4 130` keeps deliberate ends ended. `runRoutineV8.service`
is never enabled at boot: a person starts the first run; after a host power loss `v8-park-on-boot.service` parks the
chamber and a person restarts the run (`systemctl start runRoutineV8` resumes it).

Tests (hermetic: simulated chamber, fake clock, fake T640 or a Modbus server on 127.0.0.1, no MQTT, `credentials.yml`
never read):

```bash
python3 -m unittest discover -s tests -v
```

---

## Kept / Simplified / Dropped

| Runner feature | Here | Why |
|---|---|---|
| Points from `schedule.tsv` in order | **Kept** (verbatim copy, sha logged) | One source of truth; the order is physics |
| Ramps at the row's rate; dew-point trajectory; dry warm-ups; resume rule | **Kept** | Condensation |
| Schedule-exact transition window D (extended past D + 0.5 min only); RH-only change linear over D | **Kept** (must-fix 1) | The holds were sized for it |
| T set point every 10-s tick | **Simplified**: every 60 s | Fewer commands; the summary is still read every 10 s |
| Dew-point cap / excursion HOLD | **Kept** except the tube-heater part | Not logged here |
| Excursion ABORT | **Kept** (chamber PV, T640 sample RH, box T, fault bit) | Must-fix 2 |
| Td_ch = the higher of the chamber PV and the WIMDA dew point | **Simplified**: chamber PV only | WIMDA not read here |
| Guaranteed soaks, 60-min give-up | **Kept** | Simple, and part of the protocol |
| First-step RH-only rate limit (6 %/min) | **Kept** | |
| Pre-cycle checks pre1–pre3 | **Kept** for the T640 PM2.5 and chamber RH items; **simplified** for the IPS items (operator answer); fail or no answer → SAFE | No IPS feed here; must-fix 3 |
| Abort list: T640 stale | **Kept** (must-fix 2) | |
| Abort list: IPS/T640 ratio | **Dropped** | Needs the IPS |
| Abort list: humid-soak RH shortfall; purge-excess flag | **Kept** (the flag is printed and logged, not notified) | Chamber data only |
| Abort list: no reading, unconfirmed, pull-down | **Kept** | Chamber data only |
| SAFE dry-out | **Kept** (early end, 90-min limit) | The T640 is read here now |
| Restart that continues an open SAFE, resumes an unfinished run, refuses a finished abort (`_decide`) | **Kept** (from the state file; a finished abort needs `--clear-abort` instead of a new events file) | Must-fix 5 |
| Chamber left CONSTANT → hands off | **Kept** | Interlock wins |
| Command client with retries and back-off (`espec.py`) | **Simplified**: `Chamber` + one read-back; unconfirmed set points re-sent every 60 s | Lakitha's pipeline; the 5-min unconfirmed abort still applies |
| Systemd watchdog, `Restart=on-failure` with `--resume`, `OnFailure=` emergency stop | **Kept** (`OnFailure=` runs `parkChamberV8.py`, which stops only when the state says the chamber was not parked) | Must-fix 5 |
| Influx / JSONL feeds, notifications, `--simulate`, chained cycles | **Dropped** | Not needed for a supervised weekend run |
| Gate G0 start checks | **Dropped** (operator checklist below; `--t640-check`) | Need Influx, NTP and T640 registers |
| Events JSON-lines file | **Replaced** by `BTL433ESC001RTNV8` plus the existing streams | Lakitha's data pipeline |

---

## Changed

| File | Change | Why |
|---|---|---|
| `runRoutineV8.py` | New: the v8 routine | The deliverable |
| `publishV8.py` | New (must-fix 4): publishes the outbox to MQTT from its own process | No network I/O in the control loop |
| `parkChamberV8.py` | New (must-fix 5): humidity OFF and STOP after an end the routine could not handle | SIGKILL, out-of-memory, crash, power loss |
| `v8/systemd/*.service` | New (must-fixes 4, 5): the run unit (watchdog, restart with `--resume`, `OnFailure=`), the park unit, park at boot, the publisher | Must-fixes 4, 5 |
| `v8/.gitignore` | New: `state/` | The state file is runtime data |
| `v8/schedule.tsv`, `v8/README.md`, `v8/.gitattributes` | New: verbatim schedule copy, its provenance and sha256, kept byte for byte | One source of truth |
| `benchTestV8.py` | New: operator-present bench test of humidity ON/OFF and purge ON/OFF, with a cable-pull mode; MQTT through the outbox | Host duty 10 before the first run |
| `tests/` | New: hermetic tests (107) | Section 7 of the task and the must-fix review |
| `mintsXU4/especChamber/chamber.py` | Added `set_humidity_enabled` (CHNG 13), `set_dry_air_purge` (CHNG 14), their two `change_mapping` labels, and the optional `request_timeout` passed to the two `requests` calls | The v8 routine needs humidity OFF, the purge and a timeout; old callers are unchanged (`None` = no timeout) |
| `status.sh` | Also reports `runRoutineV8.py`, `publishV8.py` and the state file | `pgrep -f 'runRoutine.py'` does not match them |
| `README.md` | Short "v8 routine" section | Points here |

## Left Alone on Purpose

| What | Why |
|---|---|
| `mintsSensorReader.py`, `mintsDefinitions.py`, `mintsLatest.py`, MQTT settings | The data pipeline stays as it is; `runRoutineV8.py` switches MQTT off in its own process only (`mSR.mqttOn = False`) |
| Every `write_*` method (stream names, field names, order, types) | Calibration's `build_dataset.py` reads them |
| `write_time_signal_set` writing to `DAP` | Changing it changes a stream the pipeline reads; reported below |
| The existing `set_*` methods, `get_and_write_summary`, `get_available_chamber_index`, `execute_command`'s request and response handling | Pipeline; only the timeout argument was added |
| `credentials.yml` | Never opened, staged or committed; reported below |
| `runRoutine.py`, `runRoutineCustom.py`, `stopChamber.py`, `Chamber.Routine` / `run_routine` | The old grid routines and the manual STOP keep working |
| `teledyneSensing`'s `t640Reader.py` | Read from only (register map, address); it keeps logging the T640 |
| The default chamber URL `http://192.168.20.121` | Lakitha's; `--chamber-url` overrides it |
| Everything in the Calibration repository | Read and copied from only |

## Provenance

Every block in the new and changed files carries one tag: `ORIGINAL (Lakitha)`, `COPIED (Dr. Lary)` or
`ADDED BY CLAUDE`; changes of the must-fix review are marked `v8 must-fix review (2026-10-22)`.
`grep -rn -E "ORIGINAL \(Lakitha\)|COPIED \(Dr. Lary\)|ADDED BY CLAUDE" firmware/` lists them.
Calibration line numbers are at `d4db474` (the transferred repository no longer has that commit; every cited range
was re-checked unchanged at `c082131`, and the blocks copied on 2026-10-22 cite `c082131`); Lakitha's at main
`ccc8ab8`.

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
| `runRoutineV8.py` | Rule-text patterns `grab`, `parse_rules` | Dr. Lary (simplified; T640 patterns by Claude; SAFE early end as `schedule.py:302-303`) | `schedule.py:230-307` |
| `runRoutineV8.py` | `parse_precheck` | Dr. Lary (simplified: a dict, IPS items only noted) | `schedule.py:311-351` at `c082131` |
| `runRoutineV8.py` | `RH_RATE_MAX`, `ROUNDING_MIN`, `transition_min` | Dr. Lary | `cycle.py:81-83, 329-346` at `c082131` |
| `runRoutineV8.py` | `precheck_tick`, `precheck_end` | Dr. Lary (simplified: no IPS items) | `cycle.py:719-773` at `c082131` |
| `runRoutineV8.py` | `soak_rules` (humid-soak RH shortfall, purge-ON RH excess) and their numbers | Dr. Lary (simplified: the flag is logged, not notified) | `cycle.py:685-702`, `schedule.py:284-288` at `c082131` |
| `runRoutineV8.py` | `sd_notify`, the READY / WATCHDOG pings | Dr. Lary | `cycle.py:274-287, 586, 802, 1046` at `c082131` |
| `runRoutineV8.py` | `apply` | Dr. Lary (simplified) | `cycle.py:545-570` |
| `runRoutineV8.py` | `check_rules`, `hold` | Dr. Lary (simplified; per-rule timers by Claude) | `cycle.py:603-609, 615-650, 653-684` |
| `runRoutineV8.py` | `startup` | Dr. Lary (T640 start gate by Claude) | `cycle.py:776-802` |
| `runRoutineV8.py` | `run_point` (transition, window D, resume rule, Td_from/Td_target, soak, give-up) | Dr. Lary (simplified) | `cycle.py:809-936` at `c082131` |
| `runRoutineV8.py` | `stop`, `emergency_stop` | Dr. Lary (simplified) | `cycle.py:210-232, 938-946` |
| `runRoutineV8.py` | `safe`, `safe_guarded` | Dr. Lary (simplified; the dry-out's end as `cycle.py:1012-1033` at `c082131`) | `cycle.py:948-1062` |
| `runRoutineV8.py` | `run` | Dr. Lary (simplified) | `cycle.py:1097-1184` |
| `runRoutineV8.py` | T640 register map in `T640Modbus.read` | teledyneSensing (Lakitha) | `firmware/xu4Mqtt/t640/t640.py`, `t640Reader.py` |
| `runRoutineV8.py` | Settings, `Point`, `load_schedule`, `--plan`, exceptions, `T640Modbus`, `T640Poller`, `StateFile`, `OperatorChannel`, `Outbox`, `install_outbox`, `read`, `confirmed`, `td_pv`, `capped_rh`, `held`, `t640_values`, `check_operator`, `ask`, `loop`, `status`, `log_event` (RTNV8), `save_state`, `feed_change`, `watch_text`, `blocked_reason`, `start_gate`, CLI, signals | Claude | — |
| `publishV8.py` | Whole file | Claude (topic and payload of `mintsLatest.writeMQTTLatest`) | — |
| `parkChamberV8.py` | Credentials, chamber index, `Chamber(...)` | Lakitha | `runRoutineCustom.py:7-27` |
| `parkChamberV8.py` | Everything else | Claude (humidity OFF then STOP as Dr. Lary's `emergency_stop`) | — |
| `benchTestV8.py` | Credentials, chamber index, `Chamber(...)` | Lakitha | `runRoutineCustom.py:7-27` |
| `benchTestV8.py` | Everything else | Claude | — |
| `chamber.py` | Whole file except the blocks below | Lakitha | main `ccc8ab8` |
| `chamber.py` | `request_timeout`, labels 13/14, `set_humidity_enabled`, `set_dry_air_purge` | Claude (payloads from Dr. Lary's `espec.py:10-11, 243-255`) | — |
| `status.sh`, `README.md` | Whole file except the marked block | Lakitha | main `ccc8ab8` |
| `status.sh`, `README.md` | v8 block | Claude | — |
| `v8/schedule.tsv` | Whole file | Dr. Lary (verbatim) | Calibration `Docs/protocol/schedule.tsv` at `d809739` |
| `V8_ROUTINE_UPDATE.md`, `v8/README.md`, `v8/.gitattributes`, `v8/.gitignore`, `v8/systemd/*`, `tests/*` | Whole files | Claude | — |

---

## Bench Test (before the first v8 run)

Operator at the chamber, chamber at lab conditions, door closed:

```bash
python3 benchTestV8.py --i-am-at-the-chamber
```

It starts CONSTANT at the current temperature, switches the humidity system ON / OFF and the purge ON / OFF, reads
each one back, prints PASS or FAIL, and always ends with humidity OFF and STOP. Without `--i-am-at-the-chamber` it
refuses and sends nothing.

**T640 check** (while `t640Reader.py` keeps running on its host, so two Modbus clients at once are tested too):

```bash
python3 runRoutineV8.py --t640-check
```

Three good readings, each within a few seconds, with plausible sample RH and box T. If it fails while
`t640Reader.py` runs and works when it is stopped, the T640 does not take a second Modbus client: report it before
the run.

**Cable-pull check** (shows the timeout and the no-reading abort working):

1. Run `python3 benchTestV8.py --i-am-at-the-chamber --cable-pull`.
2. After 3 valid reads, pull the chamber's network cable.
3. Each failed read must print "NO VALID READING" within about 20 s (10-s connect + 10-s read timeout), never hang.
4. After 3 failed reads, plug the cable back. The reads must become valid again, then the test stops the chamber.
5. In a real run the same outage, if it lasts 5 min, aborts to SAFE; if SAFE cannot reach the chamber for 5 more min,
   the routine tries humidity OFF and STOP and exits. **With the cable out these commands cannot arrive: stop the
   chamber at the panel.**

**Restart and park check** (systemd installed, chamber at lab conditions):

1. `sudo systemctl start runRoutineV8` with `V8_ARGS=--skip-precycle --start-point 1` in `v8/state/run.env`.
2. Once point 1 holds, `sudo systemctl kill -s SIGKILL runRoutineV8`.
3. Within about 15 s `journalctl -fu runRoutineV8` must show the restart and "Resuming at point 1"; the chamber stays
   in CONSTANT.
4. While the restarted run goes on, `sudo systemctl start v8-park`: `journalctl -u v8-park` must say "nothing to do:
   the routine is still running" (the park unit never acts under a live run).
5. `sudo systemctl stop runRoutineV8` (humidity OFF, then STOP; no restart).

---

## Weekend Operator Checklist

Before the start:

- [ ] Water tank filled (distilled water) and pressurised (18 psi), pump switched on.
- [ ] Dry-air purge: air supply on, purge unit plugged in.
- [ ] T640 running; `python3 runRoutineV8.py --t640-check` gives three readings.
- [ ] `v8-park.service` installed; `publishV8.service` and `v8-park-on-boot.service` enabled
      (`systemctl status publishV8 v8-park-on-boot`).
- [ ] `python3 runRoutineV8.py --plan` reviewed: points, total, "at or below the 23 C tube cap".
- [ ] Bench test and restart check passed (first v8 run only).
- [ ] Aerosol feed on **HEPA bypass** for pre1 and pre2.
- [ ] Start with `sudo systemctl start runRoutineV8` (inside `screen` / `tmux` instead, a crash is neither restarted
      nor parked).

During the run:

- [ ] pre1–pre3: check the printed T640 / IPS checklist by hand during each hold, then answer `pass` or `fail`
      (`python3 runRoutineV8.py --operator pass`). A failed check goes to SAFE; do **not** press Ctrl-C for it.
- [ ] At the feed prompt after pre2, switch the aerosol feed to **aerosol** and answer `go`.
- [ ] If the run is started with `--no-t640`: someone watches the T640 sample RH at pre2 and points 12–21 with the
      printed threshold and sends `--operator safe` when it is crossed.
- [ ] Someone checks in overnight (`journalctl -fu runRoutineV8`, `status.sh`, Grafana `BTL433ESC001*`).

After the stop row:

- [ ] Open the chamber door (the routine prints this).
- [ ] After a SAFE end the door stays closed until someone checks the chamber; the next start needs
      `--clear-abort "<what was checked>"`.

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

1. With the T640 rules back, is the remaining simplification acceptable for the weekend run (no WIMDA dew point, no
   tube-heater rule, no IPS/T640 ratio, the pre1 LOD and the pre3 ratio recorded by the operator)?
2. Should gate G0 become a pre-start script (`--plan`, `--t640-check`, plus the NTP checks)?
3. The `DAP` issue (finding 1): new suffix for the time signal, or a pipeline-side filter?
4. The tracked `credentials.yml` (finding 2).
5. The new stream name `BTL433ESC001RTNV8` (now with a `detail` field): acceptable, or another name?
6. `feat/chamber-offline-7.17` (the runner without Influx) is not on `origin`. When it lands, should this routine read
   the same local feed instead of its own Modbus client?
<!-- END ADDED BY CLAUDE -->
