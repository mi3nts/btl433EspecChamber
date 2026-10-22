"""
runRoutineV8.py - the v8 calibration routine for the ESPEC BTL-433 (v8 routine update, 2026-10-20; must-fix review,
2026-10-22).

NEW FILE on branch feature/v8-routine-update.

WHAT. Runs the points of v8/schedule.tsv in file order (pre1-pre3, 1-30, bake, then the stop row) in CONSTANT mode.
Per point: a transition that lasts the schedule's window D (the TSV's arrival time minus the previous row's end, never
shorter than the temperature ramp at the row's rate), with the RH change spread over D; then a timed or guaranteed
soak from the end of D. The chamber summary is read every 10 s and the T640 every 10 s (Modbus/TCP over the LAN, in
a background thread). The dew-point guard (dew-point trajectory, dry warm-ups, the first-step rule, the 23 C cap, the
chamber-PV and T640 HOLD / ABORT rules, the stale-T640 rule) keeps water off the sensors and the sample tube. At the
end of each pre-cycle hold the operator answers pass or fail; a fail or no answer goes to SAFE. However the script
ends, the chamber is left stopped (or dried out in SAFE, then stopped); the state file and parkChamberV8.py (systemd
ExecStopPost) cover the ends the script cannot see itself (SIGKILL, out-of-memory, crash).

PROVENANCE. A simplified copy of Dr. Lary's chamber runner: Calibration tools/run_chamber_cycle.py and
calib/chamber/cycle.py, psychro.py, schedule.py, espec.py at Calibration commit d4db474 (schedule.tsv last changed at
d809739). Structure, entry point and data pipeline from Lakitha's runRoutineCustom.py and Chamber.Routine.run_routine
(main ccc8ab8). Ramp, dew-point, soak, SAFE and abort logic copied and simplified from cycle.py; Magnus formulas
copied from psychro.py; TSV parsing, the 10-s / 60-s loop, logging glue, console output and the CLI added by Claude.
The must-fix review (2026-10-22) added the transition window, the T640 reader and rules, the operator answers, the
local outbox and the state file; the T640 register map is that of teledyneSensing firmware/xu4Mqtt/t640/t640.py.

PIPELINE (called, never modified). mintsXU4.especChamber.chamber.Chamber (get_and_write_summary, set_*,
start_constant_mode, stop_chamber), mintsSensorReader.sensorFinisher (CSV; MQTT is switched off in this process and
done by publishV8.py from the outbox), mintsDefinitions.credentials. Streams: the existing BTL433ESC001
STATUS/TMPRT/HMDTY/DAP/PRGRM/CHNG/RTNCHG/RTNPRGV2 and the new BTL433ESC001RTNV8.

LEFT OUT (table "Kept / simplified / dropped" in V8_ROUTINE_UPDATE.md): the rules that need IPS or Influx data (the
pre-cycle checks themselves are answered by the operator, the IPS/T640 ratio, the purge-excess flag), the WIMDA and
tube-heater parts of the excursion rule (not logged here), the humid-soak RH shortfall, gate G0, notifications,
--simulate and the JSON-lines events file.

Usage (from firmware/xu4Mqtt, like the other routine scripts):
    python3 runRoutineV8.py --plan                 # print the timed plan, contact nothing
    python3 runRoutineV8.py --t640-check           # read the T640 three times, contact nothing else
    python3 runRoutineV8.py                        # the full run (operator at the chamber for the pre-cycle)
    python3 runRoutineV8.py --operator pass        # answer a pre-cycle check (also: fail, go, safe)
    python3 runRoutineV8.py --resume               # resume at the point the state file names
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - imports and settings - standard library only, Python 3.8 syntax
import argparse
import hashlib
import json
import math
import os
import re
import select
import signal
import socket
import struct
import sys
import threading
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

# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - T640, operator, state and outbox settings
STATE_DIR         = os.path.join(HERE, "v8", "state")   # state.json and operator.json (git-ignored, v8/.gitignore)
T640_HOST         = "192.168.20.125"     # teledyneSensing firmware/xu4Mqtt/t640Reader.py hostIP
T640_PORT         = 502                  # Modbus/TCP, unit 1 (t640/t640.py)
T640_UNIT         = 1
T640_TIMEOUT_S    = 3.0                  # per connection and per reply; the read runs in its own thread
T640_START_WAIT_S = 60.0                 # no T640 reading this long after start: refused, nothing sent
OPERATOR_WAIT_MIN = 30.0                 # an unanswered pre-cycle check or feed change goes to SAFE
WATCH_TD_C        = 15.0                 # --no-t640: points whose dew point is at or above this need a person watching the T640 (12-21)
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


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 1: the RH change spread over the transition window D
def window_fraction(e, window_s, T, t_from, T1, td0, td1):
    """How far (0-1) the dew point has moved from ``td0`` to ``td1`` after ``e`` s of a window of ``window_s`` s.

    The time fraction e / D spreads the change over D. While T also changes, a rising dew point never runs ahead of
    the T trajectory (the slower of the two fractions) and a falling one never lags it (the faster): the air is
    never closer to its dew point than on dp_trajectory_rh. An RH-only change (T1 == t_from) follows e / D alone.
    """
    f_d = 1.0 if window_s <= 0 else min(1.0, max(0.0, e / window_s))
    if T1 == t_from:
        return f_d
    f_t = min(1.0, max(0.0, (T - t_from) / (T1 - t_from)))
    return min(f_t, f_d) if td1 > td0 else max(f_t, f_d)
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - schedule.tsv reader - one source of truth, no point retyped in Python
# v8 routine update: SIMPLIFIED - the runner validates every column (calib/chamber/schedule.py:354-480); here only the 15 columns of task 5.1 and must-fix 1 are read - the file is the verbatim, sha-logged copy
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
        # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 1: the schedule's arrival time; window_min is set by load_schedule
        self.arrival_min        = float(r["expected_arrival_min_after_start"])
        self.window_min         = None
        # END ADDED BY CLAUDE


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
    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 1: window D = this row's arrival - the previous row's end (arrival + hold), in TSV order
    for prev, p in zip(points, points[1:]):
        p.window_min = p.arrival_min - (prev.arrival_min + prev.hold_min)
    # END ADDED BY CLAUDE
    rules = parse_rules(by)
    rules["max_humidify_after"] = max(p.humidify_after_min for p in points)  # cycle.py:831 (schedule.max_humidify_after)
    return points, by["stop"], rules, hashlib.sha256(raw).hexdigest()
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 1: the transition lasts D, never less than the T ramp
def transition_min(p, ramp_min):
    """Minutes from the transition start to the hold start: the TSV window D, or the T ramp when that is longer
    (the first TSV row has no D; the arrival times are whole minutes, so D can be a few seconds short of the ramp)."""
    return ramp_min if p.window_min is None else max(ramp_min, p.window_min)
# END ADDED BY CLAUDE


# COPIED (Dr. Lary) - calib/chamber/schedule.py:230-307 at Calibration d4db474 (the patterns of _grab / parse_excursion / parse_abort / parse_safe)
# v8 routine update: SIMPLIFIED - the runner reads every number of the three rule rows; here only the ones this routine enforces
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
    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 2: the T640 parts of the excursion row and the abort row's stale rule
    r["hold_srh"], r["hold_srh_min"], r["hold_duty"] = grab(
        r"t640_sample_RH > " + NUM + r" % for " + NUM + r" min while t640_asc_duty >= " + NUM + r" %", ex)  # 45 %, 5 min, 95 %
    (r["hold_box"],) = grab(r"Td_ch > t640_box_T - " + NUM + r" C", ex)                               # 3 C
    a = grab(r"ABORT to SAFE if t640_sample_RH > " + NUM + r" % for " + NUM + r" min, or > " + NUM + r" % for "
             + NUM + r" min", ex)                                                                   # 60 % 10 min, 75 % 2 min
    b = grab(r"or t640_sample_RH > " + NUM + r" % for " + NUM + r" min, or t640_fault", ex)          # 60 % 5 min
    r["abort_srh"] = [(a[0], a[1]), (a[2], a[3]), (b[0], b[1])]
    grab(r"or Td_ch >= t640_box_T", ex)                                                             # no number; must still be there
    r["fault_min"], r["fault_srh"] = grab(r"t640_fault = 1 for " + NUM + r" min while t640_sample_RH > " + NUM + r" %", ex)
    (r["t640_stale_min"],) = grab(r"T640 data stale > " + NUM + r" min", ab)                          # 5 min
    # END ADDED BY CLAUDE
    return r


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - --plan: timed plan, dew point of every RH set point, cap check
def hm(minutes):
    return "%d:%02d" % divmod(int(round(minutes)), 60)


def plan_rows(points, t_from0, rules):
    """Per point: (ramp_min, transition_min, start_min, hold_start_min, end_min). The first ramp uses the SAFE rates
    by direction (cycle.py:826); every transition lasts the TSV window D (must-fix 1)."""
    rows, clock, t_prev = [], 0.0, t_from0
    for k, p in enumerate(points):
        dT = p.t_set - t_prev
        rate = p.ramp_rate if k else (rules["safe_up"] if dT > 0 else rules["safe_down"])
        ramp = abs(dT) / rate if dT else 0.0
        trans = transition_min(p, ramp)
        rows.append((ramp, trans, clock, clock + trans, clock + trans + p.hold_min))
        clock, t_prev = clock + trans + p.hold_min, p.t_set
    return rows


def over_cap(points, cap):
    return [p.name for p in points if p.rh_set is not None and dew_point(p.t_set, p.rh_set) > cap]


def print_plan(points, t_from0, rules, sha, stop_row, path=SCHEDULE_FILE):
    t0 = datetime.now()
    print(f"schedule {path}  sha256 {sha}  dew-point cap {rules['cap']:g} C")
    print(f"{'pos':>3} {'point':>5} {'T':>5} {'RH':>4} {'Td':>5} {'ramp':>5} {'trans':>5} {'hold':>4} {'start':>6} "
          f"{'hold@':>6} {'end':>6} {'clock':>5}  notes")
    rows = plan_rows(points, t_from0, rules)
    for k, (p, (ramp, trans, start, arrive, end)) in enumerate(zip(points, rows), start=1):
        td = "" if p.rh_set is None else "%.1f" % dew_point(p.t_set, p.rh_set)
        notes = ["timed" if p.gs_band is None else "gs +-%g" % p.gs_band, "purge" if p.purge else "",
                 "dry warm-up" if p.rh_set is not None and not p.ramp_humidity else "", p.aerosol_feed, p.tag,
                 "pass/fail asked" if p.is_pre else ""]
        print(f"{k:>3} {p.name:>5} {p.t_set:>5g} {'OFF' if p.rh_set is None else '%g' % p.rh_set:>4} {td:>5} "
              f"{ramp:>5.1f} {trans:>5.1f} {p.hold_min:>4g} {hm(start):>6} {hm(arrive):>6} {hm(end):>6} "
              f"{(t0 + timedelta(minutes=start)).strftime('%H:%M'):>5}  {', '.join(n for n in notes if n)}")
    total = rows[-1][4] if rows else 0.0
    print(f"  STOP at {hm(total)} ({(t0 + timedelta(minutes=total)).strftime('%a %H:%M')} if started now): "
          f"{stop_row['check_or_rule']}")
    print(f"  Total {total / 60:.2f} h ({total:.0f} min). 'trans' is the schedule's window D (the hold starts at its "
          f"end); guaranteed soaks (gs) add the PV lag, the pre-cycle answers add the operator's time; the first ramp "
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
    for line in str(message).split("\n"):
        print(f"#  {line}")
    print("#" * 78)
    print()
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 2: the T640 read locally over the LAN (no Influx)
class T640Modbus:
    """Reads the T640 over Modbus/TCP with the standard library: input registers 0-61 (function 4) and discrete
    inputs 0-7 (function 2), one short connection per read. Register map: teledyneSensing t640/t640.py (floats are
    two registers, high word first)."""

    def __init__(self, host, port=T640_PORT, unit=T640_UNIT, timeout=T640_TIMEOUT_S):
        self.host, self.port, self.unit, self.timeout = host, port, unit, timeout
        self.tid = 0

    @staticmethod
    def _recv(sock, n):
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise IOError("the T640 closed the connection")
            buf += chunk
        return buf

    def _call(self, sock, fc, start, count):
        self.tid = (self.tid + 1) & 0xFFFF
        sock.sendall(struct.pack(">HHHBBHH", self.tid, 0, 6, self.unit, fc, start, count))
        tid, proto, length, _ = struct.unpack(">HHHB", self._recv(sock, 7))
        body = self._recv(sock, length - 1)
        if tid != self.tid or proto != 0:
            raise IOError(f"Modbus reply out of step (transaction {tid}, protocol {proto})")
        if body[0] == (fc | 0x80):
            raise IOError(f"Modbus exception {body[1]} on function {fc}")
        if body[0] != fc or body[1] != len(body) - 2:
            raise IOError(f"malformed Modbus reply to function {fc}")
        return body[2:]

    def read(self):
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            regs = self._call(s, 4, 0, 62)
            bits = self._call(s, 2, 0, 8)

        def f(i):
            return struct.unpack(">f", regs[2 * i:2 * i + 4])[0]

        v = {"pm25": f(8), "sample_rh": f(36), "box_t": f(38), "asc_duty": f(60), "fault": (bits[0] >> 7) & 1}
        for k in ("sample_rh", "box_t", "asc_duty"):
            if not math.isfinite(v[k]):
                raise ValueError(f"T640 {k} is {v[k]}")
        return v


class T640Poller(threading.Thread):
    """Reads the T640 every ``period_s`` in its own thread, so a slow or dead T640 never delays the control loop;
    the loop takes ``latest()`` and the abort row's stale rule judges its age."""

    def __init__(self, reader, period_s=10.0):
        super().__init__(name="t640", daemon=True)
        self.reader, self.period_s = reader, period_s
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.t_read = self.values = self.error = None

    def run(self):
        while not self.stopped.is_set():
            t0 = time.time()
            try:
                v = self.reader.read()
                with self.lock:
                    self.t_read, self.values, self.error = time.time(), v, None
            except Exception as e:
                with self.lock:
                    self.error = f"{type(e).__name__}: {e}"
            self.stopped.wait(max(0.5, self.period_s - (time.time() - t0)))

    def latest(self):
        """(time of the last good read or None, its values)."""
        with self.lock:
            return self.t_read, self.values
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 5: atomic state file; must-fix 3: the operator's answers
def write_json_atomic(path, data):
    """Write ``data`` so that a reader (or a crash) sees the old file or the new one, never half of one."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        fd = os.open(folder, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


def boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id") as f:
            return f.read().strip()
    except OSError:
        return None


def pid_alive(state):
    """True when the process that wrote ``state`` still runs (same host, same boot)."""
    pid = (state or {}).get("pid")
    if not pid or state.get("host") != socket.gethostname() or state.get("boot_id") != boot_id():
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class StateFile:
    """STATE_DIR/state.json: run, point, phase, last event and outcome, rewritten atomically at every event."""

    def __init__(self, path):
        self.path = path

    def read(self):
        try:
            with open(self.path) as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except ValueError as e:
            return {"outcome": "unreadable state file", "error": str(e)}

    def write(self, data):
        write_json_atomic(self.path, data)


class OperatorChannel:
    """The operator's answers: a line typed at the terminal (when stdin is one; Enter alone = go) or
    ``python3 runRoutineV8.py --operator WORD``, which writes STATE_DIR/operator.json. Each answer is read once;
    an answer older than ``since`` is dropped."""

    def __init__(self, path, tty=None):
        self.path = path
        if tty is None:
            try:
                tty = sys.stdin is not None and sys.stdin.isatty()
            except (AttributeError, ValueError):
                tty = False
        self.tty = tty

    def poll(self, since, waiting=None):
        word = None
        if self.tty:
            try:
                if select.select([sys.stdin], [], [], 0)[0]:
                    word = sys.stdin.readline().strip().lower() or "go"
            except (OSError, ValueError):
                self.tty = False
        try:
            with open(self.path) as f:
                d = json.load(f)
            os.remove(self.path)
            if word is None and float(d.get("time", 0)) >= since:
                word = str(d.get("answer", "")).strip().lower()
        except FileNotFoundError:
            pass
        except (ValueError, OSError) as e:
            print(f"Operator file {self.path} unreadable ({e}): ignored")
            try:
                os.remove(self.path)
            except OSError:
                pass
        return word or None


def send_operator_answer(word, state_dir=STATE_DIR):
    write_json_atomic(os.path.join(state_dir, "operator.json"), {"answer": word, "time": time.time(), "pid": os.getpid()})
    print(f"Answer {word!r} written to {os.path.join(state_dir, 'operator.json')}; the routine reads it within 10 s.")
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 4: no MQTT in the control process
class Outbox:
    """One JSON line per record ({"sensor": name, "data": record}), one file per UTC day, for publishV8.py. JSON
    keeps each value's type, so the published payload is the one sensorFinisher would have sent."""

    def __init__(self, folder):
        self.folder = folder

    def write(self, sensorName, sensorDictionary):
        try:
            os.makedirs(self.folder, exist_ok=True)
            path = os.path.join(self.folder, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
            line = json.dumps({"sensor": sensorName, "data": sensorDictionary}, default=str) + "\n"
            with open(path, "a") as f:
                f.write(line)
        except Exception as e:      # the outbox must never stop the control loop
            print(f"Outbox write failed ({type(e).__name__}: {e}); the CSV still has the record")


def install_outbox(mSR, folder):
    """Switch MQTT off in this process (mintsSensorReader reads ``mqttOn`` at every call) and add every record to
    the outbox after the CSV. chamber.py calls ``mSR.sensorFinisher`` through the module, so its records follow."""
    mSR.mqttOn = False
    original = mSR.sensorFinisher
    box = Outbox(folder)

    def sensorFinisher(dateTime, sensorName, sensorDictionary):
        original(dateTime, sensorName, sensorDictionary)
        box.write(sensorName, sensorDictionary)

    mSR.sensorFinisher = sensorFinisher
    return box


def outbox_folder(mD):
    return os.path.join(mD.dataFolder, mD.macAddress, "v8outbox")
# END ADDED BY CLAUDE


class V8Routine:
    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - routine state - one object per run, so iterations restart at 1
    event_mapping = {
        0: "Run Started", 1: "Transition Started", 2: "Arrived", 3: "Humidity Enabled After Dry Warm-up",
        4: "Dew-Point Hold", 5: "Guaranteed Soak Given Up", 6: "Soak Ended", 7: "Aborted", 8: "SAFE Started",
        9: "SAFE Ended", 10: "Run Ended", 11: "Chamber Left CONSTANT", 12: "Emergency Stop",
        # v8 must-fix review (2026-10-22): CHANGED - events 13-18 added (T reached inside the window, the pre-cycle answers, the feed change, an operator SAFE request)
        13: "Temperature Reached", 14: "Pre-cycle Check Passed", 15: "Pre-cycle Check Failed",
        16: "Pre-cycle Check Unanswered", 17: "Operator Confirmed Feed Change", 18: "Operator Requested SAFE",
    }

    def __init__(self, chamber, mSR, points, rules, sha, t_from0=LAB_T_C, operator_wait=True, t640=None, operator=None,
                 state=None, info=None):
        self.c, self.mSR, self.points, self.r, self.sha = chamber, mSR, points, rules, sha
        self.operator_wait = operator_wait
        self.tick_s = rules["tick_s"]
        self.minutes = [trans + p.hold_min for p, (_, trans, _, _, _) in zip(points, plan_rows(points, t_from0, rules))]
        self.point, self.position, self.phase = points[0], 0, "start"
        self.sent, self.last_want, self.read_ok = {}, None, False
        self.expect_constant = False
        self.last_valid = self.run_start = self.step_start = time.time()
        self.unconfirmed_since = self.hold_rh = None
        self.hold_noted = self.pulldown_done = False
        # v8 must-fix review (2026-10-22): CHANGED - one timer per rule ("hold:..." reset at each point), the T640, the operator, the state file
        self.since = {}
        self.t640, self.op, self.state, self.info = t640, operator, state, dict(info or {})
        self.waiting, self.answer, self.t640_now = None, None, None
        self.outcome, self.parked, self.hands_off = None, None, False
        self.last_event, self.run_id = None, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
    # v8 must-fix review (2026-10-22): CHANGED - a "detail" field (the rule that fired, the operator's answer, the outcome) and the state file written at every event
    def log_event(self, event_id, p=None, detail=""):
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
            ("detail"         , str(detail)),
        ])
        self.last_event = (event_id, str(detail))
        self.save_state()
        self.mSR.sensorFinisher(dateTime, SENSOR_ID, sensorDictionary)
    # END ADDED BY CLAUDE

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 5: point, phase, last event and outcome, atomically, before the event is logged
    def save_state(self):
        if self.state is None:
            return
        d = OrderedDict([
            ("run_id", self.run_id), ("pid", os.getpid()), ("host", socket.gethostname()), ("boot_id", boot_id()),
            ("schedule_sha", self.sha), ("points", [p.name for p in self.points]), ("point", self.point.name),
            ("position", self.position), ("phase", self.phase),
            ("last_event", None if self.last_event is None else self.last_event[0]),
            ("last_event_label", None if self.last_event is None else self.event_mapping.get(self.last_event[0])),
            ("detail", None if self.last_event is None else self.last_event[1]),
            ("outcome", self.outcome), ("chamber_parked", self.parked), ("hands_off", self.hands_off),
            ("updated", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")),
        ])
        d.update(self.info)
        try:
            self.state.write(d)
        except Exception as e:      # a full disk must not stop the control loop; the park hook then assumes the worst
            print(f"State file not written ({type(e).__name__}: {e})")
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

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - one timer per rule: True once ``cond`` has held for ``minutes``
    def held(self, key, cond, now, minutes):
        if not cond:
            self.since.pop(key, None)
            return False
        return now - self.since.setdefault(key, now) >= minutes * 60.0

    def t640_values(self, now):
        """The T640's latest values (None with --no-t640); the abort row's stale rule raises Abort."""
        if self.t640 is None:
            return None
        t_read, values = self.t640.latest()
        age = now - (self.run_start if t_read is None else t_read)
        if age >= self.r["t640_stale_min"] * 60.0:
            raise Abort(f"T640 data stale > {self.r['t640_stale_min']:g} min "
                        f"({'never read' if t_read is None else 'last read %.0f s ago' % age})")
        self.t640_now = values
        return values

    def check_operator(self, now):
        """An operator SAFE request at any time; an answer while one is asked."""
        if self.op is None:
            return
        word = self.op.poll(self.waiting[2] if self.waiting else self.run_start, self.waiting)
        if not word:
            return
        if word == "safe":
            self.log_event(18, detail="operator")
            raise Abort("operator requested SAFE")
        if self.waiting and word in self.waiting[3]:
            self.answer = word
        else:
            print(f"Operator answer {word!r} ignored: "
                  + (f"expected one of {', '.join(self.waiting[3])}" if self.waiting else "nothing is being asked"))
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:603-609 (no reading, unconfirmed), 615-650 (excursion HOLD / ABORT), 653-672 (HOLD), 679-684 (pull-down) at Calibration d4db474
    # v8 must-fix review (2026-10-22): CHANGED - the T640 parts (sample RH, box T, fault bit) and the stale-T640 rule are back, read from the T640 over the LAN; still left out: the WIMDA dew point and the tube heater (not logged here)
    def check_rules(self, valid, now):
        r = self.r
        self.check_operator(now)
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
        t6 = self.t640_values(now)
        srh = box = None
        if t6 is not None:
            srh, box = t6["sample_rh"], t6["box_t"]

        # ABORT to SAFE (excursion row)
        if self.held("abort:td", td is not None and td > r["cap"] + r["abort_over"], now, r["abort_min"]):
            raise Abort(f"dew-point excursion ABORT: chamber dew point {td:.1f} C > {r['cap'] + r['abort_over']:g} C "
                        f"for {r['abort_min']:g} min")
        if t6 is not None:
            for limit, minutes in r["abort_srh"]:
                if self.held(f"abort:srh>{limit:g}/{minutes:g}", srh > limit, now, minutes):
                    raise Abort(f"dew-point excursion ABORT: T640 sample RH {srh:.1f} % > {limit:g} % for {minutes:g} min")
            if td is not None and td >= box:
                raise Abort(f"dew-point excursion ABORT: chamber dew point {td:.1f} C >= T640 box T {box:.1f} C")
            if self.held("abort:fault", t6["fault"] == 1 and srh > r["fault_srh"], now, r["fault_min"]):
                raise Abort(f"dew-point excursion ABORT: T640 system fault for {r['fault_min']:g} min with sample RH "
                            f"{srh:.1f} % > {r['fault_srh']:g} %")

        # HOLD (excursion row)
        why = []
        if self.held("hold:td", td is not None and td > r["cap"] + r["hold_over"], now, r["hold_min"]):
            why.append(f"chamber dew point {td:.1f} C > {r['cap'] + r['hold_over']:g} C for {r['hold_min']:g} min")
        if t6 is not None:
            if self.held("hold:srh", srh > r["hold_srh"] and t6["asc_duty"] >= r["hold_duty"], now, r["hold_srh_min"]):
                why.append(f"T640 sample RH {srh:.1f} % > {r['hold_srh']:g} % for {r['hold_srh_min']:g} min with the "
                           f"ASC heater at {t6['asc_duty']:.0f} %")
            if td is not None and td > box - r["hold_box"]:
                why.append(f"chamber dew point {td:.1f} C > T640 box T {box:.1f} C - {r['hold_box']:g} C")
        if why:
            self.hold("; ".join(why))

    # v8 must-fix review (2026-10-22): CHANGED - takes the reason (any HOLD rule) instead of the chamber dew point
    def hold(self, reason):
        """Step the RH set point back to the RH whose dew point is cap - 1 C; never re-raised within the point."""
        want = self.last_want or {}
        t_set = self.sent.get("T", self.c.temperature_set_value)
        if want.get("humidity") is not True or t_set is None:
            if not self.hold_noted:
                self.hold_noted = True
                print(f"HOLD at point {self.point.name} ({reason}): humidity OFF, nothing to step back")
            return
        target = min(max(rh_for_dew(self.r["cap"] - self.r["hold_below"], t_set), RH_RANGE[0]), RH_RANGE[1])
        if self.hold_rh is not None and target >= self.hold_rh - 1e-9:
            return
        self.hold_rh = target if self.hold_rh is None else min(self.hold_rh, target)
        banner(f"DEW-POINT HOLD at point {self.point.name}: {reason}; RH set point -> {self.hold_rh:.1f} % for the "
               f"rest of the point")
        self.log_event(4, detail=reason)
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
        t6 = self.t640_now
        print(f"Point {self.point.name} ({k}/{len(self.points)}, {self.phase}) | T set {v('temperature_set_value')} -> "
              f"{self.point.t_set:g} (PV {v('temperature_process_value')}) | RH set {hum} (PV {v('humidity_process_value')}) | "
              f"purge {'ON' if v('dap_enable') == 1 else 'OFF'} | point {hm((now - self.step_start) / 60.0)} | "
              f"run {hm((now - self.run_start) / 60.0)}, about {hm(left)} left"
              + ("" if t6 is None else f" | T640 sample RH {t6['sample_rh']:.1f} %, box {t6['box_t']:.1f} C")
              + ("" if valid else " | NO VALID READING"))
    # END ADDED BY CLAUDE

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 3: ask the operator while the loop and every rule keep running
    def ask(self, kind, prompt, choices, want_fn):
        """Hold ``want_fn`` until the operator answers one of ``choices``; None after OPERATOR_WAIT_MIN."""
        banner(prompt + f"\nAnswer here ({' / '.join(choices)}), or from any shell in firmware/xu4Mqtt:\n"
               + "\n".join(f"    python3 runRoutineV8.py --operator {w}" for w in choices)
               + f"\nNo answer within {OPERATOR_WAIT_MIN:g} min = SAFE. Any time: --operator safe.")
        since, phase = time.time(), self.phase
        self.waiting, self.answer, self.phase = (kind, self.point.name, since, tuple(choices)), None, "operator: " + kind
        self.save_state()
        try:
            self.loop(want_fn, lambda now, valid: self.answer is not None or now - since >= OPERATOR_WAIT_MIN * 60.0,
                      self.check_rules)
        finally:
            self.waiting, self.phase = None, phase
        return self.answer
    # END ADDED BY CLAUDE

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:776-802 (_startup) at Calibration d4db474
    def startup(self):
        # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 2: no T640 reading, no start (nothing sent yet)
        if self.t640 is not None:
            t_end = time.time() + T640_START_WAIT_S
            while self.t640.latest()[0] is None and time.time() < t_end:
                time.sleep(1.0)
            if self.t640.latest()[0] is None:
                raise RunRefused(f"no T640 reading in {T640_START_WAIT_S:g} s (last error: "
                                 f"{getattr(self.t640, 'error', None)}); check the LAN, or run with --no-t640 and a "
                                 f"person watching the T640 sample RH")
        # END ADDED BY CLAUDE
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
        self.point = p
        # v8 routine update: SIMPLIFIED - the aerosol feed is manual in the runner too (cycle.py:861-862 logs it); here the operator is asked
        # v8 must-fix review (2026-10-22): CHANGED - asked before anything else of the point, while the previous point's set points and every rule keep running (was a blocking input())
        if prev is not None and p.aerosol_feed != prev.aerosol_feed:
            self.feed_change(prev, p)
        self.hold_rh, self.hold_noted = None, False
        for key in [k for k in self.since if k.startswith("hold:")]:
            del self.since[key]
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
        # v8 must-fix review (2026-10-22): CHANGED - also for an RH-only change, which is now spread over D too
        if humid_on and ramp_h and td0 is None:
            td0 = td1
        # v8 must-fix review (2026-10-22): CHANGED - must-fix 1: the transition lasts the TSV window D (cycle.py:840, 853-854; transition_minutes at schedule.py:334-346): T ramps at the row's rate, the RH change is spread over D (window_fraction), the hold starts at the end of D
        ramp_s = abs(dT) / rate * 60.0 if dT else 0.0
        window_s = transition_min(p, ramp_s / 60.0) * 60.0
        print("-" * 78)
        print(f"Point {p.name} ({self.position}/{len(self.points)}, {p.tag}): TRANSITION {t_from:g} -> {p.t_set:g} C at "
              f"{rate:g} C/min ({ramp_s / 60.0:.1f} min) in a {window_s / 60.0:.1f}-min window, RH "
              f"{'OFF' if p.rh_set is None else '%g %%' % p.rh_set}, humidity during the window "
              f"{'ON (dew point spread over the window)' if humid_on and ramp_h else 'OFF'}, purge "
              f"{'ON' if p.purge else 'OFF'}, aerosol feed {p.aerosol_feed}")
        if self.t640 is None and p.dew_point is not None and p.dew_point >= WATCH_TD_C:
            banner(self.watch_text(p))
        self.phase = "transition"
        self.log_rtnprg(p)
        self.log_event(1, p)

        # v8 routine update: SIMPLIFIED - runner sends the ramping T set point every 10-s tick (cycle.py:865-869); here a new T set point every 60 s
        t0, sign = time.time(), (1.0 if dT > 0 else -1.0)
        st = {"t_arr": None, "humid": False}

        def humidity(now, w):
            """The humidity part of the wanted state, for the window and the soak alike."""
            if not humid_on:
                w["humidity"] = False
            elif ramp_h:
                f = window_fraction(now - t0, window_s, w["T"], t_from, p.t_set, td0, td1)
                w.update(humidity=True, RH=p.rh_set if f >= 1.0 else rh_for_dew(td0 + (td1 - td0) * f, w["T"]))
            elif st["t_arr"] is not None and now - st["t_arr"] >= wait * 60.0:
                # dry warm-up: humidity_after_min counts from the T arrival, so the window D holds the RH settling
                w.update(humidity=True, RH=p.rh_set)
                if not st["humid"]:
                    st["humid"] = True
                    print(f"Point {p.name}: dry warm-up done, humidity ON at {p.rh_set:g} % "
                          f"{(now - st['t_arr']) / 60.0:.1f} min after the temperature arrived")
                    self.log_event(3, p)
            else:
                w["humidity"] = False                           # dry warm-up / humidity-OFF row
            return w

        def want_transition(now):
            e = now - t0
            T = p.t_set if e >= ramp_s else t_from + sign * rate * e / 60.0
            return humidity(now, {"T": T, "purge": p.purge})

        def rules_transition(valid, now):
            self.check_rules(valid, now)
            if st["t_arr"] is None and now - t0 >= ramp_s and valid and not differs(c.temperature_set_value, p.t_set):
                st["t_arr"] = now
                self.log_event(13, p, detail=f"{(now - t0) / 60.0:.1f} min into a {window_s / 60.0:.1f}-min window")

        self.loop(want_transition, lambda now, valid: now - t0 >= window_s and st["t_arr"] is not None,
                  rules_transition)

        t_hold, hold_s = time.time(), p.hold_min * 60.0
        self.phase = "soak"
        self.log_rtnchg(10, self.position)
        self.log_event(2, p)
        if p.is_pre:
            # v8 routine update: SIMPLIFIED - runner checks pre1-pre3 against T640 / IPS data (cycle.py:719-774); here the operator checks them
            # v8 must-fix review (2026-10-22): CHANGED - must-fix 3: the checklist at arrival, then pass / fail asked at the end of the hold (below)
            banner(f"OPERATOR CHECKLIST for {p.name} (pass / fail is asked at the end of the {p.hold_min:g}-min hold): "
                   f"{p.check}")
        elif p.check:
            print(f"Operator note for point {p.name}: {p.check}")
        gs = {"acc": 0.0, "last": None}

        def want_soak(now):
            return humidity(now, {"T": p.t_set, "purge": p.purge})

        def done_soak(now, valid):
            if p.gs_band is None:
                return now - t_hold >= hold_s
            t_pv = c.temperature_process_value
            if gs["last"] is not None and valid and t_pv is not None and abs(t_pv - p.t_set) <= p.gs_band:
                gs["acc"] += now - gs["last"]
            gs["last"] = now
            if gs["acc"] >= hold_s:
                return True
            if now - t_hold >= hold_s + GS_GIVE_UP_MIN * 60.0:
                banner(f"WARNING: guaranteed soak at point {p.name} given up: the +-{p.gs_band:g} C band held "
                       f"{gs['acc'] / 60.0:.1f} of {p.hold_min:g} min within {p.hold_min + GS_GIVE_UP_MIN:g} min")
                self.log_rtnchg(11, self.position)
                self.log_event(5, p)
                return True
            return False

        self.loop(want_soak, done_soak, self.check_rules)
        self.log_event(6, p)
        # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 3: a failed or unanswered pre-cycle check goes to SAFE (protocol section 4, abort row); the next point waits for the answer
        if p.is_pre:
            ans = self.ask("check", f"PRE-CYCLE CHECK {p.name}: {p.check}", ("pass", "fail"), want_soak)
            if ans == "pass":
                self.log_event(14, p, detail="operator: pass")
            elif ans == "fail":
                self.log_event(15, p, detail="operator: fail")
                raise Abort(f"pre-cycle check {p.name} failed (operator)")
            else:
                self.log_event(16, p, detail=f"no answer in {OPERATOR_WAIT_MIN:g} min")
                raise Abort(f"pre-cycle check {p.name} not answered within {OPERATOR_WAIT_MIN:g} min")
        # END ADDED BY CLAUDE

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - aerosol-feed change message (only pre2 -> pre3 in v8); the operator is present at the start
    # v8 must-fix review (2026-10-22): CHANGED - asked through ask() (the loop and the rules keep running; no answer in 30 min = SAFE) instead of a blocking input()
    def feed_change(self, prev, p):
        if not self.operator_wait:
            banner(f"OPERATOR: set the aerosol feed {prev.aerosol_feed} -> {p.aerosol_feed} before point {p.name} "
                   f"(--no-operator-wait: not waited for)")
            return
        ans = self.ask("feed", f"OPERATOR: set the aerosol feed {prev.aerosol_feed} -> {p.aerosol_feed} before point "
                       f"{p.name}, then answer go (Enter)", ("go",), lambda now: dict(self.last_want or {}))
        if ans is None:
            raise Abort(f"aerosol feed change before point {p.name} not confirmed within {OPERATOR_WAIT_MIN:g} min")
        self.log_event(17, p, detail=f"{prev.aerosol_feed} -> {p.aerosol_feed}")

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 2 fallback: the written watch threshold when the T640 is not read
    def watch_text(self, p):
        r = self.r
        limits = ", ".join(f"> {lim:g} % for {mins:g} min" for lim, mins in sorted(set(r["abort_srh"]), key=lambda x: -x[0]))
        return (f"T640 NOT READ (--no-t640): a person must watch the T640 sample RH through point {p.name} (dew point "
                f"{p.dew_point:g} C).\nSAFE now (python3 runRoutineV8.py --operator safe) if the sample RH is {limits},"
                f"\nor the T640 box T is at or below the chamber dew point, or a T640 fault shows with sample RH > "
                f"{r['fault_srh']:g} %.")
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
        self.parked = stopped      # v8 must-fix review (2026-10-22): CHANGED - recorded for the state file and parkChamberV8.py
        return stopped

    def emergency_stop(self, why):
        banner(f"Humidity OFF and STOP now: {why}")
        self.stop(why)
        try:
            self.log_event(12, detail=why)
        except Exception:
            traceback.print_exc()

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:948-1062 (_safe, _safe_guarded) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - runner's dry-out ends early on Td_ch <= 5 C and t640_sample_RH <= 35 % for 10 min and never lasts over 90 min (cycle.py:1018-1033); here a fixed 60 min (safe row)
    def safe(self, reason):
        r, c = self.r, self.c
        self.phase, self.hold_rh = "safe", None
        banner(f"SAFE entered: {reason}")
        self.log_event(8, detail=reason)
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
            self.hands_off = True
            self.log_event(11, detail=str(e))
            return "left_constant"
        except KeyboardInterrupt:
            self.emergency_stop("interrupted during SAFE")
            return "interrupted"
        except Exception as e:      # SafeFailed or anything else: stop the chamber
            traceback.print_exc()
            self.emergency_stop(f"SAFE failed: {e}")
            return "safe_failed"

    # COPIED (Dr. Lary) - calib/chamber/cycle.py:1097-1184 (run) at Calibration d4db474
    # v8 routine update: SIMPLIFIED - no events log, no notifications; the outcome is printed and logged to RTNCHG / RTNV8
    # v8 must-fix review (2026-10-22): CHANGED - the outcome, the confirmed STOP and the hands-off case go to the state file, which decides what a restart may do (main) and what parkChamberV8.py does
    def run(self):
        outcome = "error"
        self.log_rtnchg(1, 0)
        self.log_event(0)
        print(f"Run started: {len(self.points)} points, schedule sha256 {self.sha}, first aerosol feed "
              f"{self.points[0].aerosol_feed}, T640 {'NOT READ (--no-t640)' if self.t640 is None else 'read every 10 s'}")
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
            self.log_event(7, detail=str(e))
            outcome = self.safe_guarded(str(e))
        except LeftConstant as e:
            banner(f"The chamber left CONSTANT by itself ({e}): NOT restarted, no SAFE, nothing more is sent "
                   "(the interlock wins). Inspect the chamber.")
            self.hands_off = True
            self.log_event(11, detail=str(e))
            outcome = "left_constant"
        except KeyboardInterrupt:
            self.emergency_stop("interrupted (Ctrl-C / SIGTERM / SIGHUP)")
            outcome = "interrupted"
        except RunRefused as e:
            banner(f"Run refused, nothing sent: {e}")
            self.hands_off = True
            outcome = "refused"
        except Exception as e:
            traceback.print_exc()
            if self.expect_constant:
                outcome = "error, " + self.safe_guarded(f"routine error: {type(e).__name__}: {e}")
            else:
                self.emergency_stop(f"routine error before CONSTANT: {type(e).__name__}")
        finally:
            self.outcome = outcome
            try:
                self.log_rtnchg(2, self.position, success=int(outcome == "complete"))
                self.log_event(10, detail=outcome)
            except Exception:
                traceback.print_exc()
                self.save_state()
        if outcome == "complete":
            print("Outcome: complete")
        elif blocked_reason(self.state.read() if self.state else {"outcome": outcome}):
            print(f"Outcome: {outcome}. A new run needs --clear-abort \"<what was checked>\" after the chamber has been "
                  f"inspected.")
        else:
            print(f"Outcome: {outcome}. Resume with: python3 runRoutineV8.py --resume (point {self.point.name})")
        return outcome


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 5: what the last run's state allows
def blocked_reason(prev):
    """Why the previous run's state forbids a start or a resume without --clear-abort (None = allowed)."""
    if not prev:
        return None
    out = prev.get("outcome")
    if prev.get("phase") == "safe" or prev.get("last_event") == 7:     # however it ended after that (parked, interrupted)
        return f"the previous run aborted to SAFE at point {prev.get('point')} (outcome {out!r})"
    if out is None or out in ("complete", "interrupted", "refused", "error") or out.startswith("died"):
        return None             # "error" alone: an error before CONSTANT, humidity OFF and STOP sent, no SAFE
    return f"the previous run ended with outcome {out!r} at point {prev.get('point')}"
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - command line and point selection
def parse_args(argv):
    ap = argparse.ArgumentParser(description="Run the v8 calibration routine (v8/schedule.tsv) on the ESPEC BTL-433.")
    ap.add_argument("--plan", action="store_true", help="print the timed plan and the dew points, contact nothing")
    ap.add_argument("--start-point", help="resume at this point (pre1-pre3, 1-30, bake)")
    ap.add_argument("--skip-precycle", action="store_true", help="skip pre1-pre3")
    ap.add_argument("--skip-bake", action="store_true", help="stop after point 30")
    ap.add_argument("--chamber-url", default=url, help=f"Web Controller base URL (default {url})")
    ap.add_argument("--no-operator-wait", action="store_true", help="do not wait for the operator at the aerosol-feed change")
    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - T640, operator answers, state and resume
    ap.add_argument("--t640-host", default=T640_HOST, help=f"T640 Modbus/TCP address (default {T640_HOST})")
    ap.add_argument("--t640-port", type=int, default=T640_PORT, help=f"T640 Modbus/TCP port (default {T640_PORT})")
    ap.add_argument("--no-t640", action="store_true",
                    help="do not read the T640 (its rules are off): a person must watch the T640 sample RH at the "
                         "points with a dew point >= %g C" % WATCH_TD_C)
    ap.add_argument("--t640-check", action="store_true", help="read the T640 three times and print it, contact nothing else")
    ap.add_argument("--operator", choices=("pass", "fail", "go", "safe"),
                    help="answer the running routine (pre-cycle check pass / fail, feed change go) or send it to SAFE")
    ap.add_argument("--resume", action="store_true", help="resume at the point the state file names")
    ap.add_argument("--clear-abort", metavar="WHAT_WAS_CHECKED",
                    help="allow a start after an aborted / SAFE / unconfirmed run, saying what was checked")
    ap.add_argument("--state-dir", default=STATE_DIR, help=f"state.json and operator.json (default {STATE_DIR})")
    # END ADDED BY CLAUDE
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


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 5: SIGHUP (a closed terminal) parks the chamber like SIGTERM and Ctrl-C
def install_signal_handlers():
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), raise_interrupt)


