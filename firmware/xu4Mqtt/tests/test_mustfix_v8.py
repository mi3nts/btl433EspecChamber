"""
Hermetic tests of the v8 must-fix review (2026-10-22). NEW FILE on branch feature/v8-routine-update.

PROVENANCE. Written by Claude. One class per must-fix item (the window D has its tests in test_runRoutineV8.py's
NormalRun, against the full simulated run). No network: the chamber is tests/_fakes.py's simulated controller, the
T640 a fake (or, for the Modbus client, a Modbus/TCP server on 127.0.0.1), MQTT a recording function.

Run from firmware/xu4Mqtt:  python3 -m unittest discover -s tests -v
"""

# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - tests of must-fixes 2-5
import io
import json
import os
import socket
import socketserver
import struct
import tempfile
import threading
import types
import unittest
from collections import OrderedDict
from contextlib import redirect_stdout
from unittest import mock

import _fakes as F
from _fakes import rr

T0 = 1800000000.0
HUMID = dict(start_point="16", point_names=["16", "17", "18"], t_pv=20.0, rh_pv=30.0)   # 35/45 -> 32.5/55 -> 30/65


def t640_with(values_at_17, base=None):
    """A T640 whose readings change once point 17's T set point (32.5 C) is in force."""
    box = {}

    def setup(ctrl, clock):
        box["ctrl"] = ctrl

    def make(clock):
        def values(now):
            v = dict(base or {"sample_rh": 30.0, "box_t": 40.0, "asc_duty": 50.0, "fault": 0, "pm25": 5.0})
            if abs(box["ctrl"].t_set - 32.5) < 0.05:
                v.update(values_at_17(box["ctrl"], now))
            return v
        return F.FakeT640(clock, values=values)
    return setup, make


def first_at_17(res):
    """When point 17's T set point first reached the chamber."""
    return min(t for t, cmd, j, _ in res.ctrl.posts if "temp" in (j or {}) and abs(j["temp"]["set_value"] - 32.5) < 0.05)


