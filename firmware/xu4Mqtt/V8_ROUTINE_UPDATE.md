<!-- ADDED BY CLAUDE (v8 routine update, 2026-10-20; must-fix review, 2026-10-22; shortened 2026-10-23) -->
# v8 Routine Update — What Changed and Why

[`runRoutineV8.py`](runRoutineV8.py) runs the MINTS-AI calibration programme **v8** ([`v8/schedule.tsv`](v8/schedule.tsv))
point by point in CONSTANT mode. It is a simplified copy of Dr. Lary's chamber runner (Calibration
`tools/run_chamber_cycle.py` + `calib/chamber/`, ~2,900 lines). Its structure and data pipeline follow Lakitha's
`runRoutineCustom.py`, so the data reaches Influx as the existing `BTL433ESC001*` streams. It reads the chamber
(Web Controller) and the T640 (Modbus/TCP) on the lab LAN only: no Influx and no internet.

**What the routine does, step by step and for how long, is in [v8Guide.md](v8Guide.md).** This file records how it was
built, what was left out, setup and pre-run checks, and open issues.

- **Request** (Rittik Patra, 2026-10-20): copy the runner and simplify it as far as possible, using
  `runRoutineCustom.py` as the reference. The points must run in order and condensation must be avoided.
- **Sources:** Calibration `d4db474`, with every cited range re-checked unchanged at `c082131`. `schedule.tsv` was last
  changed at `d809739`; its sha256 is `9f59b5fb…` ([v8/README.md](v8/README.md)).

---

## Review History

**Must-fix review (2026-10-22).** All five items are fixed:

| # | Finding | Fix |
|---|---|---|
| 1 | Holds started when T arrived, which cut 99 min of RH settling from the holds | The transition lasts the schedule's window D; the hold starts at its end. Plan = the schedule's 1,490 min exactly. |
| 2 | No T640 protection | The T640 is read locally every 10 s; its HOLD / ABORT, box-T, fault-bit and stale-data rules are back |
| 3 | A failed pre-cycle check went to STOP, leaving the chamber humid | The routine checks the T640 PM2.5 and chamber RH items, then asks pass / fail. A fail or no answer runs SAFE. |
| 4 | MQTT publishing ran inside the 10-s control loop | The routine writes CSV and a local outbox; `publishV8.py` publishes from its own process |
| 5 | Nothing parked the chamber after SIGKILL, out-of-memory or power loss | State file, systemd watchdog, restart with `--resume`, `OnFailure=` park unit and a park-at-boot unit |

**Re-check against the runner (2026-10-22, `c082131`).** Parts of fixes 1–3 had first been reconstructed from the
schedule's rule text. They were replaced with copies of the runner's code for: the window D, the dew-point trajectory,
RH-only changes (linear in RH), dry warm-ups (timed from the end of D), the first step's ramp, the pre-cycle checks,
HOLD timers kept across points, the stale-T640 count, the SAFE dry-out's early end, and the watchdog.

**Calibration owner's rules applied:** zero internet from the chamber control, and no code deletes a variable-built
path. So `publishV8.py` never deletes old outbox files, and the operator answer file is never deleted.

**Bench test (2026-10-23).** After STOP, the controller kept reporting `constant` for a few seconds. STOP is now
confirmed by polling for `standby` for up to 20 s (`wait_standby`).

---

## Kept / Simplified / Dropped

Everything from the runner not listed below is kept as the runner does it: points in schedule order, ramps, the
dew-point trajectory, dry warm-ups, the first-step / resume rule, the 23 °C cap, guaranteed soaks with a 60-min
give-up, the chamber and T640 abort rules, the SAFE dry-out, the restart decision, and the interlock hands-off.