def start_gate(args, sha, state):
    """None when this start is allowed (``args.start_point`` set for --resume); else the exit code after a message."""
    prev = state.read()
    if prev and prev.get("outcome") is None and pid_alive(prev):
        print(f"Refused: the routine is already running (pid {prev.get('pid')}, point {prev.get('point')}).")
        return 3
    why = blocked_reason(prev)
    if why and not args.clear_abort:
        print(f"Refused: {why}.\nInspect the chamber (dry, door, water), then start with --clear-abort \"<what was "
              f"checked>\". The state file is {state.path}.")
        return 3
    if args.resume:
        if not prev or not prev.get("point") or prev.get("outcome") == "complete":
            print("Refused: --resume has nothing to resume (no state, or the last run completed).")
            return 3
        if prev.get("schedule_sha") != sha:
            print("Refused: --resume with a different schedule.tsv than the run being resumed; use --start-point.")
            return 3
        args.start_point = prev["point"]
        print(f"Resuming at point {args.start_point} (last run: outcome {prev.get('outcome')}, phase {prev.get('phase')}).")
    return None


def t640_check(args):
    reader = T640Modbus(args.t640_host, args.t640_port)
    good = 0
    for k in range(3):
        t0 = time.time()
        try:
            v = reader.read()
            good += 1
            print(f"T640 {args.t640_host}: sample RH {v['sample_rh']:.1f} %, box T {v['box_t']:.1f} C, ASC heater "
                  f"{v['asc_duty']:.0f} %, fault {v['fault']}, PM2.5 {v['pm25']:.2f} ug/m3 ({time.time() - t0:.1f} s)")
        except Exception as e:
            print(f"T640 {args.t640_host}: no reading ({type(e).__name__}: {e})")
        if k < 2:
            time.sleep(10)
    return 0 if good == 3 else 1