class T640Rules(unittest.TestCase):                       # must-fix 2
    def test_sample_rh_above_75_for_2_min_aborts_to_safe(self):
        setup, make = t640_with(lambda c, now: {"sample_rh": 80.0})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "safe")
        (t_abort, point), = F.events(res, 7)
        self.assertEqual(point, "17")
        self.assertAlmostEqual(t_abort - first_at_17(res), 120.0, delta=21.0)
        self.assertIn("T640 sample RH 80.0 % > 75 %", F.recs(res, "BTL433ESC001RTNV8")[-4][1]["detail"]
                      + "".join(d["detail"] for _, d in F.recs(res, "BTL433ESC001RTNV8")))

    def test_sample_rh_above_60_for_5_min_aborts_to_safe(self):
        setup, make = t640_with(lambda c, now: {"sample_rh": 65.0})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "safe")
        self.assertAlmostEqual(F.events(res, 7)[0][0] - first_at_17(res), 300.0, delta=21.0)

    def test_sample_rh_above_45_with_the_asc_heater_saturated_holds(self):
        setup, make = t640_with(lambda c, now: {"sample_rh": 50.0, "asc_duty": 97.0})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "complete")
        holds = [(t, d["detail"]) for t, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 4]
        self.assertEqual(len(holds), 1)
        self.assertIn("T640 sample RH 50.0 % > 45 %", holds[0][1])
        self.assertAlmostEqual(holds[0][0] - first_at_17(res), 300.0, delta=25.0)
        target = round(rr.rh_for_dew(22.0, 32.5), 1)
        after = [h["set_value"] for t, h, _ in F.humidity_posts(res)
                 if holds[0][0] <= t < F.events(res, 1)[2][0] and "set_value" in h]
        self.assertAlmostEqual(after[0], target, delta=0.1)

    def test_sample_rh_above_45_without_the_heater_saturated_does_not_hold(self):
        setup, make = t640_with(lambda c, now: {"sample_rh": 50.0, "asc_duty": 80.0})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual((res.outcome, F.events(res, 4)), ("complete", []))

    def test_chamber_dew_point_near_the_box_temperature_holds(self):
        # point 17 is 32.5 C / 55 %: Td 22.3 C > box 25 C - 3 C
        setup, make = t640_with(lambda c, now: {"box_t": 25.0} if c.humi_on else {})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "complete")
        details = [d["detail"] for _, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 4]
        self.assertTrue(details and "T640 box T 25.0 C - 3 C" in details[0], details)

    def test_chamber_dew_point_at_the_box_temperature_aborts_at_once(self):
        setup, make = t640_with(lambda c, now: {"box_t": 21.0} if c.rh_pv > 50.0 else {})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "safe")
        self.assertIn(">= T640 box T 21.0 C", [d for _, d in F.recs(res, "BTL433ESC001RTNV8")
                                                if d["eventID"] == 7][0]["detail"])

    def test_fault_bit_with_sample_rh_above_45_for_5_min_aborts(self):
        setup, make = t640_with(lambda c, now: {"fault": 1, "sample_rh": 50.0})
        res = F.run(setup=setup, t640=make, **HUMID)
        self.assertEqual(res.outcome, "safe")
        self.assertAlmostEqual(F.events(res, 7)[0][0] - first_at_17(res), 300.0, delta=21.0)

    def test_fault_bit_with_a_dry_sample_does_not_abort(self):
        setup, make = t640_with(lambda c, now: {"fault": 1, "sample_rh": 40.0})
        self.assertEqual(F.run(setup=setup, t640=make, **HUMID).outcome, "complete")

    def test_stale_t640_for_5_min_aborts_to_safe(self):
        t_dead = T0 + 1800.0
        res = F.run(t640=lambda clock: F.FakeT640(clock, alive=lambda now: now < t_dead), **HUMID)
        self.assertEqual(res.outcome, "safe")
        t_abort = F.events(res, 7)[0][0]
        self.assertAlmostEqual(t_abort - t_dead, 300.0, delta=11.0)
        self.assertIn("T640 data stale", [d for _, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 7][0]["detail"])

    def test_no_t640_reading_at_start_is_refused_without_a_command(self):
        res = F.run(t640=lambda clock: F.FakeT640(clock, alive=lambda now: False), **HUMID)
        self.assertEqual(res.outcome, "refused")
        self.assertEqual(res.ctrl.posts, [])
        self.assertEqual(res.clock.now - T0 >= rr.T640_START_WAIT_S, True)

    def test_without_the_t640_the_watch_points_are_12_to_21(self):      # and pre2 (16.4 C), whose check is the T640's
        points = rr.load_schedule(rr.SCHEDULE_FILE)[0]
        self.assertEqual([p.name for p in points if p.dew_point is not None and p.dew_point >= rr.WATCH_TD_C],
                         ["pre2"] + [str(i) for i in range(12, 22)])
        res = F.run(t640=None, **HUMID)
        self.assertEqual(res.outcome, "complete")
        text = res.routine.watch_text(res.points[1])
        self.assertIn("> 75 % for 2 min", text)
        self.assertIn("> 60 % for 5 min", text)
        self.assertIn("--operator safe", text)


class ModbusServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class T640ModbusClient(unittest.TestCase):                # must-fix 2: the client against a local Modbus/TCP server
    def serve(self, regs, bits, exception=None):
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                while True:
                    head = self.request.recv(12)
                    if len(head) < 12:
                        return
                    tid, _, _, unit, fc, start, count = struct.unpack(">HHHBBHH", head)
                    if exception:
                        pdu = struct.pack(">BB", fc | 0x80, exception)
                    elif fc == 4:
                        data = b"".join(struct.pack(">H", regs.get(i, 0)) for i in range(start, start + count))
                        pdu = struct.pack(">BB", 4, len(data)) + data
                    else:
                        pdu = struct.pack(">BBB", 2, 1, bits)
                    self.request.sendall(struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu)

        srv = ModbusServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return srv.server_address[1]

    @staticmethod
    def floats(**at):
        regs = {}
        for i, v in at.items():
            hi, lo = struct.unpack(">HH", struct.pack(">f", v))
            regs[int(i[1:])], regs[int(i[1:]) + 1] = hi, lo
        return regs

    def test_reads_sample_rh_box_t_duty_pm_and_the_fault_bit(self):
        port = self.serve(self.floats(r8=4.25, r36=41.5, r38=31.0, r60=96.0), bits=0b10000000)
        v = rr.T640Modbus("127.0.0.1", port, timeout=2.0).read()
        self.assertEqual(v, {"pm25": 4.25, "sample_rh": 41.5, "box_t": 31.0, "asc_duty": 96.0, "fault": 1})

    def test_fault_bit_clear(self):
        port = self.serve(self.floats(r36=30.0, r38=30.0, r60=10.0), bits=0b01111111)
        self.assertEqual(rr.T640Modbus("127.0.0.1", port, timeout=2.0).read()["fault"], 0)

    def test_modbus_exception_and_nan_are_errors(self):
        port = self.serve({}, 0, exception=2)
        with self.assertRaises(IOError):
            rr.T640Modbus("127.0.0.1", port, timeout=2.0).read()
        port = self.serve(self.floats(r36=float("nan"), r38=30.0, r60=10.0), 0)
        with self.assertRaises(ValueError):
            rr.T640Modbus("127.0.0.1", port, timeout=2.0).read()

    def test_poller_keeps_the_last_good_read_and_the_error(self):
        class Reader:
            n = 0

            def read(self):
                Reader.n += 1
                if Reader.n > 1:
                    raise OSError("unreachable")
                return {"sample_rh": 30.0}
        p = rr.T640Poller(Reader(), period_s=0.01)
        p.start()
        self.addCleanup(p.stopped.set)
        for _ in range(200):
            if Reader.n >= 3:
                break
            threading.Event().wait(0.01)
        t_read, v = p.latest()
        self.assertEqual(v, {"sample_rh": 30.0})
        self.assertIsNotNone(t_read)
        self.assertIn("unreachable", p.error)


