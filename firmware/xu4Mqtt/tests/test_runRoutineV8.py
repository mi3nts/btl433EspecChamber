"""
Hermetic tests of runRoutineV8.py (v8 routine update, 2026-10-20). NEW FILE on branch feature/v8-routine-update.

PROVENANCE. Written by Claude for this branch. The cases are the list of task section 7; the expected numbers come
from v8/schedule.tsv and the Magnus formulas copied from Calibration calib/chamber/psychro.py.

Run from firmware/xu4Mqtt:  python3 -m unittest discover -s tests -v
No network, no MQTT, no credentials.yml: the chamber is the simulated controller of tests/_fakes.py and time is fake.
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - the routine's tests
import ast
import io
import os
import signal
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fakes as F
from _fakes import rr

ALL = ["pre1", "pre2", "pre3"] + [str(i) for i in range(1, 29)] + ["bake"]


class ScheduleAndPlan(unittest.TestCase):
    def setUp(self):
        self.points, self.stop_row, self.rules, self.sha = rr.load_schedule(rr.SCHEDULE_FILE)

    def test_points_are_the_tsv_rows_in_file_order(self):
        self.assertEqual([p.name for p in self.points], ALL)
        self.assertEqual(self.stop_row["tag"], "stop")

    def test_schedule_is_the_verbatim_copy(self):
        self.assertTrue(self.sha.startswith("92ee4e0873b00c0e"))
        with open(os.path.join(F.XU4, "v8", "README.md"), encoding="utf-8") as f:
            self.assertIn(self.sha, f.read())

    def test_rule_numbers_read_from_the_rule_rows(self):
        r = self.rules
        self.assertEqual((r["cap"], r["tick_s"], r["hold_over"], r["hold_min"], r["hold_below"]), (19, 10, 1, 2, 1))
        self.assertEqual((r["abort_over"], r["abort_min"]), (2, 2))
        self.assertEqual((r["pulldown_T"], r["pulldown_min"], r["no_reading_min"], r["unconfirmed_min"]), (-18, 90, 5, 5))
        self.assertEqual((r["safe_lo"], r["safe_hi"], r["safe_up"], r["safe_down"], r["safe_rh"], r["safe_dry_min"]),
                         (22, 30, 1.0, 0.6, 15, 60))
        # v8 must-fix review (2026-10-22) - the T640 parts of the excursion row and the stale rule
        self.assertEqual((r["hold_srh"], r["hold_srh_min"], r["hold_duty"], r["hold_box"]), (45, 5, 95, 3))
        self.assertEqual(r["abort_srh"], [(60, 10), (75, 2), (60, 5)])
        self.assertEqual((r["fault_min"], r["fault_srh"], r["t640_stale_min"]), (5, 45, 5))

    def test_plan_prints_every_point_dew_point_and_total_and_contacts_nothing(self):
        out = io.StringIO()
        boom = mock.Mock(side_effect=AssertionError("--plan made a request"))
        with redirect_stdout(out), mock.patch.object(F.chamber_mod, "requests", mock.Mock(get=boom, post=boom)):
            self.assertEqual(rr.main(["--plan"]), 0)
        text = out.getvalue()
        for p in self.points:
            self.assertRegex(text, r"\n\s*\d+\s+%s\s" % p.name)
            if p.rh_set is not None:
                self.assertIn("%.1f" % rr.dew_point(p.t_set, p.rh_set), text)
        self.assertIn("Total 23.75 h (1425 min)", text)   # v8 must-fix 1: the TSV's own pre1 -> stop span
        self.assertRegex(text, r"\n\s*14\s+11\s+20\s+15\s+-7.5\s+0.0\s+13.0\s")   # point 11: no ramp, D = 13 min
        self.assertIn(self.sha, text)
        self.assertIn("at or below the 19 C tube cap", text)

    def test_plan_refuses_a_dew_point_above_the_cap(self):
        with open(rr.SCHEDULE_FILE, "rb") as f:
            raw = f.read().decode("utf-8")
        bad = raw.replace("\n13\t30\t50\t", "\n13\t30\t95\t")      # 30 C / 95 % -> Td 29.1 C > 19 C
        self.assertNotEqual(bad, raw)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "schedule.tsv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(bad)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(rr.main(["--plan"], schedule_path=path), 2)
                self.assertEqual(rr.main(["--state-dir", d], schedule_path=path), 2)   # the real run refuses before any import
        self.assertIn("REFUSED: the dew point of points 13", out.getvalue())

    def test_point_selection(self):
        names = lambda argv: [p.name for p in rr.select_points(self.points, rr.parse_args(argv))[0]]  # noqa: E731
        self.assertEqual(names([]), ALL)
        self.assertEqual(names(["--skip-precycle"]), ALL[3:])
        self.assertEqual(names(["--skip-bake"]), ALL[:-1])
        self.assertEqual(names(["--start-point", "12"]), ALL[ALL.index("12"):])
        self.assertEqual(rr.select_points(self.points, rr.parse_args(["--start-point", "12"]))[1], 20.0)
        with self.assertRaises(SystemExit):
            names(["--start-point", "29"])
        with self.assertRaises(SystemExit):
            names(["--start-point", "pre2", "--skip-precycle"])

    def test_python_3_8_syntax(self):
        for rel in ("runRoutineV8.py", "benchTestV8.py", "publishV8.py", "parkChamberV8.py",
                    os.path.join("mintsXU4", "especChamber", "chamber.py")):
            with open(os.path.join(F.XU4, rel), encoding="utf-8") as f:
                ast.parse(f.read(), filename=rel, feature_version=(3, 8))

    def test_sigterm_handler_is_ctrl_c(self):
        with self.assertRaises(KeyboardInterrupt):
            rr.raise_interrupt(15, None)

    def test_sigterm_and_sighup_both_park_the_chamber(self):      # v8 must-fix 5
        old = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
        try:
            rr.install_signal_handlers()
            self.assertIs(signal.getsignal(signal.SIGTERM), rr.raise_interrupt)
            self.assertIs(signal.getsignal(signal.SIGHUP), rr.raise_interrupt)
        finally:
            for s, h in old.items():
                signal.signal(s, h)


class NormalRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = F.run(operator_wait=True)
        cls.arrive = dict((p, t) for t, p in F.events(cls.res, 2))
        cls.start = dict((p, t) for t, p in F.events(cls.res, 1))

    def test_completes_and_visits_every_point_in_tsv_order(self):
        self.assertEqual(self.res.outcome, "complete")
        self.assertEqual([p for _, p in F.events(self.res, 1)], ALL)
        self.assertEqual([p for _, p in F.events(self.res, 2)], ALL)
        self.assertEqual([p for _, p in F.events(self.res, 6)], ALL)

    def test_ends_with_humidity_off_then_stop(self):
        self.assertEqual(F.last_commands(self.res), [("constants/constant_1", {"humi": {"group": "loop", "enable": False}}),
                                                     ("operations/stop_chamber", {"group": "standby"})])
        self.assertEqual(self.res.ctrl.op, "standby")

    def test_rtnchg_sequence(self):
        seq = [(d["changeID"], d["iteration"]) for _, d in F.recs(self.res, "BTL433ESC001RTNCHG")]
        n = len(ALL)
        self.assertEqual(seq, [(1, 0)] + [(10, i) for i in range(1, n + 1)] + [(2, n)])
        labels = {d["changeID"]: d["changeLabel"] for _, d in F.recs(self.res, "BTL433ESC001RTNCHG")}
        self.assertEqual(labels, {1: "Routine Started", 10: "Routine Holding", 2: "Routine Ended"})
        self.assertEqual(list(F.recs(self.res, "BTL433ESC001RTNCHG")[0][1]),
                         ["dateTime", "changeID", "changeLabel", "iteration", "success"])

    def test_rtnprgv2_once_per_point_with_off_as_minus_100(self):
        rows = [d for _, d in F.recs(self.res, "BTL433ESC001RTNPRGV2")]
        self.assertEqual([d["rotuingIteration"] for d in rows], list(range(1, len(ALL) + 1)))
        by = dict(zip(ALL, rows))
        self.assertEqual((by["2"]["entryHumidity"], by["2"]["entryHC"]), (-100, 0))
        self.assertEqual((by["12"]["entryHumidity"], by["12"]["entryHC"]), (35.0, 1))
        self.assertEqual(list(rows[0]), ["dateTime", "rotuingPercentage", "rotuingIteration", "rotuingLength",
                                         "entryTemperature", "entryHumidity", "entryHC", "success"])

    def test_rtnv8_fields(self):
        d = F.recs(self.res, "BTL433ESC001RTNV8")[0][1]
        self.assertEqual(list(d), ["dateTime", "eventID", "eventLabel", "point", "tag", "temperatureSet", "humiditySet",
                                   "humiditySystem", "dryAirPurge", "aerosolFeed", "holdMin", "rampRate", "gsBand",
                                   "scheduleSha", "detail"])
        self.assertTrue(d["scheduleSha"].startswith("92ee4e08"))
        self.assertLess(len(F.recs(self.res, "BTL433ESC001RTNV8")), 10 * len(ALL))     # events only, not ticks

    def test_no_rh_set_point_above_the_dew_point_cap(self):
        posts = [(h["set_value"], t_set) for _, h, t_set in F.humidity_posts(self.res) if "set_value" in h]
        self.assertGreater(len(posts), 100)
        for rh, t_set in posts:
            self.assertLessEqual(rr.dew_point(t_set, rh), 19.0 + 1e-9, (rh, t_set))

    def test_humidity_off_rows_stay_off(self):
        for name in ("2", "3", "25"):
            t0, t1 = self.start[name] + 0.5, self.start[ALL[ALL.index(name) + 1]]
            ons = [t for t, on in self.res.ctrl.humi_log if on and t0 <= t < t1]
            self.assertEqual(ons, [], name)
            self.assertFalse(F.FakeController.state_at(self.res.ctrl.humi_log, t0))

    def test_dry_warm_ups_switch_humidity_on_after_humidify_after_min(self):
        dry = [p for p in self.res.points if p.rh_set is not None and not p.ramp_humidity]
        self.assertEqual([p.name for p in dry], ["6", "7", "26", "28"])
        log = self.res.ctrl.humi_log
        for p in dry:
            on_at = self.arrive[p.name] + p.humidify_after_min * 60.0       # from arrival = the end of D (cycle.py:903)
            self.assertFalse(F.FakeController.state_at(log, self.start[p.name] + 0.5), p.name)
            self.assertEqual([t for t, on in log if on and self.start[p.name] <= t < on_at], [], p.name)
            first_on = min(t for t, on in log if on and t >= on_at)
            self.assertLess(first_on - on_at, 12.0, p.name)
        self.assertEqual(sorted(p for _, p in F.events(self.res, 3)), sorted(p.name for p in dry))

    # v8 must-fix review (2026-10-22): CHANGED - as the runner (cycle.py:871-885): with T changing the RH set point
    # follows the dew-point trajectory interpolated with T; an RH-only change goes linearly in RH over the window D
    def test_humid_transitions_follow_the_runner(self):
        pts, traj, linear = self.res.points, 0, 0
        for k, p in enumerate(pts[1:], start=1):
            prev = pts[k - 1]
            if not (p.ramp_humidity and p.rh_set is not None and prev.rh_set is not None and prev.humidity_on):
                continue
            td0, td1 = rr.dew_point(prev.t_set, prev.rh_set), rr.dew_point(p.t_set, p.rh_set)
            window_s = rr.transition_min(p, abs(p.t_set - prev.t_set) / p.ramp_rate) * 60.0
            for t, h, t_set in F.humidity_posts(self.res):
                if not (self.start[p.name] <= t < self.arrive[p.name] and "set_value" in h):
                    continue
                if p.t_set != prev.t_set:
                    f = (t_set - prev.t_set) / (p.t_set - prev.t_set)
                    self.assertGreaterEqual(f, -1e-9)
                    self.assertAlmostEqual(rr.dew_point(t_set, h["set_value"]), td0 + (td1 - td0) * f, delta=0.15,
                                           msg=(p.name, t_set, h))
                    traj += 1
                else:
                    f = min(1.0, (t - self.start[p.name]) / window_s)
                    self.assertAlmostEqual(h["set_value"], prev.rh_set + (p.rh_set - prev.rh_set) * f, delta=0.3,
                                           msg=(p.name, t, h))
                    linear += 1
        self.assertGreater(traj, 80)      # 92 since the Frog schedule (3ca7f85) dropped the warm-humid ladder
        self.assertGreater(linear, 20)

    def test_holds_start_at_the_end_of_the_schedule_window(self):        # v8 must-fix 1
        for p in self.res.points[1:]:
            prev = self.res.points[self.res.points.index(p) - 1]
            ramp_min = abs(p.t_set - prev.t_set) / p.ramp_rate
            self.assertGreaterEqual(self.arrive[p.name] - self.start[p.name], rr.transition_min(p, ramp_min) * 60.0,
                                    p.name)
        for name in ("pre2", "pre3", "11", "20", "21", "22", "24", "28"):       # the early holds of the review
            p = next(q for q in self.res.points if q.name == name)
            self.assertAlmostEqual(self.arrive[name] - self.start[name], p.window_min * 60.0, delta=75.0, msg=name)

    def test_rh_only_change_is_spread_over_the_window(self):             # point 11: 20 C, 35 -> 15 % over 13 min
        rh = [h["set_value"] for t, h, _ in F.humidity_posts(self.res)
              if self.start["11"] <= t < self.arrive["11"] and "set_value" in h]
        self.assertGreaterEqual(len(rh), 10)
        self.assertEqual(rh, sorted(rh, reverse=True))
        self.assertGreater(rh[0], 30.0)
        self.assertEqual(rh[-1], 15.0)

    def test_purge_follows_the_row(self):
        log = self.res.ctrl.dap_log
        for p in self.res.points:
            self.assertEqual(F.FakeController.state_at(log, self.start[p.name] + 15.0), p.purge, p.name)
            self.assertEqual(F.FakeController.state_at(log, self.arrive[p.name]), p.purge, p.name)

    def test_expanded_summary_every_10_s(self):
        t = [x for x, _ in F.recs(self.res, "BTL433ESC001TMPRT")]
        gaps = [b - a for a, b in zip(t, t[1:])]
        self.assertLessEqual(max(gaps), 10.0 + 1e-6)
        stops = sum(1 for _, cmd, _, _ in self.res.ctrl.posts if cmd == "operations/stop_chamber")
        # every summary is expanded (DAP + PRGRM) except the one Lakitha's stop_chamber reads itself
        self.assertEqual(len(F.recs(self.res, "BTL433ESC001PRGRM")), len(t) - stops)

    # v8 must-fix review (2026-10-22): CHANGED - the feed change and the three pre-cycle checks are asked, never input()
    def test_operator_asked_at_each_pre_cycle_check_and_once_at_the_feed_change(self):
        self.assertEqual([(k, p) for _, k, p in self.res.operator.asked],
                         [("check", "pre1"), ("check", "pre2"), ("feed", "pre3"), ("check", "pre3")])
        self.assertEqual([p for _, p in F.events(self.res, 13)], ["pre1", "pre2", "pre3"])
        self.assertEqual([p for _, p in F.events(self.res, 16)], ["pre3"])
        self.assertLessEqual(F.events(self.res, 16)[0][0], self.start["pre3"])

    def test_pull_down_reached_in_time_and_guaranteed_soaks_held(self):
        self.assertEqual(F.events(self.res, 5), [])
        self.assertEqual(F.events(self.res, 7), [])


class StartPointAndRestart(unittest.TestCase):
    def test_start_point_and_iteration_restart(self):
        for _ in range(2):
            res = F.run(start_point="23", t_pv=10.0, rh_pv=35.0)
            self.assertEqual(res.outcome, "complete")
            self.assertEqual([p for _, p in F.events(res, 1)], ALL[ALL.index("23"):])
            seq = [(d["changeID"], d["iteration"]) for _, d in F.recs(res, "BTL433ESC001RTNCHG")]
            self.assertEqual(seq[:3], [(1, 0), (10, 1), (10, 2)])

    def test_skip_precycle_and_bake(self):
        res = F.run(skip_precycle=True, skip_bake=True, point_names=["1", "2", "3", "28"])
        self.assertEqual([p for _, p in F.events(res, 2)], ["1", "2", "3", "28"])
        self.assertEqual(res.outcome, "complete")

    def test_first_step_rule_rise_from_humid_air_ramps_dry(self):
        res = F.run(start_point="12", point_names=["12"], t_pv=20.0, rh_pv=75.0)   # 20 -> 35 C from 75 % RH
        t_start, t_arr = F.events(res, 1)[0][0], F.events(res, 2)[0][0]
        log = res.ctrl.humi_log
        self.assertFalse(F.FakeController.state_at(log, t_start + 0.5))
        first_on = min(t for t, on in log if on and t > t_start)
        self.assertGreaterEqual(first_on, t_arr + 10 * 60.0)     # the schedule's longest humidify_after_min
        self.assertLess(first_on, t_arr + 10 * 60.0 + 12.0)

    def test_first_step_rule_humid_pull_down_below_zero_ramps_dry(self):
        res = F.run(start_point="4", point_names=["4"], t_pv=22.0, rh_pv=50.0)    # 22 -> -2.5 C, 70 %
        t_start, t_arr = F.events(res, 1)[0][0], F.events(res, 2)[0][0]
        self.assertEqual([t for t, on in res.ctrl.humi_log if on and t_start <= t < t_arr], [])
        self.assertTrue(F.FakeController.state_at(res.ctrl.humi_log, t_arr + 12.0))


class DewPointHold(unittest.TestCase):
    def test_hold_steps_rh_down_and_never_re_raises_within_the_point(self):
        def setup(ctrl, clock):
            seen = {}

            def wet(c):   # the chamber PV reads 56 % for 3 min, one minute after point 13's set point is reached
                if abs(c.t_set - 30.0) < 0.05:
                    seen.setdefault("t", clock.now)
                    return 56.0 if 60.0 < clock.now - seen["t"] <= 240.0 else None   # Td 20.3 C: over cap + 1, under cap + 2
                return None
            ctrl.rh_override = wet
        res = F.run(start_point="12", point_names=["12", "13", "14"], t_pv=35.0, rh_pv=30.0, setup=setup)
        self.assertEqual(res.outcome, "complete")
        holds = F.events(res, 4)
        self.assertEqual([p for _, p in holds], ["13"])
        t_hold, t14 = holds[0][0], F.events(res, 1)[2][0]
        target = round(rr.rh_for_dew(18.0, 30.0), 1)
        after = [h["set_value"] for t, h, _ in F.humidity_posts(res) if t_hold <= t < t14 and "set_value" in h]
        self.assertTrue(after)
        self.assertAlmostEqual(after[0], target, delta=0.1)
        self.assertLessEqual(max(after), after[0])
        before = [h["set_value"] for t, h, _ in F.humidity_posts(res) if t < t_hold and "set_value" in h]
        self.assertEqual(before[-1], 50.0)
        rh14 = [h["set_value"] for t, h, _ in F.humidity_posts(res) if t >= t14 and "set_value" in h]
        self.assertIn(65.0, rh14)                  # the hold ends with the point


    # Frog schedule (Calibration 3ca7f85): ABORT at cap + 2 C for 2 min, the same 2 min as the HOLD at cap + 1 C. The ABORT
    # is evaluated first (as cycle.py:655-668), so a dew point that jumps past cap + 2 C aborts with no HOLD before it.
    def test_dew_point_above_cap_plus_2_for_2_min_aborts_to_safe(self):
        def setup(ctrl, clock):
            ctrl.rh_override = lambda c: 95.0 if abs(c.t_set - 30.0) < 0.05 else None   # Td 29.1 C at 30 C
        res = F.run(start_point="12", point_names=["12", "13", "14"], t_pv=35.0, rh_pv=30.0, setup=setup)
        self.assertEqual(res.outcome, "safe")
        self.assertEqual(F.events(res, 4), [])
        self.assertEqual([p for _, p in F.events(res, 7)], ["13"])
        first_30 = min(t for t, cmd, j, _ in res.ctrl.posts if "temp" in (j or {}) and abs(j["temp"]["set_value"] - 30.0) < 0.05)
        self.assertAlmostEqual(F.events(res, 7)[0][0] - first_30, 2 * 60.0, delta=21.0)
        self.assertIn("> 21 C for 2 min", [d for _, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 7][0]["detail"])
        self.assertEqual(F.last_commands(res)[-1], ("operations/stop_chamber", {"group": "standby"}))


class ExitPaths(unittest.TestCase):
    def assertSafeEnd(self, res):
        self.assertEqual(F.last_commands(res), [("constants/constant_1", {"humi": {"group": "loop", "enable": False}}),
                                                ("operations/stop_chamber", {"group": "standby"})])
        self.assertEqual(F.recs(res, "BTL433ESC001RTNCHG")[-1][1]["changeID"], 2)

    def test_ctrl_c_humidity_off_then_stop_at_once(self):
        def hook(now, fired=[]):   # noqa: B006 - one-shot
            if now > 1800000000.0 + 3 * 3600 and not fired:
                fired.append(now)
                raise KeyboardInterrupt
        res = F.run(hooks=[hook])
        self.assertEqual(res.outcome, "interrupted")
        self.assertSafeEnd(res)
        self.assertLess(res.ctrl.posts[-1][0] - (1800000000.0 + 3 * 3600), 30.0)
        self.assertEqual([p for _, p in F.events(res, 12)], ["2"])

    def test_unexpected_exception_goes_through_safe(self):
        def wrap(routine):
            orig = routine.run_point

            def run_point(p, prev, first):
                if p.name == "3":
                    raise RuntimeError("simulated bug")
                return orig(p, prev, first)
            routine.run_point = run_point
        res = F.run(wrap=wrap)
        self.assertEqual(res.outcome, "error, safe")
        self.assertEqual(len(F.events(res, 8)), 1)
        self.assertEqual(len(F.events(res, 9)), 1)
        self.assertSafeEnd(res)

    def test_no_reading_aborts_to_safe(self):
        t_fail = 1800000000.0 + 4.4 * 3600        # a 6-min outage during point 3

        def setup(ctrl, clock):
            ctrl.fail = lambda t: t_fail <= t < t_fail + 6 * 60.0
        res = F.run(setup=setup)
        self.assertEqual(res.outcome, "safe")
        self.assertEqual([p for _, p in F.events(res, 7)], ["3"])
        t_abort = F.events(res, 7)[0][0]
        self.assertAlmostEqual(t_abort - t_fail, 5 * 60.0, delta=11.0)
        # SAFE: humidity OFF first, then the dry-out at 15 % with the purge ON, then STOP
        safe_posts = [(cmd, j) for t, cmd, j, _ in res.ctrl.posts if t >= t_abort]
        self.assertEqual(safe_posts[0], ("constants/constant_1", {"humi": {"group": "loop", "enable": False}}))
        self.assertIn(("constants/constant_1", {"humi": {"group": "loop", "enable": True, "set_value": 15.0,
                                                         "range": [10, 95]}}), safe_posts)
        self.assertIn(("constants/constant_1", {"dap": {"group": "dap_1", "value": True}}), safe_posts)
        # the T640 reads 30 % sample RH and the chamber dries to Td < 5 C: the early end of the safe row
        (t_safe_end, _), = F.events(res, 9)
        self.assertLess(t_safe_end - t_abort, 60 * 60.0)
        self.assertEqual([d["detail"] for _, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 9],
                         ["dry for 10 min"])
        self.assertSafeEnd(res)

    def test_no_reading_during_safe_is_an_emergency_stop(self):
        def setup(ctrl, clock):
            ctrl.fail = lambda t: t > 1800000000.0 + 4 * 3600
        res = F.run(setup=setup)
        self.assertEqual(res.outcome, "safe_failed")
        cmds = [cmd for _, cmd, _, _ in res.ctrl.posts[-4:]]
        self.assertEqual(cmds, ["constants/constant_1", "constants/constant_1", "operations/stop_chamber",
                                "operations/stop_chamber"])          # humidity OFF and STOP, each tried twice
        self.assertEqual(len(F.events(res, 12)), 1)

    def test_unconfirmed_set_point_aborts_to_safe(self):
        def setup(ctrl, clock):
            ctrl.ignore_t = lambda v: v < 15.0
        res = F.run(start_point="2", point_names=["2", "3"], setup=setup)
        self.assertEqual(res.outcome, "safe")
        t_abort = F.events(res, 7)[0][0]
        t_first_ignored = min(t for t, cmd, j, _ in res.ctrl.posts if "temp" in (j or {}) and j["temp"]["set_value"] < 15)
        self.assertAlmostEqual(t_abort - t_first_ignored, 5 * 60.0, delta=12.0)
        resent = [t for t, cmd, j, _ in res.ctrl.posts if "temp" in (j or {}) and j["temp"]["set_value"] < 15]
        self.assertGreaterEqual(len(resent), 5)             # re-sent at every 60-s update until the abort
        self.assertSafeEnd(res)

    def test_pull_down_too_slow_aborts_to_safe(self):
        def setup(ctrl, clock):
            ctrl.cool_rate = 0.3          # 22 -> -18 C would take 133 min
        res = F.run(start_point="2", point_names=["2", "3"], setup=setup)
        self.assertEqual(res.outcome, "safe")
        t_start, t_abort = F.events(res, 1)[0][0], F.events(res, 7)[0][0]
        self.assertAlmostEqual(t_abort - t_start, 90 * 60.0, delta=11.0)
        self.assertSafeEnd(res)

    def test_chamber_leaving_constant_sends_nothing_more(self):
        t_leave = 1800000000.0 + 5 * 3600

        def setup(ctrl, clock):
            ctrl.leave_constant_at = t_leave
        res = F.run(setup=setup)
        self.assertEqual(res.outcome, "left_constant")
        self.assertEqual([t for t, _, _, _ in res.ctrl.posts if t >= t_leave], [])
        self.assertEqual(len(F.events(res, 11)), 1)
        self.assertEqual(F.recs(res, "BTL433ESC001RTNCHG")[-1][1]["changeID"], 2)

    def test_panel_programme_is_refused_without_a_command(self):
        res = F.run(op="program")
        self.assertEqual(res.outcome, "refused")
        self.assertEqual(res.ctrl.posts, [])
# END ADDED BY CLAUDE


if __name__ == "__main__":
    unittest.main()
