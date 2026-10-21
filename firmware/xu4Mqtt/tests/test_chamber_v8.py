"""
Hermetic tests of the additive chamber.py methods and benchTestV8.py's refusal (v8 routine update, 2026-10-20).
NEW FILE on branch feature/v8-routine-update. Written by Claude; the expected payloads are those of Calibration
calib/chamber/espec.py:10-11 (humidity ON/OFF, dry-air purge). No network: requests is the simulated controller.
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - chamber.py and bench-test tests
import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fakes as F

URL = "http://chamber.test/api/v4/chambers/1/constants/constant_1"


class ChamberMethods(unittest.TestCase):
    def setUp(self):
        self.clock = F.FakeTime()
        self.ctrl = F.FakeController(self.clock, op="constant")
        F.mSR.records, F.mSR.clock = [], self.clock
        self.ps = F.patches(self.clock, self.ctrl)
        for p in self.ps:
            p.start()
        self.out = open(os.devnull, "w")
        self.stdout = mock.patch("sys.stdout", self.out)
        self.stdout.start()

    def tearDown(self):
        self.stdout.stop()
        self.out.close()
        for p in self.ps:
            p.stop()

    def chng(self):
        return [d for _, d in F.recs(self, "BTL433ESC001CHNG")]

    records = property(lambda self: F.mSR.records)

    def test_old_callers_unchanged_no_timeout_by_default(self):
        c = F.make_chamber(self.clock, self.ctrl)
        self.assertTrue(c.set_temperature_value(25.0))
        self.assertEqual(self.ctrl.posts[-1][1:3], ("constants/constant_1", {"temp": {"group": "loop", "set_value": 25.0,
                                                                                       "range": [-20, 180]}}))
        self.assertTrue(c.set_humidity_value(40.0))
        self.assertEqual(self.ctrl.posts[-1][2], {"humi": {"group": "loop", "enable": True, "set_value": 40.0,
                                                           "range": [10, 95]}})
        self.assertEqual({t for _, t in self.ctrl.calls}, {None})
        self.assertEqual(c.change_mapping[10], "Temperature Set")
        self.assertEqual(c.change_mapping[52], "Routine Incrimented")

    def test_request_timeout_reaches_both_requests_calls(self):
        c = F.make_chamber(self.clock, self.ctrl, request_timeout=10)
        c.set_humidity_enabled(True)
        self.assertEqual({m for m, _ in self.ctrl.calls}, {"GET", "POST"})
        self.assertEqual({t for _, t in self.ctrl.calls}, {10})

    def test_set_humidity_enabled_payload_and_chng(self):
        c = F.make_chamber(self.clock, self.ctrl)
        for state in (True, False):
            self.assertTrue(c.set_humidity_enabled(state))
            self.assertEqual(self.ctrl.posts[-1][1:3], ("constants/constant_1", {"humi": {"group": "loop", "enable": state}}))
            d = self.chng()[-1]
            self.assertEqual((d["changeID"], d["changeLabel"], d["newValue"], d["success"]),
                             (13, "Humidity System Set", int(state), 1))
            self.assertEqual(list(d), ["dateTime", "changeID", "changeLabel", "newValue", "success"])

    def test_set_dry_air_purge_payload_uses_the_summary_group(self):
        self.ctrl.dap_group = "loop_dap_7"
        c = F.make_chamber(self.clock, self.ctrl)
        self.assertTrue(c.set_dry_air_purge(True))
        self.assertEqual(self.ctrl.posts[-1][1:3], ("constants/constant_1", {"dap": {"group": "loop_dap_7", "value": True}}))
        d = self.chng()[-1]
        self.assertEqual((d["changeID"], d["changeLabel"], d["newValue"]), (14, "Dry Air Purge Set", 1))

    def test_set_dry_air_purge_refuses_without_a_dap_group(self):
        self.ctrl.fail = lambda t: True          # the summary never arrives, so no DAP group is known
        c = F.make_chamber(self.clock, self.ctrl)
        self.assertFalse(c.set_dry_air_purge(True))
        self.assertEqual(self.ctrl.posts, [])

    def test_write_streams_unchanged(self):
        F.make_chamber(self.clock, self.ctrl)
        names = [n for _, n, _ in F.mSR.records]
        self.assertEqual(names, ["BTL433ESC001STATUS", "BTL433ESC001TMPRT", "BTL433ESC001HMDTY", "BTL433ESC001DAP",
                                 "BTL433ESC001DAP", "BTL433ESC001PRGRM"])   # the time signal still goes to DAP (reported)
        fields = {n: list(d) for _, n, d in F.mSR.records}
        self.assertEqual(fields["BTL433ESC001TMPRT"], ["dateTime", "temperatureGroup", "enabled", "setValue",
                                                       "processValue", "power"])
        self.assertEqual(fields["BTL433ESC001HMDTY"], ["dateTime", "humidityGroup", "enabled", "setValue",
                                                       "processValue", "power"])


class BenchTestRefusal(unittest.TestCase):
    def test_refuses_without_the_operator_flag_and_sends_nothing(self):
        import benchTestV8
        boom = mock.Mock(side_effect=AssertionError("the bench test made a request"))
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(F.chamber_mod, "requests", mock.Mock(get=boom, post=boom)):
            self.assertEqual(benchTestV8.main([]), 2)
        self.assertIn("Refused", out.getvalue())
# END ADDED BY CLAUDE


if __name__ == "__main__":
    unittest.main()