class PreCycleChecks(unittest.TestCase):                  # must-fix 3
    PRE = dict(point_names=["pre1", "pre2", "pre3", "1"], operator_wait=True)

    def test_failed_check_goes_to_safe_not_stop(self):
        res = F.run(answers={("check", "pre2"): ("fail", 60.0)}, **self.PRE)
        self.assertEqual(res.outcome, "safe")
        self.assertEqual([p for _, p in F.events(res, 15)], ["pre2"])
        self.assertEqual([p for _, p in F.events(res, 7)], ["pre2"])
        self.assertEqual(len(F.events(res, 8)), 1)               # SAFE: dry-out, then STOP
        self.assertEqual(len(F.events(res, 9)), 1)
        self.assertNotIn("pre3", [p for _, p in F.events(res, 1)])
        safe_posts = [(cmd, j) for t, cmd, j, _ in res.ctrl.posts if t >= F.events(res, 7)[0][0]]
        self.assertIn(("constants/constant_1", {"dap": {"group": "dap_1", "value": True}}), safe_posts)
        self.assertEqual(safe_posts[-1], ("operations/stop_chamber", {"group": "standby"}))

    def test_unanswered_check_goes_to_safe_after_30_min(self):
        res = F.run(answers={("check", "pre1"): (None, 0.0)}, **self.PRE)
        self.assertEqual(res.outcome, "safe")
        self.assertEqual([p for _, p in F.events(res, 16)], ["pre1"])
        self.assertAlmostEqual(F.events(res, 16)[0][0] - F.events(res, 6)[0][0], rr.OPERATOR_WAIT_MIN * 60.0, delta=11.0)

    def test_point_1_waits_for_the_loading_check_with_the_rules_running(self):
        res = F.run(answers={("check", "pre3"): ("pass", 20 * 60.0)}, **self.PRE)
        self.assertEqual(res.outcome, "complete")
        t_end_pre3 = [t for t, p in F.events(res, 6) if p == "pre3"][0]
        t_start_1 = [t for t, p in F.events(res, 1) if p == "1"][0]
        self.assertGreaterEqual(t_start_1 - t_end_pre3, 20 * 60.0)
        reads = [t for t, _ in F.recs(res, "BTL433ESC001TMPRT") if t_end_pre3 <= t <= t_start_1]
        self.assertLessEqual(max(b - a for a, b in zip(reads, reads[1:])), 10.0 + 1e-6)
        self.assertEqual([d["detail"] for _, d in F.recs(res, "BTL433ESC001RTNV8") if d["eventID"] == 14],
                         ["operator: pass"] * 3)

    def test_unconfirmed_feed_change_goes_to_safe(self):
        res = F.run(answers={("feed", "pre3"): (None, 0.0)}, **self.PRE)
        self.assertEqual(res.outcome, "safe")
        self.assertEqual([p for _, p in F.events(res, 7)], ["pre3"])

    def test_operator_safe_request_at_any_time(self):
        res = F.run(safe_at=T0 + 2.5 * 3600, start_point="1")
        self.assertEqual(res.outcome, "safe")
        self.assertEqual(len(F.events(res, 18)), 1)
        self.assertAlmostEqual(F.events(res, 7)[0][0] - (T0 + 2.5 * 3600), 0.0, delta=11.0)

    def test_operator_channel_reads_each_answer_once_and_drops_stale_ones(self):
        with tempfile.TemporaryDirectory() as d:
            ch = rr.OperatorChannel(os.path.join(d, "operator.json"), tty=False)
            with redirect_stdout(io.StringIO()):
                rr.send_operator_answer("pass", d)
            self.assertEqual(ch.poll(0.0), "pass")
            self.assertIsNone(ch.poll(0.0))
            with redirect_stdout(io.StringIO()):
                rr.send_operator_answer("fail", d)
            self.assertIsNone(ch.poll(rr.time.time() + 60.0))      # older than the question: dropped
            self.assertFalse(os.path.exists(os.path.join(d, "operator.json")))

    def test_operator_cli_writes_the_answer_and_touches_nothing_else(self):
        boom = mock.Mock(side_effect=AssertionError("request made"))
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()), \
                mock.patch.object(F.chamber_mod, "requests", mock.Mock(get=boom, post=boom)):
            self.assertEqual(rr.main(["--operator", "safe", "--state-dir", d]), 0)
            with open(os.path.join(d, "operator.json")) as f:
                self.assertEqual(json.load(f)["answer"], "safe")


