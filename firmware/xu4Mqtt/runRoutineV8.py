"""
runRoutineV8.py - the v8 calibration routine for the ESPEC BTL-433 (v8 routine update, 2026-10-20).

NEW FILE on branch feature/v8-routine-update.

WHAT. Runs the points of v8/schedule.tsv in file order (pre1-pre3, 1-30, bake, then the stop row) in CONSTANT mode.
Per point: a temperature ramp at the row's rate (a new T set point every 60 s), the row's humidity and dry-air purge,
then a timed or guaranteed soak. The chamber summary is read and logged every 10 s. The dew-point guard (dew-point
trajectory on humid ramps, dry warm-ups, the first-step rule, the 23 C cap) keeps water off the sensors and the
sample tube. However the script ends, the chamber is left stopped (or dried out in SAFE, then stopped).

PROVENANCE. A simplified copy of Dr. Lary's chamber runner: Calibration tools/run_chamber_cycle.py and
calib/chamber/cycle.py, psychro.py, schedule.py, espec.py at Calibration commit d4db474 (schedule.tsv last changed at
d809739). Structure, entry point and data pipeline from Lakitha's runRoutineCustom.py and Chamber.Routine.run_routine
(main ccc8ab8). Ramp, dew-point, soak, SAFE and abort logic copied and simplified from cycle.py; Magnus formulas
copied from psychro.py; TSV parsing, the 10-s / 60-s loop, logging glue, console output and the CLI added by Claude.

PIPELINE (called, never modified). mintsXU4.especChamber.chamber.Chamber (get_and_write_summary, set_*,
start_constant_mode, stop_chamber), mintsSensorReader.sensorFinisher (CSV + MQTT), mintsDefinitions.credentials.
Streams: the existing BTL433ESC001 STATUS/TMPRT/HMDTY/DAP/PRGRM/CHNG/RTNCHG/RTNPRGV2 and the new BTL433ESC001RTNV8.

LEFT OUT (table "Kept / simplified / dropped" in V8_ROUTINE_UPDATE.md): every rule that needs T640, IPS or Influx
data (pre-cycle checks, T640 stale, the sample-RH / box-T parts of the excursion rule, the humid-soak RH shortfall,
the IPS/T640 ratio, the purge-excess flag), the schedule-exact transition window D, gate G0, notifications, the
systemd watchdog, --resume from an events log, --simulate and the JSON-lines events file.

Usage (from firmware/xu4Mqtt, like the other routine scripts):
    python3 runRoutineV8.py --plan                 # print the timed plan, contact nothing
    python3 runRoutineV8.py                        # the full run (operator at the chamber for the start)
    python3 runRoutineV8.py --start-point 12       # resume at point 12
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - imports and settings - standard library only, Python 3.8 syntax
import argparse
import hashlib
import math
import os
import re
import signal
import sys
import time
import traceback
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

HERE              = os.path.dirname(os.path.abspath(__file__))
SCHEDULE_FILE     = os.path.join(HERE, "v8", "schedule.tsv")
SENSOR_ID         = "BTL433ESC001RTNV8"  # event stream; the BTL433ESC001 prefix keeps it in build_dataset.py REF_MEAS_PREFIXES
RAMP_UPDATE_S     = 60                   # task 5.2: a new T set point every 60 s (the summary is still read every tick)
REQUEST_TIMEOUT_S = 10                   # calib/chamber/espec.py:49 TIMEOUT_S: a hung request cannot freeze the run
LAB_T_C           = 22.0                 # --plan only: assumed start temperature before pre1 (the pre1 row itself, 22 C)
# END ADDED BY CLAUDE

# ORIGINAL (Lakitha) - runRoutineCustom.py:17 at main ccc8ab8
url   = "http://192.168.20.121"
# v8 routine update: LEFT ALONE - the default chamber URL is Lakitha's - --chamber-url overrides it
# v8 routine update: LEFT ALONE - stopChamber.py - still the manual STOP; this routine stops the chamber itself however it ends

# COPIED (Dr. Lary) - calib/chamber/cycle.py:78-80 at Calibration d4db474
GS_GIVE_UP_MIN      = 60.0   # section 5.2: a guaranteed soak whose band has not held 60 min after its hold time is given up
RESUME_RISE_C       = 5.0    # section 13.1 duty 7: a first / resumed rise of >= 5 C ...
RESUME_RISE_FROM_RH = 40.0   # ... from >= 40 % RH runs with the humidity system OFF and waits before steam

# COPIED (Dr. Lary) - calib/chamber/espec.py:47-48 at Calibration d4db474
RH_RANGE = [10, 95]          # chamber.py set_humidity_value payload
SET_TOL  = 0.051             # set points are sent rounded to 0.1; a read-back within this counts as confirmed


# COPIED (Dr. Lary) - calib/chamber/psychro.py:15-37 at Calibration d4db474 (verbatim)
A, B, C = 6.112, 17.62, 243.12


def es_hpa(t):
    return A * math.exp(B * t / (C + t))


def dew_point(t, rh):
    if rh <= 0:
        raise ValueError(f"dew point of RH {rh} is undefined")
    g = math.log(rh / 100.0) + B * t / (C + t)
    return C * g / (B - g)


def rh_for_dew(td, t):
    """RH (%) at air temperature ``t`` whose dew point is ``td`` (capped at 100)."""
    return min(100.0, 100.0 * es_hpa(td) / es_hpa(t))


def dp_trajectory_rh(T, t0, T1, td0, td1):
    """tools/make_chamber_schedule.dp_trajectory_rh: f = (T - t0) / (T1 - t0) clipped to [0, 1]."""
    f = 1.0 if T1 == t0 else min(1.0, max(0.0, (T - t0) / (T1 - t0)))
    return min(100.0, 100.0 * es_hpa(td0 + (td1 - td0) * f) / es_hpa(T))


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - schedule.tsv reader - one source of truth, no point retyped in Python
# v8 routine update: SIMPLIFIED - the runner validates every column (calib/chamber/schedule.py:354-480); here only the 14 columns of task 5.1 are read - the file is the verbatim, sha-logged copy
class Point:
    """One point row of schedule.tsv (pre1-pre3, 1-30, bake)."""

    def __init__(self, r):
        onoff = {"ON": True, "OFF": False}
        self.name               = r["point"]
        self.is_pre             = self.name.startswith("pre")
        self.t_set              = float(r["T_set_C"])
        self.rh_set             = None if r["RH_set_pct_or_OFF"] == "OFF" else float(r["RH_set_pct_or_OFF"])
        self.hold_min           = float(r["hold_min_at_setpoint"])
        self.ramp_rate          = float(r["ramp_rate_C_per_min"]) if r["ramp_rate_C_per_min"] else None
        self.ramp_humidity      = onoff[r["ramp_humidity_system"]]
        self.humidify_after_min = float(r["humidify_after_min"])
        self.humidity_on        = onoff[r["humidity_system"]]
        self.purge              = onoff[r["dry_air_purge"]]
        self.aerosol_feed       = r["aerosol_feed"]
        band                    = r["guaranteed_soak_T_band_C"]
        self.gs_band            = None if band == "none(timed)" else float(band)
        self.dew_point          = float(r["dew_point_C"]) if r["dew_point_C"] else None
        self.tag                = r["tag"]
        self.check              = r["check_or_rule"]


def load_schedule(path):
    """(points, stop row, rule numbers, sha256 of the file bytes)."""
    with open(path, "rb") as f:
        raw = f.read()
    lines = raw.decode("utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:] if line.strip()]
    names = [r["point"] for r in rows]
    by = dict(zip(names, rows))
    points = [Point(r) for r in rows[:names.index("bake") + 1]]
    rules = parse_rules(by)
    rules["max_humidify_after"] = max(p.humidify_after_min for p in points)  # cycle.py:831 (schedule.max_humidify_after)
    return points, by["stop"], rules, hashlib.sha256(raw).hexdigest()
# END ADDED BY CLAUDE


# COPIED (Dr. Lary) - calib/chamber/schedule.py:230-307 at Calibration d4db474 (the patterns of _grab / parse_excursion / parse_abort / parse_safe)
# v8 routine update: SIMPLIFIED - the runner reads every number of the three rule rows; here only the chamber-only ones this routine enforces
NUM = r"(-?[0-9.]+)"


def grab(pattern, text):
    m = re.search(pattern, text)
    if m is None:
        raise ValueError(f"schedule rule text changed: /{pattern}/ not found")
    return [float(x) for x in m.groups()]


def parse_rules(by):
    ex, ab, sf = (by[k]["check_or_rule"] for k in ("excursion", "abort", "safe"))
    r = {"cap": float(by["excursion"]["dew_point_C"])}                          # excursion row, dew_point_C: 23 C
    (r["tick_s"],) = grab(r"every " + NUM + r"-s tick", ex)                       # 10 s
    r["hold_over"], r["hold_min"] = grab(r"HOLD if Td_ch > cap \(-?[0-9.]+ C\) \+ " + NUM + r" C for " + NUM + r" min", ex)
    (r["hold_below"],) = grab(r"dew point is cap - " + NUM + r" C at the current T set point", ex)
    r["abort_over"], r["abort_min"] = grab(r"or Td_ch > cap \+ " + NUM + r" C for " + NUM + r" min", ex)    # 3 C, 5 min
    r["pulldown_T"], r["pulldown_min"] = grab(r"pull-down to " + NUM + r" C > " + NUM + r" min", ab)   # -18 C, 90 min
    (r["no_reading_min"],) = grab(r"no valid chamber reading for " + NUM + r" min", ab)               # 5 min
    (r["unconfirmed_min"],) = grab(r"a set point unconfirmed for " + NUM + r" min", ab)               # 5 min
    r["safe_lo"], r["safe_hi"], r["safe_up"], r["safe_down"] = grab(
        r"the PV clamped to " + NUM + r"-" + NUM + r" C, ramped at " + NUM + r" C/min up / " + NUM + r" C/min down", sf)
    r["safe_rh"], r["safe_dry_min"] = grab(r"on arrival humidity ON at " + NUM + r" % with the dry-air purge ON for "
                                           + NUM + r" min", sf)                                     # 15 %, 60 min
    return r


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - --plan: timed plan, dew point of every RH set point, cap check
def hm(minutes):
    return "%d:%02d" % divmod(int(round(minutes)), 60)


def plan_rows(points, t_from0, rules):
    """Per point: (ramp_min, start_min, arrival_min, end_min). The first ramp uses the SAFE rates by direction (cycle.py:826)."""
    rows, clock, t_prev = [], 0.0, t_from0
    for k, p in enumerate(points):
        dT = p.t_set - t_prev
        rate = p.ramp_rate if k else (rules["safe_up"] if dT > 0 else rules["safe_down"])
        ramp = abs(dT) / rate if dT else 0.0
        rows.append((ramp, clock, clock + ramp, clock + ramp + p.hold_min))
        clock, t_prev = clock + ramp + p.hold_min, p.t_set
    return rows


def over_cap(points, cap):
    return [p.name for p in points if p.rh_set is not None and dew_point(p.t_set, p.rh_set) > cap]


def print_plan(points, t_from0, rules, sha, stop_row, path=SCHEDULE_FILE):
    t0 = datetime.now()
    print(f"schedule {path}  sha256 {sha}  dew-point cap {rules['cap']:g} C")
    print(f"{'pos':>3} {'point':>5} {'T':>5} {'RH':>4} {'Td':>5} {'ramp':>5} {'hold':>4} {'start':>6} {'arrive':>6} "
          f"{'end':>6} {'clock':>5}  notes")
    rows = plan_rows(points, t_from0, rules)
    for k, (p, (ramp, start, arrive, end)) in enumerate(zip(points, rows), start=1):
        td = "" if p.rh_set is None else "%.1f" % dew_point(p.t_set, p.rh_set)
        notes = ["timed" if p.gs_band is None else "gs +-%g" % p.gs_band, "purge" if p.purge else "",
                 "dry warm-up" if p.rh_set is not None and not p.ramp_humidity else "", p.aerosol_feed, p.tag]
        print(f"{k:>3} {p.name:>5} {p.t_set:>5g} {'OFF' if p.rh_set is None else '%g' % p.rh_set:>4} {td:>5} "
              f"{ramp:>5.1f} {p.hold_min:>4g} {hm(start):>6} {hm(arrive):>6} {hm(end):>6} "
              f"{(t0 + timedelta(minutes=start)).strftime('%H:%M'):>5}  {', '.join(n for n in notes if n)}")
    total = rows[-1][3] if rows else 0.0
    print(f"  STOP at {hm(total)} ({(t0 + timedelta(minutes=total)).strftime('%a %H:%M')} if started now): "
          f"{stop_row['check_or_rule']}")
    print(f"  Total {total / 60:.2f} h ({total:.0f} min). Guaranteed soaks (gs) add the PV lag; the first ramp "
          f"starts from the chamber PV (assumed {t_from0:g} C here).")
    bad = over_cap(points, rules["cap"])
    if bad:
        print(f"  REFUSED: the dew point of points {', '.join(bad)} is above the {rules['cap']:g} C tube cap")
    else:
        print(f"  Every RH set point has its dew point at or below the {rules['cap']:g} C tube cap.")
    return not bad
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - exit paths of the run (names follow cycle.py:99-118)
class Abort(Exception): pass          # a rule sends the run to SAFE
class LeftConstant(Exception): pass   # the chamber left CONSTANT by itself (alarm, water out, panel STOP): the interlock wins
class SafeFailed(Exception): pass     # SAFE could not read or command the chamber for the abort row's limit
class RunRefused(Exception): pass     # the chamber is in a mode this routine does not take over (a panel programme)


def differs(value, target):
    try:
        return abs(float(value) - float(target)) > SET_TOL
    except (TypeError, ValueError):
        return True


def banner(message):
    print()
    print("#" * 78)
    print(f"#  {message}")
    print("#" * 78)
    print()
# END ADDED BY CLAUDE


class V8Routine:
    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - routine state - one object per run, so iterations restart at 1
    event_mapping = {
        0: "Run Started", 1: "Transition Started", 2: "Arrived", 3: "Humidity Enabled After Dry Warm-up",
        4: "Dew-Point Hold", 5: "Guaranteed Soak Given Up", 6: "Soak Ended", 7: "Aborted", 8: "SAFE Started",
        9: "SAFE Ended", 10: "Run Ended", 11: "Chamber Left CONSTANT", 12: "Emergency Stop",
    }

    def __init__(self, chamber, mSR, points, rules, sha, t_from0=LAB_T_C, operator_wait=True):
        self.c, self.mSR, self.points, self.r, self.sha = chamber, mSR, points, rules, sha
        self.operator_wait = operator_wait
        self.tick_s = rules["tick_s"]
        self.minutes = [ramp + p.hold_min for p, (ramp, _, _, _) in zip(points, plan_rows(points, t_from0, rules))]
        self.point, self.position, self.phase = points[0], 0, "start"
        self.sent, self.last_want, self.read_ok = {}, None, False
        self.expect_constant = False
        self.last_valid = self.run_start = self.step_start = time.time()
        self.unconfirmed_since = self.hold_since = self.hold_rh = self.abort_since = None
        self.hold_noted = self.pulldown_done = False
    # END ADDED BY CLAUDE

    # ORIGINAL (Lakitha) - chamber.py:483-489 (Routine.routine_mapping) at main ccc8ab8
    routine_mapping = {
            0: "Routine Initiated",
            1: "Routine Started",
            2: "Routine Ended",
            10: "Routine Holding",
            11: "Routine Holding – Waypoint Unreached",
        }

    # ORIGINAL (Lakitha) - chamber.py:891-903 (run_routine's RTNCHG record) at main ccc8ab8; the def line and its parameters ADDED BY CLAUDE (one helper instead of inline copies)
    def log_rtnchg(self, change_id, iteration, success=1):
        dateTime          = datetime.now(timezone.utc)
        sensorIDPost      = "RTNCHG"

        # Log the change
        sensorDictionary = OrderedDict([
            ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("changeID"     , change_id),
            ("changeLabel"  , self.routine_mapping.get(change_id)),
            ("iteration"    , iteration),
            ("success"      , success),
            ])

        self.mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

    # ORIGINAL (Lakitha) - chamber.py:833-848 (run_routine's RTNPRGV2 record) at main ccc8ab8; the def line and the OFF values (-100 / 0, as V7) ADDED BY CLAUDE
    def log_rtnprg(self, p):
        dateTime          = datetime.now(timezone.utc)
        sensorIDPost      = "RTNPRGV2"
        routine_length    = len(self.points)

        # Log the change
        sensorDictionary = OrderedDict([
            ("dateTime", str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("rotuingPercentage" , 100*(self.position/routine_length)),
            ("rotuingIteration"  , self.position),
            ("rotuingLength"     , routine_length),
            ("entryTemperature"  , p.t_set),
            ("entryHumidity"     , -100 if p.rh_set is None else p.rh_set),
            ("entryHC"           , 0 if p.rh_set is None else 1),
            ("success"           , 1),
            ])

        self.mSR.sensorFinisher(dateTime, "BTL433ESC001" + sensorIDPost, sensorDictionary)

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - BTL433ESC001RTNV8 event record (events only, never every tick; layout follows V7's log_event)
    def log_event(self, event_id, p=None):
        p = p or self.point
        dateTime = datetime.now(timezone.utc)
        sensorDictionary = OrderedDict([
            ("dateTime"       , str(dateTime.strftime('%Y-%m-%d %H:%M:%S.%f'))),
            ("eventID"        , event_id),
            ("eventLabel"     , self.event_mapping.get(event_id)),
            ("point"          , p.name),
            ("tag"            , p.tag),
            ("temperatureSet" , float(p.t_set)),
            ("humiditySet"    , -100.0 if p.rh_set is None else float(p.rh_set)),
            ("humiditySystem" , int(p.humidity_on)),
            ("dryAirPurge"    , int(p.purge)),
            ("aerosolFeed"    , str(p.aerosol_feed)),
            ("holdMin"        , float(p.hold_min)),
            ("rampRate"       , -1.0 if p.ramp_rate is None else float(p.ramp_rate)),
            ("gsBand"         , -1.0 if p.gs_band is None else float(p.gs_band)),
            ("scheduleSha"    , self.sha),
        ])
        self.mSR.sensorFinisher(dateTime, SENSOR_ID, sensorDictionary)
    # END ADDED BY CLAUDE

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - one 10-s read through the existing pipeline, with the read-back comparison
    def read(self):
        """Read and log the chamber summary; True for a valid reading."""
        # v8 routine update (2026-10-20): CHANGED - expanded=True on every read - run_routine expands only at start-up, so DAP.enabled (the purge column) was barely refreshed
        try:
            self.c.get_and_write_summary(expanded=True)
            valid = bool(self.c.validity)
        except Exception as e:      # a summary without the expected keys: counts as no reading
            print(f"Chamber summary unreadable: {type(e).__name__}: {e}")
            valid = False
        now, self.read_ok = time.time(), valid
        if valid:
            self.last_valid = now
            if self.expect_constant and self.c.operationLabel != "constant":
                raise LeftConstant(f"the chamber reports operation {self.c.operationLabel!r}")
            if self.confirmed():
                self.unconfirmed_since = None
            elif self.unconfirmed_since is None:
                self.unconfirmed_since = now
        return valid

    def confirmed(self):
        """Every set value / state last sent is what the summary reads back (the runner's "confirmed", espec.py:220-227)."""
        c, s = self.c, self.sent
        if "T" in s and differs(c.temperature_set_value, s["T"]):
            return False
        if s.get("humidity") is False and c.humidity_enable != 0:
            return False
        if s.get("humidity") is True and (c.humidity_enable != 1 or differs(c.humidity_set_value, s["RH"])):
            return False
        return "purge" not in s or c.dap_enable == int(s["purge"])

    def td_pv(self):
        """Dew point of the chamber PV (None without an RH PV)."""
        t, rh = self.c.temperature_process_value, self.c.humidity_process_value
        if t is None or rh is None or rh <= 0:
            return None
        return dew_point(t, min(rh, 100.0))
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:545-570 (_apply) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - the runner's client confirms each command with its own retried read-back (espec.py:220-227); here one summary read after the commands, and an unconfirmed set point is re-sent at the next 60-s update - the abort row's 5-min "unconfirmed" limit still applies
    def apply(self, want):
        """Send what differs between ``want`` (T, humidity, RH, purge; absent = leave) and the read-back state."""
        c, sent, n = self.c, {}, 0
        self.last_want = want
        if want.get("humidity") is False:
            sent["humidity"] = False
            if c.humidity_enable != 0:
                c.set_humidity_enabled(False)
                n += 1
        if want.get("T") is not None:
            sent["T"] = t = round(want["T"], 1)
            if differs(c.temperature_set_value, t):
                c.set_temperature_value(t)
                n += 1
        if want.get("humidity") is True:
            rh = self.capped_rh(want["RH"], sent.get("T", c.temperature_set_value))
            sent.update(humidity=True, RH=rh)
            if c.humidity_enable != 1 or differs(c.humidity_set_value, rh):
                c.set_humidity_value(rh)
                n += 1
        if want.get("purge") is not None:
            sent["purge"] = bool(want["purge"])
            if c.dap_enable != int(want["purge"]):
                c.set_dry_air_purge(bool(want["purge"]))
                n += 1
        self.sent = sent
        if n:
            self.read()

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - the dew-point cap on every RH set point sent (task 5.3.4; cap from the excursion row)
    def capped_rh(self, rh, t_set):
        rh = min(max(rh, RH_RANGE[0]), RH_RANGE[1])
        if self.hold_rh is not None:
            rh = min(rh, self.hold_rh)
        cap_rh = math.floor(rh_for_dew(self.r["cap"], float(t_set)) * 10.0) / 10.0
        return round(min(rh, cap_rh), 1)
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:603-609 (no reading, unconfirmed), 626 + 631-634 (Td ABORT), 637-639 + 653-672 (HOLD), 679-684 (pull-down) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - runner's excursion rule also HOLDs / ABORTs on t640_sample_RH, t640_box_T, the tube heater and the T640 fault bit (cycle.py:615-650); here only the two chamber-PV dew-point parts (HOLD above cap + 1 C, ABORT above cap + 3 C) - those feeds come from Influx, which this routine does not read
    def check_rules(self, valid, now):
        r = self.r
        if now - self.last_valid >= r["no_reading_min"] * 60.0:
            raise Abort(f"no valid chamber reading for {r['no_reading_min']:g} min")
        if self.unconfirmed_since is not None and now - self.unconfirmed_since >= r["unconfirmed_min"] * 60.0:
            raise Abort(f"a set point unconfirmed for {r['unconfirmed_min']:g} min (sent {self.sent})")
        p = self.point
        if p.t_set <= r["pulldown_T"] and not self.pulldown_done:
            if valid and self.c.temperature_process_value is not None and self.c.temperature_process_value <= r["pulldown_T"]:
                self.pulldown_done = True
            elif now - self.step_start > r["pulldown_min"] * 60.0:
                raise Abort(f"pull-down to {r['pulldown_T']:g} C > {r['pulldown_min']:g} min")
        td = self.td_pv() if valid else None
        if td is None or td <= r["cap"] + r["abort_over"]:
            self.abort_since = None
        elif self.abort_since is None:
            self.abort_since = now
        elif now - self.abort_since >= r["abort_min"] * 60.0:
            raise Abort(f"dew-point excursion ABORT: chamber dew point {td:.1f} C > {r['cap'] + r['abort_over']:g} C "
                        f"for {r['abort_min']:g} min")
        if td is None or td <= r["cap"] + r["hold_over"]:
            self.hold_since = None
        elif self.hold_since is None:
            self.hold_since = now
        elif now - self.hold_since >= r["hold_min"] * 60.0:
            self.hold(td)

    def hold(self, td):
        """Step the RH set point back to the RH whose dew point is cap - 1 C; never re-raised within the point."""
        want = self.last_want or {}
        t_set = self.sent.get("T", self.c.temperature_set_value)
        if want.get("humidity") is not True or t_set is None:
            if not self.hold_noted:
                self.hold_noted = True
                print(f"HOLD at point {self.point.name}: chamber dew point {td:.1f} C, humidity OFF, nothing to step back")
            return
        target = min(max(rh_for_dew(self.r["cap"] - self.r["hold_below"], t_set), RH_RANGE[0]), RH_RANGE[1])
        if self.hold_rh is not None and target >= self.hold_rh - 1e-9:
            return
        self.hold_rh = target if self.hold_rh is None else min(self.hold_rh, target)
        banner(f"DEW-POINT HOLD at point {self.point.name}: chamber dew point {td:.1f} C > "
               f"{self.r['cap'] + self.r['hold_over']:g} C for {self.r['hold_min']:g} min; RH set point -> "
               f"{self.hold_rh:.1f} % for the rest of the point")
        self.log_event(4)
        self.apply(want)

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - the tick loop: summary every 10 s, set points every 60 s (and at once when humidity or purge must switch)
    def loop(self, want_fn, done_fn, rules):
        last_update = None
        while True:
            now = time.time()
            valid = self.read()
            rules(valid, now)
            want = want_fn(now)
            switch = self.last_want is None or any(want.get(k) != self.last_want.get(k) for k in ("humidity", "purge"))
            if valid and (last_update is None or switch or now - last_update >= RAMP_UPDATE_S):
                self.apply(want)
                last_update = now
            self.status(valid, now)
            if done_fn(now, valid):
                return
            time.sleep(max(0.0, now + self.tick_s - time.time()))

    def status(self, valid, now):
        c, k = self.c, self.position
        v = lambda name: getattr(c, name, None)   # noqa: E731 - attributes exist only after a valid summary
        left = sum(self.minutes[k:]) + max(0.0, self.minutes[k - 1] - (now - self.step_start) / 60.0) if k else 0.0
        hum = "OFF" if v("humidity_enable") == 0 else f"{v('humidity_set_value')}"
        print(f"Point {self.point.name} ({k}/{len(self.points)}, {self.phase}) | T set {v('temperature_set_value')} -> "
              f"{self.point.t_set:g} (PV {v('temperature_process_value')}) | RH set {hum} (PV {v('humidity_process_value')}) | "
              f"purge {'ON' if v('dap_enable') == 1 else 'OFF'} | point {hm((now - self.step_start) / 60.0)} | "
              f"run {hm((now - self.run_start) / 60.0)}, about {hm(left)} left"
              + ("" if valid else " | NO VALID READING"))
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:776-802 (_startup) at Calibration d4db474
    def startup(self):
        if not self.read():
            raise RuntimeError("no valid chamber summary at start")
        op = self.c.operationLabel
        if op == "constant":
            print("The chamber is already in CONSTANT mode: taking it over without restarting it")
        elif op == "standby":
            self.apply({"T": self.c.temperature_process_value, "humidity": False})
            self.c.start_constant_mode()
            if not self.read() or self.c.operationLabel != "constant":
                raise RuntimeError("CONSTANT mode not confirmed by the summary read back")
        else:
            raise RunRefused(f"the chamber is in {op!r} mode (a panel programme?); stop it before starting this routine")
        self.expect_constant = True

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:809-936 (_run_point) at Calibration d4db474
    def run_point(self, p, prev, first):
        c, r = self.c, self.r
        self.point, self.hold_rh, self.hold_since, self.hold_noted = p, None, None, False
        self.step_start, self.pulldown_done = time.time(), False
        t_pv = c.temperature_process_value
        t_from = p.t_set if t_pv is None else (t_pv if first else prev.t_set)
        if not first and differs(c.temperature_set_value, prev.t_set) and c.temperature_set_value is not None:
            t_from = c.temperature_set_value    # the previous step ended elsewhere (a confirmed set point is the truth)
        dT = p.t_set - t_from
        ramp_h, wait = p.ramp_humidity, p.humidify_after_min
        rate = p.ramp_rate
        if first or rate is None:
            rate = r["safe_up"] if dT > 0 else r["safe_down"]
        if first:     # host duty 7: dry warm-up / dry pull-down from the actual start (cycle.py:830-837)
            rh_pv = c.humidity_process_value
            if dT >= RESUME_RISE_C and rh_pv is not None and rh_pv >= RESUME_RISE_FROM_RH and p.rh_set is not None:
                ramp_h, wait = False, max(wait, r["max_humidify_after"])
            if dT < 0 and p.t_set < 0 and p.rh_set is not None:
                ramp_h, wait = False, 0.0
            if (ramp_h, wait) != (p.ramp_humidity, p.humidify_after_min):
                print(f"First-step rule (host duty 7): point {p.name} ramps with humidity OFF, humidity after {wait:g} min")
        humid_on = p.humidity_on and p.rh_set is not None
        if self.sent.get("humidity") is True and c.humidity_enable == 1 and c.humidity_set_value:
            td0 = dew_point(t_from, c.humidity_set_value)       # the RH set point in force
        else:
            td0 = self.td_pv()                                  # humidity was off: the chamber PV
        td1 = p.dew_point if p.dew_point is not None else (dew_point(p.t_set, p.rh_set) if humid_on else None)
        if humid_on and ramp_h and dT != 0 and td0 is None:
            td0 = td1
        # v8 routine update: SIMPLIFIED - the aerosol feed is manual in the runner too (cycle.py:861-862 logs it); here the operator is told and, once at the start, waited for
        if prev is not None and p.aerosol_feed != prev.aerosol_feed:
            self.feed_change(prev, p)
        print("-" * 78)
        print(f"Point {p.name} ({self.position}/{len(self.points)}, {p.tag}): TRANSITION {t_from:g} -> {p.t_set:g} C at "
              f"{rate:g} C/min, RH {'OFF' if p.rh_set is None else '%g %%' % p.rh_set}, humidity during the ramp "
              f"{'ON (dew-point trajectory)' if humid_on and ramp_h else 'OFF'}, purge {'ON' if p.purge else 'OFF'}, "
              f"aerosol feed {p.aerosol_feed}")
        self.log_rtnprg(p)
        self.log_event(1, p)

        # v8 routine update: SIMPLIFIED - runner's transition lasts the schedule's window D (cycle.py:840, 853-854; transition_minutes at 334-346); here Lakitha-style "ramp until T arrives": the ramp time |dT| / rate, so a point can arrive up to a few minutes before its TSV expected_arrival - holds are unchanged, --plan prints the real timeline
        # v8 routine update: SIMPLIFIED - runner sends the ramping T set point every 10-s tick (cycle.py:865-869) and spreads an RH-only change over D (cycle.py:880-883); here a new T set point every 60 s and an RH-only change at once - the controller ramps RH itself and the air is already at T, so nothing is colder than the new dew point
        t0, sign = time.time(), (1.0 if dT > 0 else -1.0)
        dur_s = abs(dT) / rate * 60.0 if dT else 0.0
        self.phase = "transition"

        def want_transition(now):
            e = now - t0
            T = p.t_set if e >= dur_s else t_from + sign * rate * e / 60.0
            w = {"T": T, "purge": p.purge}
            if not humid_on or not ramp_h:
                w["humidity"] = False                           # dry warm-up / humidity-OFF row
            elif dT != 0:
                w.update(humidity=True, RH=dp_trajectory_rh(T, t_from, p.t_set, td0, td1))
            else:
                w.update(humidity=True, RH=p.rh_set)
            return w

        self.loop(want_transition,
                  lambda now, valid: now - t0 >= dur_s and valid and not differs(c.temperature_set_value, p.t_set),
                  self.check_rules)

        t_arr, hold_s = time.time(), p.hold_min * 60.0
        self.phase = "soak"
        self.log_rtnchg(10, self.position)
        self.log_event(2, p)
        if p.is_pre:
            # v8 routine update: SIMPLIFIED - runner checks pre1-pre3 against T640 / IPS data (cycle.py:719-774) and aborts on a failure; here a timed hold and a printed checklist - those checks need Influx
            banner(f"OPERATOR CHECKLIST for {p.name} (NOT checked by this routine): {p.check}")
        elif p.check:
            print(f"Operator note for point {p.name}: {p.check}")
        gs = {"acc": 0.0, "last": None, "humid": False}

        def want_soak(now):
            w = {"T": p.t_set, "purge": p.purge}
            if humid_on and (ramp_h or now - t_arr >= wait * 60.0):
                w.update(humidity=True, RH=p.rh_set)
                if not ramp_h and not gs["humid"]:
                    gs["humid"] = True
                    print(f"Point {p.name}: dry warm-up done, humidity ON at {p.rh_set:g} % "
                          f"{(now - t_arr) / 60.0:.1f} min after arrival")
                    self.log_event(3, p)
            else:
                w["humidity"] = False
            return w

        def done_soak(now, valid):
            if p.gs_band is None:
                return now - t_arr >= hold_s
            t_pv = c.temperature_process_value
            if gs["last"] is not None and valid and t_pv is not None and abs(t_pv - p.t_set) <= p.gs_band:
                gs["acc"] += now - gs["last"]
            gs["last"] = now
            if gs["acc"] >= hold_s:
                return True
            if now - t_arr >= hold_s + GS_GIVE_UP_MIN * 60.0:
                banner(f"WARNING: guaranteed soak at point {p.name} given up: the +-{p.gs_band:g} C band held "
                       f"{gs['acc'] / 60.0:.1f} of {p.hold_min:g} min within {p.hold_min + GS_GIVE_UP_MIN:g} min")
                self.log_rtnchg(11, self.position)
                self.log_event(5, p)
                return True
            return False

        self.loop(want_soak, done_soak, self.check_rules)
        self.log_event(6, p)

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - aerosol-feed change message (only pre2 -> pre3 in v8); the operator is present at the start
    def feed_change(self, prev, p):
        banner(f"OPERATOR: set the aerosol feed {prev.aerosol_feed} -> {p.aerosol_feed} before point {p.name}")
        if self.operator_wait:
            try:
                input("Press Enter once the aerosol feed is set ... ")
            except EOFError:
                print("No terminal to wait on: continuing")
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:938-946 (_final_stop) and 210-232 (emergency_stop) at Calibration d4db474
    def stop(self, why):
        """Humidity OFF, then STOP, each tried twice; True when the summary reads back standby."""
        self.expect_constant = False
        stopped = False
        for what, fn in (("humidity OFF", lambda: self.c.set_humidity_enabled(False)), ("STOP", self.c.stop_chamber)):
            for attempt in (1, 2):
                try:
                    ok = fn()
                    if what == "STOP":
                        ok = ok and self.read() and self.c.operationLabel == "standby"
                        stopped = bool(ok)
                    if ok:
                        break
                except Exception:
                    traceback.print_exc()
        if not stopped:
            banner(f"EMERGENCY: STOP not confirmed ({why}) - stop the chamber at the panel now")
        return stopped

    def emergency_stop(self, why):
        banner(f"Humidity OFF and STOP now: {why}")
        self.stop(why)
        try:
            self.log_event(12)
        except Exception:
            traceback.print_exc()

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:948-1062 (_safe, _safe_guarded) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - runner's dry-out ends early on Td_ch <= 5 C and t640_sample_RH <= 35 % for 10 min and never lasts over 90 min (cycle.py:1018-1033); here a fixed 60 min (safe row) - the early end needs the T640 from Influx
    def safe(self, reason):
        r, c = self.r, self.c
        self.phase, self.hold_rh, self.hold_since = "safe", None, None
        banner(f"SAFE entered: {reason}")
        self.log_event(8)
        c.set_humidity_enabled(False)            # first act, even if it reads OFF
        self.sent, self.unconfirmed_since = {"humidity": False}, None
        t0, limit = time.time(), max(r["no_reading_min"], r["unconfirmed_min"]) * 60.0
        ok = {"t": t0}
        plan = {}

        def guard(valid, now):
            if valid and self.unconfirmed_since is None:
                ok["t"] = now
            if now - ok["t"] >= limit:
                raise SafeFailed(f"SAFE could not read or command the chamber for {limit / 60.0:g} min")

        def want_ramp(now):
            if "target" not in plan:
                t_pv = c.temperature_process_value if self.read_ok else None
                if t_pv is None:
                    return {"humidity": False}
                tgt = min(max(t_pv, r["safe_lo"]), r["safe_hi"])
                rate = r["safe_up"] if tgt > t_pv else r["safe_down"]
                plan.update(target=tgt, t_from=t_pv, start=now, dur=abs(tgt - t_pv) / rate * 60.0, rate=rate)
                print(f"SAFE: ramp {t_pv:g} -> {tgt:g} C at {rate:g} C/min, humidity OFF")
            e = now - plan["start"]
            T = plan["target"] if e >= plan["dur"] else \
                plan["t_from"] + math.copysign(plan["rate"] * e / 60.0, plan["target"] - plan["t_from"])
            return {"T": T, "humidity": False}

        self.loop(want_ramp, lambda now, valid: "target" in plan and now - plan["start"] >= plan["dur"] and valid
                  and not differs(c.temperature_set_value, round(plan["target"], 1)), guard)
        print(f"SAFE: dry-out at {plan['target']:g} C, humidity {r['safe_rh']:g} %, purge ON, {r['safe_dry_min']:g} min")
        t_arr = time.time()
        self.loop(lambda now: {"T": plan["target"], "humidity": True, "RH": r["safe_rh"], "purge": True},
                  lambda now, valid: now - t_arr >= r["safe_dry_min"] * 60.0, guard)
        self.stop("SAFE complete")
        self.log_event(9)
        banner("SAFE complete: chamber STOPPED, door closed (the next person opens it)")

    def safe_guarded(self, reason):
        try:
            self.safe(reason)
            return "safe"
        except LeftConstant as e:
            banner(f"The chamber left CONSTANT by itself during SAFE ({e}): nothing more is sent")
            self.log_event(11)
            return "left_constant"
        except KeyboardInterrupt:
            self.emergency_stop("interrupted during SAFE")
            return "interrupted"
        except Exception as e:      # SafeFailed or anything else: stop the chamber
            traceback.print_exc()
            self.emergency_stop(f"SAFE failed: {e}")
            return "safe_failed"

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:1097-1184 (run) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - no events log, no resume / continue-SAFE decision, no notifications; --start-point covers restarts and the outcome is printed and logged to RTNCHG / RTNV8
    def run(self):
        outcome = "error"
        self.log_rtnchg(1, 0)
        self.log_event(0)
        print(f"Run started: {len(self.points)} points, schedule sha256 {self.sha}, first aerosol feed "
              f"{self.points[0].aerosol_feed}")
        try:
            self.startup()
            for k, p in enumerate(self.points):
                self.position = k + 1
                self.run_point(p, self.points[k - 1] if k else None, first=(k == 0))
            self.phase = "stop"
            stopped = self.stop("run complete")
            banner("Run complete, chamber STOPPED" + (". Open the door (stop row)." if stopped else ""))
            outcome = "complete" if stopped else "stop_unconfirmed"
        except Abort as e:
            banner(f"ABORT at point {self.point.name}: {e}")
            self.log_event(7)
            outcome = self.safe_guarded(str(e))
        except LeftConstant as e:
            banner(f"The chamber left CONSTANT by itself ({e}): NOT restarted, no SAFE, nothing more is sent "
                   "(the interlock wins). Inspect the chamber.")
            self.log_event(11)
            outcome = "left_constant"
        except KeyboardInterrupt:
            self.emergency_stop("interrupted (Ctrl-C / SIGTERM)")
            outcome = "interrupted"
        except RunRefused as e:
            banner(f"Run refused, nothing sent: {e}")
            outcome = "refused"
        except Exception as e:
            traceback.print_exc()
            if self.expect_constant:
                outcome = "error, " + self.safe_guarded(f"routine error: {type(e).__name__}: {e}")
            else:
                self.emergency_stop(f"routine error before CONSTANT: {type(e).__name__}")
        finally:
            try:
                self.log_rtnchg(2, self.position, success=int(outcome == "complete"))
                self.log_event(10)
            except Exception:
                traceback.print_exc()
        print(f"Outcome: {outcome}. Resume with: python3 runRoutineV8.py --start-point {self.point.name}"
              if outcome != "complete" else "Outcome: complete")
        return outcome


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - command line and point selection
def parse_args(argv):
    ap = argparse.ArgumentParser(description="Run the v8 calibration routine (v8/schedule.tsv) on the ESPEC BTL-433.")
    ap.add_argument("--plan", action="store_true", help="print the timed plan and the dew points, contact nothing")
    ap.add_argument("--start-point", help="resume at this point (pre1-pre3, 1-30, bake)")
    ap.add_argument("--skip-precycle", action="store_true", help="skip pre1-pre3")
    ap.add_argument("--skip-bake", action="store_true", help="stop after point 30")
    ap.add_argument("--chamber-url", default=url, help=f"Web Controller base URL (default {url})")
    ap.add_argument("--no-operator-wait", action="store_true", help="do not wait for Enter at the aerosol-feed change")
    return ap.parse_args(argv)


def select_points(points, args):
    """The points of this run, in TSV order (never reordered), and the previous row's T for the first ramp of --plan."""
    names = [p.name for p in points]
    start = 0
    if args.start_point is not None:
        if args.start_point not in names:
            raise SystemExit(f"--start-point {args.start_point!r} is not a point ({', '.join(names)})")
        start = names.index(args.start_point)
        if args.skip_precycle and points[start].is_pre:
            raise SystemExit("--start-point is a pre-cycle point and --skip-precycle skips it")
    run = [p for p in points[start:] if not (args.skip_precycle and p.is_pre) and not (args.skip_bake and p.name == "bake")]
    first = names.index(run[0].name)
    return run, (points[first - 1].t_set if first else LAB_T_C)


def raise_interrupt(signum, frame):
    raise KeyboardInterrupt(f"signal {signum}")


def main(argv=None, schedule_path=SCHEDULE_FILE):
    args = parse_args(argv)
    points, stop_row, rules, sha = load_schedule(schedule_path)
    run, t_from0 = select_points(points, args)
    skipped = [p.name for p in points if p not in run]
    print("v8 calibration routine (v8 routine update, 2026-10-20)")
    if not print_plan(run, t_from0, rules, sha, stop_row, schedule_path):
        return 2
    if skipped:
        print(f"  Not run (by the options given): {', '.join(skipped)}")
    if args.plan:
        return 0
    # END ADDED BY CLAUDE

    # ORIGINAL (Lakitha) - runRoutineCustom.py:7-27 at main ccc8ab8; imported here instead of at the top, the url from --chamber-url, the request_timeout and "return 1" ADDED BY CLAUDE (so --plan contacts nothing)
    import mintsXU4.especChamber.chamber as eC
    from  mintsXU4.especChamber.chamber import Chamber
    from mintsXU4 import mintsDefinitions as mD
    from mintsXU4 import mintsSensorReader as mSR

    credentials         = mD.credentials
    token               = credentials['chamber']['token']

    # Check for available chamber index
    chamber_index = eC.get_available_chamber_index(args.chamber_url, token)

    if chamber_index is None:
        print("No available chamber found. Exiting...")
        return 1

    # Create the chamber object only if an index is available
    chamber = Chamber(args.chamber_url, chamber_index, token, request_timeout=REQUEST_TIMEOUT_S)

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - SIGTERM behaves like Ctrl-C (humidity OFF, then STOP), then run
    signal.signal(signal.SIGTERM, raise_interrupt)
    routine = V8Routine(chamber, mSR, run, rules, sha, t_from0=t_from0, operator_wait=not args.no_operator_wait)
    return 0 if routine.run() == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
# END ADDED BY CLAUDE