# END ADDED BY CLAUDE


def main(argv=None, schedule_path=SCHEDULE_FILE):
    args = parse_args(argv)
    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - operator answer and T640 check: nothing else is touched
    if args.operator:
        send_operator_answer(args.operator, args.state_dir)
        return 0
    if args.t640_check:
        return t640_check(args)
    # END ADDED BY CLAUDE
    points, stop_row, rules, sha = load_schedule(schedule_path)
    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 5: no start while a run is active, none after an abort without --clear-abort
    state = StateFile(os.path.join(args.state_dir, "state.json"))
    if not args.plan:
        code = start_gate(args, sha, state)
        if code is not None:
            return code
    # END ADDED BY CLAUDE
    run, t_from0 = select_points(points, args)
    skipped = [p.name for p in points if p not in run]
    print("v8 calibration routine (v8 routine update, 2026-10-20; must-fix review, 2026-10-22)")
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

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 4: CSV and the local outbox only; publishV8.py publishes
    box = install_outbox(mSR, outbox_folder(mD))
    print(f"MQTT is off in this process; records go to the CSV files and to {box.folder} (published by publishV8.py)")
    # END ADDED BY CLAUDE

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
    # v8 must-fix review (2026-10-22): CHANGED - SIGHUP too; the T640 poller, the operator channel and the state file
    install_signal_handlers()
    t640 = None
    if args.no_t640:
        banner(f"--no-t640: the T640 rules are OFF. A person must watch the T640 sample RH at points "
               f"{', '.join(p.name for p in run if p.dew_point is not None and p.dew_point >= WATCH_TD_C)} "
               f"with the written threshold printed at each of them.")
    else:
        t640 = T640Poller(T640Modbus(args.t640_host, args.t640_port), period_s=rules["tick_s"])
        t640.start()
    info = {"chamber_url": args.chamber_url, "chamber_index": chamber_index, "argv": list(sys.argv[1:] if argv is None else argv),
            "t640": None if args.no_t640 else f"{args.t640_host}:{args.t640_port}"}
    if args.clear_abort:
        info["cleared_abort"] = {"by": args.clear_abort, "previous": state.read()}
    routine = V8Routine(chamber, mSR, run, rules, sha, t_from0=t_from0, operator_wait=not args.no_operator_wait,
                        t640=t640, operator=OperatorChannel(os.path.join(args.state_dir, "operator.json")),
                        state=state, info=info)
    return 0 if routine.run() == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
# END ADDED BY CLAUDE