| Runner feature | Here | Why |
|---|---|---|
| T set point every 10-s tick | **Simplified:** every 60 s; the summary is still read every 10 s | Fewer commands |
| Td_ch = max(chamber PV, WIMDA dew point) | **Simplified:** chamber PV only | WIMDA not read here |
| Excursion HOLD, tube-heater part | **Dropped** | The tube heater is not logged |
| Pre-cycle IPS items (pre1 LOD, pre3 anchor-A ratio) | **Simplified:** the operator answers for them | No IPS feed here |
| Abort on IPS/T640 ratio | **Dropped** | Needs the IPS |
| Purge-excess flag notification | **Simplified:** printed and logged only | No notifications |
| Command client with retries (`espec.py`) | **Simplified:** `Chamber` plus one read-back; unconfirmed set points re-sent every 60 s | Lakitha's pipeline |
| Influx / JSONL feeds, notifications, `--simulate`, chained cycles | **Dropped** | Not needed for a supervised run |
| Gate G0 start checks | **Dropped:** the operator checklist and `--t640-check` replace them | Need Influx and NTP |
| Events JSON-lines file | **Replaced:** `BTL433ESC001RTNV8` plus the existing streams | Lakitha's data pipeline |

---

## State, Restarts and the Park Hook

`v8/state/state.json` (git-ignored) is rewritten atomically at every `RTNV8` event. It holds the run id, pid, host,
boot id, schedule sha, point, phase, last event, outcome, whether STOP was confirmed, and whether to keep hands off. A
new start reads it first, deciding as the runner's `_decide` does:

| Last state | `python3 runRoutineV8.py` | `--resume` (always passed by systemd) |
|---|---|---|
| A live run (same host and boot, pid alive) | Refused | Refused |
| Died inside an abort / SAFE | SAFE is continued | Same |
| Finished abort (`safe`, `safe_failed`, `left_constant`, `stop_unconfirmed`, `error, …`) | Refused until `--clear-abort "<what was checked>"` | Refused |
| Died or `interrupted` outside SAFE | Refused unless `--start-point` | Resumes at that point (same schedule sha only) |
| `complete`, `refused`, error before CONSTANT, or none | Starts | Starts |

A resumed run starts from the chamber PV with the first-step rule. If it cannot read the chamber, it aborts to SAFE.

`parkChamberV8.py` runs as the `OnFailure=` unit `v8-park.service` and as `v8-park-on-boot.service`. It sends humidity
OFF, then STOP, but only when the run has no outcome or ended without a confirmed STOP. It never acts under a live run,
after the chamber left CONSTANT by itself, or after a refused start. If the host stays down, nothing can park the
chamber: it holds its last set point until someone stops it at the panel.

**Exit codes:** 0 complete, 2 refused, 3 SAFE completed, 4 the chamber left CONSTANT, 5 failure, 130 interrupted.
systemd restarts on a crash and on 5, never on 2, 3, 4 or 130.

---

## Logging

All records go through `mSR.sensorFinisher`. In the routine's process MQTT is off (`mSR.mqttOn = False`). Each record
is also appended to `<dataFolder>/<mac>/v8outbox/YYYY-MM-DD.jsonl`. `publishV8.py` publishes the outbox with the
topic and payload `sensorFinisher` would use, and resumes from its saved offset if the broker is down. Nothing deletes
outbox files; they grow by about 15 MB a day.

| Stream | When | Fields |
|---|---|---|
| `STATUS`, `TMPRT`, `HMDTY`, `DAP`, `PRGRM` | Every 10 s (expanded summary) | Unchanged |
| `CHNG` | Every command | Unchanged; new IDs 13 *Humidity System Set*, 14 *Dry Air Purge Set* |
| `RTNCHG` | 1 started (iteration 0), 10 holding (iteration 1…N, restarts at 1 on a resume), 11 soak given up, 2 ended | As `run_routine` |
| `RTNPRGV2` | Each transition start | As `run_routine`; humidity OFF → `entryHumidity` −100, `entryHC` 0 |
| `RTNV8` (new) | Events | `dateTime`, `eventID`, `eventLabel`, `point`, `tag`, `temperatureSet`, `humiditySet` (−100 = OFF), `humiditySystem`, `dryAirPurge`, `aerosolFeed`, `holdMin`, `rampRate` (−1 = none), `gsBand` (−1 = timed), `scheduleSha`, `detail` |

All streams carry the `BTL433ESC001` prefix, which keeps them in the pipeline's `REF_MEAS_PREFIXES`.

`RTNV8` event IDs:

| ID | Event | ID | Event |
|---:|---|---:|---|
| 0 | run started | 10 | run ended |
| 1 | transition started | 11 | chamber left CONSTANT |
| 2 | hold start | 12 | emergency stop |
| 3 | humidity ON after a dry warm-up | 13 / 14 / 15 | pre-cycle check passed / failed / unanswered |
| 4 | dew-point HOLD | 16 | feed change confirmed |
| 5 | guaranteed soak given up | 17 | operator requested SAFE |
| 6 | soak ended | 18 | provisional pre2 sample-RH bound exceeded (log only) |
| 7 | aborted | 19 | purge-ON RH excess flag (log only) |
| 8 / 9 | SAFE started / ended | | |

---

## Setup (systemd)

Run it under systemd: a crash, kill or hang is then restarted and resumed, and the chamber is parked if systemd gives
up. The unit files assume `/home/teamlary/gitHubRepos/btl433EspecChamber` and user `teamlary`; edit them if the XU4
differs.

```bash
sudo cp v8/systemd/runRoutineV8.service v8/systemd/v8-park.service v8/systemd/v8-park-on-boot.service v8/systemd/publishV8.service /etc/systemd/system/
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now publishV8 && sudo systemctl enable v8-park-on-boot
```

- Options go in `v8/state/run.env`, for example `V8_ARGS=--skip-precycle --start-point 1`.
- With no terminal, answer prompts with `python3 runRoutineV8.py --operator …`.
- The unit is `Type=notify` with `WatchdogSec=300`, `Restart=on-failure` and `RestartSec=15`. `runRoutineV8.service`
  is never enabled at boot, so a person starts every run.

Run `python3 runRoutineV8.py --help` for all options. Tests are hermetic: a simulated chamber, a fake clock and T640,
no MQTT, and `credentials.yml` is never read. They need `requests`.

```bash
python3 -m unittest discover -s tests -v
```

---

## Bench Test

Run these before the first v8 run, with the chamber at lab conditions and the door closed.

1. **Humidity and purge.** Run `python3 benchTestV8.py --i-am-at-the-chamber`. It starts CONSTANT, switches humidity
   and the purge ON / OFF, reads each back, prints PASS / FAIL, and always ends with humidity OFF and STOP.
2. **T640.** Run `python3 runRoutineV8.py --t640-check` while `t640Reader.py` is running, and expect three good
   readings. If it fails only while `t640Reader.py` runs, the T640 does not accept a second Modbus client: report it.
3. **Cable pull.** Run the bench test with `--cable-pull` and pull the chamber's network cable after 3 valid reads.
   Each failed read must print "NO VALID READING" within about 20 s, never hang. Plug the cable back; the reads must
   recover. **With the cable out, no STOP can arrive: stop the chamber at the panel if needed.**
4. **Restart and park.**
   1. Put `V8_ARGS=--skip-precycle --start-point 1` in `run.env` and run `sudo systemctl start runRoutineV8`.
   2. Once point 1 holds, run `sudo systemctl kill -s SIGKILL runRoutineV8`. Within about 15 s the journal must show
      "Resuming at point 1".
   3. Run `sudo systemctl start v8-park`. It must report "nothing to do: the routine is still running".
   4. Finish with `sudo systemctl stop runRoutineV8`.

---

## Weekend Operator Checklist

Before the start:

- [ ] Water tank filled with distilled water and pressurised to 18 psi, pump on.
- [ ] Dry-air purge supply on, purge unit plugged in.
- [ ] T640 running; `python3 runRoutineV8.py --t640-check` gives three readings.
- [ ] `publishV8` and `v8-park-on-boot` enabled, `v8-park.service` installed.
- [ ] `python3 runRoutineV8.py --plan` reviewed; it ends "at or below the 23 C tube cap".
- [ ] Bench test passed (first v8 run only).
- [ ] Aerosol feed on **HEPA bypass**.
- [ ] Start with `sudo systemctl start runRoutineV8`, not `screen` / `tmux`: outside systemd a crash is neither
      restarted nor parked.

