"""
Hermetic test helpers for the v8 routine update (2026-10-20). NEW FILE on branch feature/v8-routine-update.

PROVENANCE. Written by Claude for this branch: the shims, the fake clock and the simulated Web Controller are new;
the controller's JSON layout is the one chamber.py's get_and_write_summary reads (main ccc8ab8) and its payload
handling follows Calibration calib/chamber/sim.py's idea (PV follows the set point) without copying it.

WHY. The tests must never read credentials.yml, never import paho / serial / getmac, and never reach the chamber,
the MQTT broker or Influx. Importing this module first installs fake mintsXU4.mintsDefinitions and
mintsXU4.mintsSensorReader modules; chamber.py's module-level ``requests`` and ``time`` are patched per test.
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - module shims: no credentials.yml, no MQTT, no serial ports
import copy
import math
import os
import sys
import types
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
XU4 = os.path.dirname(HERE)
if XU4 not in sys.path:
    sys.path.insert(0, XU4)

if "mintsXU4.mintsDefinitions" in sys.modules and not getattr(sys.modules["mintsXU4.mintsDefinitions"], "FAKE", False):
    raise RuntimeError("the real mintsDefinitions was imported before the test shim (it reads credentials.yml)")

import mintsXU4  # noqa: E402  (empty package __init__)

mD = types.ModuleType("mintsXU4.mintsDefinitions")
mD.FAKE = True
mD.dataFolder = os.path.join(HERE, "_never_written")
mD.macAddress = "testmac"
mD.credentials = {"chamber": {"token": "test-token-not-a-secret"}}
sys.modules["mintsXU4.mintsDefinitions"] = mD
mintsXU4.mintsDefinitions = mD

mSR = types.ModuleType("mintsXU4.mintsSensorReader")
mSR.FAKE = True
mSR.records = []          # (fake time, sensor name, dict)
mSR.clock = None


def _sensorFinisher(dateTime, sensorName, sensorDictionary):
    mSR.records.append((mSR.clock.now if mSR.clock else 0.0, sensorName, dict(sensorDictionary)))


mSR.sensorFinisher = _sensorFinisher
sys.modules["mintsXU4.mintsSensorReader"] = mSR
mintsXU4.mintsSensorReader = mSR

import requests  # noqa: E402  (only its exception classes are used; the module chamber.py calls is replaced)
import mintsXU4.especChamber.chamber as chamber_mod  # noqa: E402
import runRoutineV8 as rr  # noqa: E402
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - fake clock: sleep() advances time at once
class FakeTime:
    def __init__(self, start=1800000000.0):
        self.now = start
        self.hooks = []           # fn(now) called after every sleep; may raise (Ctrl-C)

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += max(0.0, s)
        for h in list(self.hooks):
            h(self.now)
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - simulated ESPEC Web Controller (API v4) behind a fake requests module
class Rsp:
    def __init__(self, status, data=None):
        self.status_code, self._data, self.text = status, data, "" if status == 200 else "simulated failure"

    def json(self):
        return self._data


class FakeController:
    """PV follows the set point (3 C/min, RH 10 %/min); with the humidity system OFF the dew point is kept (it drops
    to the air T when the air is colder, i.e. frost)."""

    def __init__(self, clock, t_pv=22.0, rh_pv=30.0, op="standby"):
        self.clock, self.op, self.last = clock, op, clock.now
        self.t_set = self.t_pv = t_pv
        self.rh_set, self.rh_pv, self.humi_on = 15.0, rh_pv, False
        self.td = rh_dew(t_pv, rh_pv)
        self.dap, self.dap_group = False, "dap_1"
        self.heat_rate = self.cool_rate = 3.0
        self.rh_rate = 10.0
        self.fail = lambda t: False            # True: every request answers HTTP 500
        self.ignore_t = lambda v: False        # True: a temperature set point is silently not taken
        self.leave_constant_at = None
        self.rh_override = None                # fn(controller) -> reported RH PV or None
        self.posts = []                        # (t, command, json, t_set before the command)
        self.calls = []                        # (method, timeout)
        self.humi_log = [(clock.now, False)]
        self.dap_log = [(clock.now, False)]
        self.requests = types.SimpleNamespace(get=self.get, post=self.post, RequestException=requests.RequestException,
                                              exceptions=requests.exceptions)

    def advance(self):
        now = self.clock.now
        dt, self.last = (now - self.last) / 60.0, now
        if self.leave_constant_at is not None and now >= self.leave_constant_at and self.op == "constant":
            self.op = "standby"
        if self.op != "constant" or dt <= 0:
            return
        d = self.t_set - self.t_pv
        step = (self.heat_rate if d > 0 else self.cool_rate) * dt
        self.t_pv = self.t_set if abs(d) <= step else self.t_pv + math.copysign(step, d)
        if self.humi_on:
            d = self.rh_set - self.rh_pv
            self.rh_pv = self.rh_set if abs(d) <= self.rh_rate * dt else self.rh_pv + math.copysign(self.rh_rate * dt, d)
            self.td = rh_dew(self.t_pv, self.rh_pv)
        else:
            self.td = min(self.td, self.t_pv)
            self.rh_pv = rr.rh_for_dew(self.td, self.t_pv)

    def summary(self):
        rh = self.rh_override(self) if self.rh_override else None
        return {"conditions": {
            "status": {"datetime": "sim", "operation": self.op, "constant_key": 1, "program_step": None,
                       "program_time_step": "", "program_time": "", "program_key": None, "program_name": "",
                       "program": None, "program_counters": [], "running": self.op != "standby"},
            "temp": {"group": "loop", "enable": True, "set_value": self.t_set, "process_value": round(self.t_pv, 2),
                     "power": 0},
            "humi": {"group": "loop", "enable": self.humi_on, "set_value": self.rh_set,
                     "process_value": round(rh if rh is not None else self.rh_pv, 2), "power": 0},
            "time_signal_1": {"group": "ts1", "value": False},
            "dap": {"group": self.dap_group, "value": self.dap}},
            "programs": {str(i): {"name": "program %d" % i} for i in range(1, 6)}}

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", timeout))
        self.advance()
        if self.fail(self.clock.now):
            return Rsp(500)
        if url.endswith("/api/v4/"):
            return Rsp(200, {"chambers": {"uri": ["/api/v4/chambers/1"]}})
        return Rsp(200, self.summary())

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", timeout))
        self.advance()
        cmd = url.split("/chambers/", 1)[1].split("/", 1)[1]
        self.posts.append((self.clock.now, cmd, copy.deepcopy(json), self.t_set))
        if self.fail(self.clock.now):
            return Rsp(500)
        if cmd == "operations/start_constant":
            self.op = "constant"
        elif cmd == "operations/stop_chamber":
            self.op = "standby"
        elif cmd == "constants/constant_1":
            if "temp" in json and not self.ignore_t(json["temp"]["set_value"]):
                self.t_set = json["temp"]["set_value"]
            if "humi" in json:
                if "set_value" in json["humi"]:
                    self.rh_set = json["humi"]["set_value"]
                if json["humi"]["enable"] != self.humi_on:
                    self.humi_on = json["humi"]["enable"]
                    self.humi_log.append((self.clock.now, self.humi_on))
            if "dap" in json and json["dap"]["value"] != self.dap:
                self.dap = json["dap"]["value"]
                self.dap_log.append((self.clock.now, self.dap))
        return Rsp(200, {"result": "ok"})

    @staticmethod
    def state_at(log, t):
        v = log[0][1]
        for tt, x in log:
            if tt <= t:
                v = x
        return v


def rh_dew(t, rh):
    return rr.dew_point(t, max(rh, 0.1))
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - fake T640 (latest() on the fake clock) and fake operator
class FakeT640:
    """``values(now)`` gives the T640 reading; ``alive(now)`` False = no new read (the last one ages)."""

    def __init__(self, clock, values=None, alive=None):
        self.clock, self.routine = clock, None       # run() sets routine: PM2.5 follows the point's aerosol feed
        self.values = values or self.benign
        self.alive = alive or (lambda now: True)
        self.t_read, self.last, self.error = None, None, "never read"

    def benign(self, now):
        feed = self.routine.point.aerosol_feed if self.routine is not None else "aerosol"
        return {"sample_rh": 30.0, "box_t": 40.0, "asc_duty": 50.0, "fault": 0,
                "pm25": 0.1 if feed == "hepa_bypass" else 5.0}

    def latest(self):
        now = self.clock.now
        if self.alive(now):
            self.t_read, self.last = now, self.values(now)
        return self.t_read, self.last


class FakeOperator:
    """Answers ``answers[(kind, point)] = (word or None, delay_s)``; default: pass / go at once. ``safe_at`` sends
    "safe" once at that fake time."""

    def __init__(self, clock, answers=None, safe_at=None):
        self.clock, self.answers, self.safe_at = clock, dict(answers or {}), safe_at
        self.asked = []          # (time, kind, point)
        self.done = set()

    def poll(self, since, waiting=None):
        now = self.clock.now
        if self.safe_at is not None and now >= self.safe_at:
            self.safe_at = None
            return "safe"
        if not waiting:
            return None
        kind, point, t_since, choices = waiting
        key = (kind, point, t_since)
        if key not in self.done:
            self.done.add(key)
            self.asked.append((t_since, kind, point))
        word, delay = self.answers.get((kind, point), ("pass" if kind == "check" else "go", 0.0))
        if word is not None and now >= t_since + delay and (key, "answered") not in self.done:
            self.done.add((key, "answered"))
            return word
        return None
# END ADDED BY CLAUDE


# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - run the routine against the simulated controller, all output discarded
class Result:
    pass


def patches(clock, ctrl):
    return [mock.patch.object(chamber_mod, "requests", ctrl.requests), mock.patch.object(chamber_mod, "time", clock),
            mock.patch.object(rr, "time", clock)]


def make_chamber(clock, ctrl, **kw):
    return chamber_mod.Chamber("http://chamber.test", 1, "test-token-not-a-secret", **kw)


def run(point_names=None, start_point=None, skip_precycle=False, skip_bake=False, setup=None, hooks=(),
        operator_wait=False, t_pv=22.0, rh_pv=30.0, op="standby", wrap=None, t640="fake", answers=None, safe_at=None,
        state=None, mode="run", resumed=False):
    """Run one routine; returns a Result with outcome, ctrl, records, clock, routine, points, t640, operator.
    ``t640``: "fake" (benign readings), None (--no-t640) or fn(clock) -> a T640 object; ``state``: a StateFile."""
    points, stop_row, rules, sha = rr.load_schedule(rr.SCHEDULE_FILE)
    args = rr.parse_args([] + (["--start-point", start_point] if start_point else [])
                         + (["--skip-precycle"] if skip_precycle else []) + (["--skip-bake"] if skip_bake else []))
    sel, t_from0 = rr.select_points(points, args)
    if point_names is not None:
        sel = [p for p in sel if p.name in point_names]
    clock = FakeTime()
    ctrl = FakeController(clock, t_pv=t_pv, rh_pv=rh_pv, op=op)
    if setup:
        setup(ctrl, clock)
    mSR.records, mSR.clock = [], clock
    res = Result()
    res.ctrl, res.clock, res.points, res.rules = ctrl, clock, sel, rules
    res.t640 = FakeT640(clock) if t640 == "fake" else (t640(clock) if t640 else None)
    res.operator = FakeOperator(clock, answers, safe_at)
    ps = patches(clock, ctrl)
    for p in ps:
        p.start()
    try:
        with open(os.devnull, "w") as devnull, mock.patch("sys.stdout", devnull), \
                mock.patch("builtins.input", side_effect=AssertionError("blocking input() in the routine")):
            chamber = make_chamber(clock, ctrl, request_timeout=rr.REQUEST_TIMEOUT_S)
            res.pings = []
            routine = rr.V8Routine(chamber, mSR, sel, rules, sha, t_from0=t_from0, operator_wait=operator_wait,
                                   t640=res.t640, operator=res.operator, state=state,
                                   watchdog=lambda m: res.pings.append((clock.now, m)), mode=mode, resumed=resumed)
            if res.t640 is not None:
                res.t640.routine = routine
            if wrap:
                wrap(routine)
            clock.hooks.extend(hooks)
            res.outcome = routine.run()
    finally:
        for p in ps:
            p.stop()
    res.routine, res.records = routine, list(mSR.records)
    return res


def recs(res, name):
    return [(t, d) for t, n, d in res.records if n == name]


def events(res, event_id):
    return [(t, d["point"]) for t, d in recs(res, "BTL433ESC001RTNV8") if d["eventID"] == event_id]


def humidity_posts(res):
    return [(t, j["humi"], t_set) for t, cmd, j, t_set in res.ctrl.posts if cmd == "constants/constant_1" and "humi" in j]


def last_commands(res, n=2):
    return [(cmd, j) for _, cmd, j, _ in res.ctrl.posts[-n:]]
# END ADDED BY CLAUDE
