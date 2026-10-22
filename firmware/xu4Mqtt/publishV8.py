"""
publishV8.py - publishes the v8 routine's records to the MQTT broker from its own process (v8 must-fix review,
2026-10-22, must-fix 4).

NEW FILE on branch feature/v8-routine-update.

WHY. mintsSensorReader.sensorFinisher publishes every record inline, and mintsLatest.connect waits up to 5 s for the
broker. In runRoutineV8.py that ran inside the 10-s control loop, six records per tick, so a broker that resolves but
does not answer delayed every safety rule. runRoutineV8.py now switches MQTT off in its own process and appends each
record to a local outbox (one JSON line per record, one file per UTC day, <dataFolder>/<mac>/v8outbox/). This
process reads the outbox and publishes each record as sensorFinisher would have (topic <mac>/<sensorName>, payload
json.dumps(record)) through Lakitha's mintsLatest connection. If the broker is down it waits and retries from the
saved offset; the control process never notices.

PROVENANCE. Written by Claude. The topic and payload are those of mintsLatest.writeMQTTLatest (main ccc8ab8).

    python3 publishV8.py                 # from firmware/xu4Mqtt; under systemd: v8/systemd/publishV8.service
    python3 publishV8.py --once          # publish what is pending and exit
"""

# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - outbox reader and publisher - standard library only, Python 3.8 syntax
import argparse
import glob
import json
import os
import sys
import time
import traceback

from runRoutineV8 import outbox_folder, write_json_atomic

OFFSETS_FILE = ".offsets.json"   # byte offset of the first unpublished line, per outbox file
POLL_S       = 2.0
RETRY_S      = 10.0


def read_offsets(folder):
    try:
        with open(os.path.join(folder, OFFSETS_FILE)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_offsets(folder, offsets):
    write_json_atomic(os.path.join(folder, OFFSETS_FILE), offsets)


def publish_pending(folder, publish, offsets):
    """Publish every complete line after the saved offsets, file by file in date order; stop at the first failed
    publish (it is retried from there next time). Returns (number published, False if a publish failed)."""
    n = 0
    for path in sorted(glob.glob(os.path.join(folder, "*.jsonl"))):
        name = os.path.basename(path)
        pos = offsets.get(name, 0)
        size = os.path.getsize(path)
        if size <= pos:
            continue
        with open(path, "rb") as f:
            f.seek(pos)
            data = f.read(size - pos)
        for raw in data.split(b"\n")[:-1]:       # the last piece is b"" or a line still being written
            end = pos + len(raw) + 1
            try:
                rec = json.loads(raw.decode("utf-8"))
                sensor, record = rec["sensor"], rec["data"]
            except (ValueError, KeyError, TypeError) as e:
                print(f"Skipped an unreadable outbox line ({name}, byte {pos}): {e}")
                pos = offsets[name] = end
                continue
            if not publish(sensor, record):
                return n, False
            pos = offsets[name] = end
            n += 1
    return n, True


def prune(folder, offsets):
    """Forget the offsets of outbox files that are gone. Nothing is deleted here (Calibration owner rule 2026-10-21:
    no code deletes a variable-built path); the outbox (about 15 MB a day) is cleared by a person, like old CSVs."""
    for name in list(offsets):
        if not os.path.exists(os.path.join(folder, name)):
            del offsets[name]


def mqtt_publisher(mL):
    """sensorFinisher's MQTT step (mintsLatest.writeMQTTLatest), returning whether the publish was accepted."""
    def publish(sensorName, sensorDictionary):
        if not mL.connect(mL.mqtt_client, mL.mqttUN, mL.mqttPW, mL.broker, mL.port):
            return False
        info = mL.mqtt_client.publish(mL.macAddress + "/" + sensorName, json.dumps(sensorDictionary))
        return info.rc == 0
    return publish


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish runRoutineV8.py's outbox to the MQTT broker.")
    ap.add_argument("--folder", help="outbox folder (default <dataFolder>/<mac>/v8outbox)")
    ap.add_argument("--once", action="store_true", help="publish what is pending, then exit")
    args = ap.parse_args(argv)

    from mintsXU4 import mintsDefinitions as mD
    from mintsXU4 import mintsLatest as mL
    folder = args.folder or outbox_folder(mD)
    publish = mqtt_publisher(mL)
    offsets = read_offsets(folder)
    print(f"Publishing {folder} to {mL.broker}:{mL.port}")
    while True:
        ok = False
        try:
            n, ok = publish_pending(folder, publish, offsets)
            if n:
                print(f"{n} records published")
            if not ok:
                print(f"Broker not reachable: retrying in {RETRY_S:g} s")
            prune(folder, offsets)
            if os.path.isdir(folder):
                save_offsets(folder, offsets)
        except Exception:
            traceback.print_exc()
        if args.once:
            return 0 if ok else 1
        time.sleep(POLL_S if ok else RETRY_S)


if __name__ == "__main__":
    sys.exit(main())
# END ADDED BY CLAUDE