During and after the run, follow the operator timeline in [v8Guide.md](v8Guide.md#when-the-operator-is-needed): the
pre-cycle answers, the feed change, overnight check-ins, and opening the door at the end. Never press Ctrl-C to fail
a check; Ctrl-C skips the dry-out.

---

## Changed Files

| File | Change |
|---|---|
| `runRoutineV8.py` | New: the routine |
| `publishV8.py` | New: publishes the outbox to MQTT (must-fix 4) |
| `parkChamberV8.py` | New: humidity OFF and STOP after an end the routine could not handle (must-fix 5) |
| `benchTestV8.py` | New: operator-present bench test, with a cable-pull mode |
| `v8/schedule.tsv`, `v8/README.md`, `v8/.gitattributes` | New: verbatim schedule copy and its provenance (CRLF kept byte for byte) |
| `v8/systemd/*.service`, `v8/.gitignore` | New: run, park, park-at-boot and publisher units; `state/` ignored |
| `tests/` | New: 107 hermetic tests |
| `v8Guide.md` | New: the operator guide |
| `mintsXU4/especChamber/chamber.py` | Added `set_humidity_enabled` (CHNG 13), `set_dry_air_purge` (CHNG 14) and an optional `request_timeout`. Old callers are unchanged. |
| `status.sh`, `README.md` | v8 block added |

**Left alone on purpose:**
- the data pipeline: `mintsSensorReader.py`, `mintsDefinitions.py`, `mintsLatest.py`, every `write_*` method, and the
  existing `set_*` and summary methods;
- the old routines `runRoutine.py`, `runRoutineCustom.py`, `stopChamber.py` and `run_routine`;
- `credentials.yml`, which was never opened;
- `teledyneSensing`'s `t640Reader.py`;
- the Calibration repository.

## Provenance

Every block in the new and changed files is tagged `ORIGINAL (Lakitha)`, `COPIED (Dr. Lary)` (with its Calibration
file and lines) or `ADDED BY CLAUDE`. List them with:

```bash
grep -rn -E "ORIGINAL \(Lakitha\)|COPIED \(Dr. Lary\)|ADDED BY CLAUDE" firmware/
```

In short:
- **From Dr. Lary's runner**, simplified: the ramp, window, dew-point, soak, pre-check, SAFE, stop, rule-parsing,
  watchdog and run logic (`cycle.py`, `schedule.py`), plus the Magnus formulas, verbatim from `psychro.py`.
- **From Lakitha:** the chamber client set-up, `routine_mapping`, and the `RTNCHG` / `RTNPRGV2` logging bodies. The
  T640 register map comes from `teledyneSensing` `t640.py`.
- **Added by Claude:** the schedule reader, `--plan`, the T640 Modbus client and poller, the state file, operator
  channel, outbox, CLI and signals, and the whole of `publishV8.py`. In `parkChamberV8.py` and `benchTestV8.py`,
  everything except the chamber client set-up.

---

## Findings (reported, not fixed)

1. **The DAP issue: the time signal is written to the purge stream.** `write_time_signal_set` uses `DAP`, so each
   summary writes two `BTL433ESC001DAP` records whose `enabled` field means different things (time signal / purge).
   The pipeline reads `DAP.enabled` as the purge.
   - Proposed fix: give the time signal its own suffix (for example `TMSIG`), or have the pipeline keep only `DAP`
     rows that carry `dapGroup`.
   - Not applied, because it changes a stream the pipeline reads.
2. **`credentials.yml` is tracked in git** despite `*.yml` in `.gitignore`. The repository owner should
   `git rm --cached` it and rotate its secrets.
3. **`Chamber.default_if_empty` uses `is " "`.** This raises a SyntaxWarning, and the field is effectively always −1.
   It is harmless, so it was left alone.

## Open Questions for Dr. Lary

1. Is the remaining simplification acceptable: no WIMDA dew point, no tube-heater rule, no IPS/T640 ratio, and the
   IPS items left to the operator?
2. Should gate G0 become a pre-start script (`--plan`, `--t640-check` and NTP checks)?
3. The DAP issue (finding 1): a new suffix, or a pipeline filter?
4. The tracked `credentials.yml` (finding 2).
5. Is the stream name `BTL433ESC001RTNV8` acceptable?
6. When `feat/chamber-offline-7.17` lands on `origin`, should this routine read the same local feed instead of its
   own Modbus client?
<!-- END ADDED BY CLAUDE -->