class Outbox(unittest.TestCase):                          # must-fix 4
    def test_control_process_writes_csv_and_outbox_never_mqtt(self):
        calls = []
        fake = types.SimpleNamespace(mqttOn=True, sensorFinisher=lambda dt, name, d: calls.append((name, dict(d))))
        with tempfile.TemporaryDirectory() as d:
            rr.install_outbox(fake, d)
            self.assertFalse(fake.mqttOn)
            rec = OrderedDict([("dateTime", "2026-10-22 01:02:03.000004"), ("point", "12"), ("setValue", 22.0),
                               ("enabled", 1), ("processValue", None)])
            fake.sensorFinisher(None, "BTL433ESC001RTNV8", rec)
            self.assertEqual(calls, [("BTL433ESC001RTNV8", dict(rec))])        # the CSV writer still runs
            (name,) = os.listdir(d)
            with open(os.path.join(d, name)) as f:
                line = json.loads(f.readline())
        self.assertEqual(line["sensor"], "BTL433ESC001RTNV8")
        self.assertEqual(json.dumps(line["data"]), json.dumps(rec))           # same payload, same types and order

    def test_mintssensorreader_reads_mqtton_at_call_time(self):
        with open(os.path.join(F.XU4, "mintsXU4", "mintsSensorReader.py"), encoding="utf-8") as f:
            src = f.read()
        body = src.split("def sensorFinisher(dateTime,sensorName,sensorDictionary):", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("if(mqttOn):", body)          # the module global, so install_outbox's mqttOn = False holds

    def test_outbox_write_failure_never_raises(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = os.path.join(d, "file")
            open(blocker, "w").close()
            with redirect_stdout(io.StringIO()) as out:
                rr.Outbox(os.path.join(blocker, "outbox")).write("X", {"a": 1})
        self.assertIn("Outbox write failed", out.getvalue())


class Publisher(unittest.TestCase):                       # must-fix 4: the separate process
    def setUp(self):
        import publishV8
        self.p = publishV8
        self.dir = tempfile.mkdtemp()
        self.addCleanup(lambda: [os.remove(os.path.join(self.dir, f)) for f in os.listdir(self.dir)] and os.rmdir(self.dir))
        self.path = os.path.join(self.dir, "2026-10-22.jsonl")

    def append(self, text):
        with open(self.path, "a") as f:
            f.write(text)

    def test_publishes_in_order_once_with_the_original_payload(self):
        recs = [("BTL433ESC001TMPRT", OrderedDict([("dateTime", "t"), ("setValue", 22.0), ("processValue", None)])),
                ("BTL433ESC001RTNV8", OrderedDict([("point", "12"), ("eventID", 1)]))]
        for name, d in recs:
            self.append(json.dumps({"sensor": name, "data": d}) + "\n")
        sent, offsets = [], {}
        n, ok = self.p.publish_pending(self.dir, lambda s, d: sent.append((s, json.dumps(d))) or True, offsets)
        self.assertEqual((n, ok), (2, True))
        self.assertEqual(sent, [(name, json.dumps(d)) for name, d in recs])
        self.assertEqual(self.p.publish_pending(self.dir, lambda s, d: self.fail("republished"), offsets), (0, True))

    def test_partial_line_waits_and_a_failure_does_not_advance(self):
        self.append(json.dumps({"sensor": "A", "data": {"x": 1}}) + "\n" + '{"sensor": "B", "da')
        offsets, sent = {}, []
        self.assertEqual(self.p.publish_pending(self.dir, lambda s, d: sent.append(s) or True, offsets), (1, True))
        self.append('ta": {"x": 2}}\n')
        self.assertEqual(self.p.publish_pending(self.dir, lambda s, d: False, offsets), (0, False))
        self.assertEqual(self.p.publish_pending(self.dir, lambda s, d: sent.append(s) or True, offsets), (1, True))
        self.assertEqual(sent, ["A", "B"])
        self.p.save_offsets(self.dir, offsets)
        self.assertEqual(self.p.read_offsets(self.dir), offsets)

    def test_unreadable_line_is_skipped(self):
        self.append("not json\n" + json.dumps({"sensor": "A", "data": {}}) + "\n")
        sent = []
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.p.publish_pending(self.dir, lambda s, d: sent.append(s) or True, {}), (1, True))
        self.assertEqual(sent, ["A"])

    def test_mqtt_publisher_uses_writemqttlatest_topic_and_payload(self):
        client = mock.Mock()
        client.publish.return_value = types.SimpleNamespace(rc=0)
        mL = types.SimpleNamespace(connect=lambda *a: True, mqtt_client=client, mqttUN="u", mqttPW="p", broker="b",
                                   port=1, macAddress="mac")
        d = OrderedDict([("a", 1.5), ("b", None)])
        self.assertTrue(self.p.mqtt_publisher(mL)("BTL433ESC001DAP", d))
        client.publish.assert_called_once_with("mac/BTL433ESC001DAP", json.dumps(d))
        mL.connect = lambda *a: False
        self.assertFalse(self.p.mqtt_publisher(mL)("X", d))


class StateAndResume(unittest.TestCase):                  # must-fix 5
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = rr.StateFile(os.path.join(self.dir, "state.json"))

    def tearDown(self):
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        os.rmdir(self.dir)

    def gate(self, prev, *argv):
        if prev is not None:
            self.state.write(prev)
        args = rr.parse_args(list(argv))
        with redirect_stdout(io.StringIO()) as out:
            code = rr.start_gate(args, "sha", self.state)
        return code, args, out.getvalue()

    def test_state_is_written_at_every_event_and_ends_with_the_outcome(self):
        seen = []

        class Recording(rr.StateFile):
            def write(s, data):
                seen.append(dict(data))
                super().write(data)
        res = F.run(start_point="1", point_names=["1", "2"], state=Recording(self.state.path))
        self.assertEqual(res.outcome, "complete")
        self.assertGreaterEqual(len(seen), len(F.recs(res, "BTL433ESC001RTNV8")))
        self.assertTrue(all(s["outcome"] is None for s in seen[:-1]))
        final = self.state.read()
        self.assertEqual((final["outcome"], final["chamber_parked"], final["hands_off"], final["point"]),
                         ("complete", True, False, "2"))
        self.assertEqual(final["last_event_label"], "Run Ended")
        self.assertEqual([f for f in os.listdir(self.dir) if f.endswith(".tmp")], [])

    def test_state_mid_run_names_the_point_and_phase_without_outcome(self):
        snap = {}

        def hook(now):
            if now > T0 + 3600 and not snap:
                snap.update(self.state.read())
        F.run(start_point="1", point_names=["1", "2"], state=self.state, hooks=[hook])
        self.assertEqual((snap["outcome"], snap["point"], snap["phase"]), (None, "2", "transition"))

    def test_abort_is_recorded_and_blocks_the_next_start(self):
        def setup(ctrl, clock):
            ctrl.ignore_t = lambda v: v < 15.0
        res = F.run(start_point="2", point_names=["2", "3"], setup=setup, state=self.state)
        self.assertEqual(res.outcome, "safe")
        st = self.state.read()
        self.assertEqual((st["outcome"], st["phase"], st["chamber_parked"]), ("safe", "safe", True))
        code, _, out = self.gate(None)
        self.assertEqual(code, 3)
        self.assertIn("aborted to SAFE at point 2", out)
        self.assertEqual(self.gate(None, "--resume")[0], 3)
        code, args, _ = self.gate(None, "--clear-abort", "inspected: dry, door closed")
        self.assertIsNone(code)

    def test_interrupted_run_may_resume_at_its_point(self):
        code, args, out = self.gate({"outcome": "interrupted", "point": "14", "phase": "soak", "schedule_sha": "sha"},
                                    "--resume")
        self.assertIsNone(code)
        self.assertEqual(args.start_point, "14")

    def test_died_run_may_resume_unless_it_died_in_safe(self):
        died = {"outcome": "died, parked", "point": "20", "phase": "transition", "last_event": 1, "schedule_sha": "sha"}
        self.assertIsNone(self.gate(died, "--resume")[0])
        died.update(phase="safe", last_event=8)
        self.assertEqual(self.gate(died, "--resume")[0], 3)

    def test_resume_refused_after_completion_or_with_another_schedule(self):
        self.assertEqual(self.gate({"outcome": "complete", "point": "bake", "schedule_sha": "sha"}, "--resume")[0], 3)
        self.assertEqual(self.gate({"outcome": "interrupted", "point": "3", "schedule_sha": "old"}, "--resume")[0], 3)

    def test_no_second_run_while_one_is_alive(self):
        alive = {"outcome": None, "pid": os.getpid(), "host": socket.gethostname(), "boot_id": rr.boot_id(),
                 "point": "5", "phase": "soak"}
        code, _, out = self.gate(alive, "--clear-abort", "x")
        self.assertEqual(code, 3)
        self.assertIn("already running", out)

    def test_left_constant_is_hands_off(self):
        res = F.run(setup=lambda c, k: setattr(c, "leave_constant_at", T0 + 3600), start_point="1",
                    point_names=["1", "2"], state=self.state)
        st = self.state.read()
        self.assertEqual((res.outcome, st["outcome"], st["hands_off"]), ("left_constant", "left_constant", True))


class ParkHook(unittest.TestCase):                        # must-fix 5: parkChamberV8.py
    def setUp(self):
        import parkChamberV8
        self.pk = parkChamberV8

    def test_decisions(self):
        dead = {"pid": 999999999, "host": socket.gethostname(), "boot_id": rr.boot_id(), "point": "19", "phase": "soak"}
        self.assertEqual(self.pk.decide(None)[0], False)
        self.assertEqual(self.pk.decide(dict(dead, outcome=None))[0], True)              # SIGKILL / OOM / crash
        self.assertEqual(self.pk.decide(dict(dead, outcome=None, boot_id="earlier"))[0], True)   # power loss
        self.assertEqual(self.pk.decide(dict(dead, outcome="stop_unconfirmed", chamber_parked=False))[0], True)
        self.assertEqual(self.pk.decide(dict(dead, outcome="complete", chamber_parked=True))[0], False)
        self.assertEqual(self.pk.decide(dict(dead, outcome="left_constant", hands_off=True))[0], False)
        self.assertEqual(self.pk.decide(dict(dead, outcome="refused", hands_off=True))[0], False)
        alive = dict(dead, pid=os.getpid(), outcome=None)
        self.assertEqual(self.pk.decide(alive)[0], False)                                 # never under a live run

    def test_park_sends_humidity_off_then_stop_and_records_it(self):
        clock = F.FakeTime()
        ctrl = F.FakeController(clock, op="constant")
        ctrl.humi_on = True
        ps = F.patches(clock, ctrl)
        for p in ps:
            p.start()
        try:
            with redirect_stdout(io.StringIO()):
                chamber = F.make_chamber(clock, ctrl, request_timeout=10)
                self.assertTrue(self.pk.park(chamber))
        finally:
            for p in ps:
                p.stop()
        self.assertEqual([(cmd, j) for _, cmd, j, _ in ctrl.posts],
                         [("constants/constant_1", {"humi": {"group": "loop", "enable": False}}),
                          ("operations/stop_chamber", {"group": "standby"})])
        with tempfile.TemporaryDirectory() as d:
            sf = rr.StateFile(os.path.join(d, "state.json"))
            self.pk.record(sf, {"outcome": None, "point": "19"}, True, "why", "ExecStopPost")
            st = sf.read()
        self.assertEqual((st["outcome"], st["previous_outcome"], st["chamber_parked"], st["parked_by"]),
                         ("died, parked", None, True, "ExecStopPost"))

    def test_nothing_to_do_contacts_nothing(self):
        boom = mock.Mock(side_effect=AssertionError("request made"))
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()) as out, \
                mock.patch.object(F.chamber_mod, "requests", mock.Mock(get=boom, post=boom)):
            rr.StateFile(os.path.join(d, "state.json")).write({"outcome": "complete", "chamber_parked": True})
            self.assertEqual(self.pk.main(["--after-exit", "--state-dir", d]), 0)
        self.assertIn("nothing to do", out.getvalue())

    def test_systemd_units_park_after_every_exit_and_at_boot(self):
        folder = os.path.join(F.XU4, "v8", "systemd")
        with open(os.path.join(folder, "runRoutineV8.service")) as f:
            unit = f.read()
        self.assertIn("ExecStopPost=/usr/bin/python3 -u parkChamberV8.py --after-exit", unit)
        self.assertIn("Restart=no", unit)
        with open(os.path.join(folder, "v8-park-on-boot.service")) as f:
            self.assertIn("parkChamberV8.py --on-boot", f.read())
# END ADDED BY CLAUDE


if __name__ == "__main__":
    unittest.main()
