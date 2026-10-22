"""
parkChamberV8.py - sends humidity OFF, then STOP, over the LAN when runRoutineV8.py ended without parking the chamber
itself (v8 must-fix review, 2026-10-22, must-fix 5).

NEW FILE on branch feature/v8-routine-update.

WHY. runRoutineV8.py parks the chamber on every end it sees (normal end, abort -> SAFE, Ctrl-C, SIGTERM, SIGHUP). It
cannot on SIGKILL, out-of-memory, a crash of the interpreter or a power loss of the host: the chamber then keeps its
last set point, possibly 90 % RH. Under systemd the routine restarts itself and resumes (runRoutineV8.service); when
systemd gives up, its OnFailure= unit runs this script. The routine writes v8/state/state.json atomically at every
event; this script reads it and parks the chamber when the run has no outcome, or ended without a confirmed STOP. It
never acts while the routine still runs, after the chamber left CONSTANT by itself (the interlock wins) or after a
refused start.

    python3 parkChamberV8.py --after-exit    # v8/systemd/v8-park.service, the OnFailure= unit of runRoutineV8.service
    python3 parkChamberV8.py --on-boot       # v8/systemd/v8-park-on-boot.service (the host went down during a run)

PROVENANCE. Written by Claude. The credentials / chamber-index / Chamber set-up is Lakitha's (runRoutineCustom.py);
the humidity OFF then STOP order, each tried twice, is Dr. Lary's emergency_stop (cycle.py:210-232).
"""

# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - park decision and action
import argparse
import os
import sys
import traceback
from datetime import datetime, timezone

from runRoutineV8 import (REQUEST_TIMEOUT_S, STATE_DIR, StateFile, install_outbox, outbox_folder, pid_alive, url)


def decide(state):
    """(park?, why) from the routine's last state."""
    if not state:
        return False, "no state file: no v8 run recorded"
    out, where = state.get("outcome"), f"point {state.get('point')}, phase {state.get('phase')}"
    if pid_alive(state):
        return False, f"the routine is still running (pid {state.get('pid')}, {where})"
    if state.get("hands_off"):
        return False, f"hands off after outcome {out!r} (the chamber left CONSTANT by itself, or nothing was sent)"
    if state.get("chamber_parked") is True:
        return False, f"the routine confirmed its own STOP (outcome {out!r})"
    if out is None:
        return True, f"the routine ended without an outcome at {where} (killed, out of memory, crash or power loss)"
    return True, f"outcome {out!r} at {where} without a confirmed STOP"


def park(chamber):
    """Humidity OFF, then STOP, each tried twice; True when the summary reads back standby."""
    for attempt in (1, 2):
        try:
            if chamber.set_humidity_enabled(False):
                break
        except Exception:
            traceback.print_exc()
    for attempt in (1, 2):
        try:
            chamber.stop_chamber()
            chamber.get_and_write_summary(expanded=True)
            if chamber.validity and chamber.operationLabel == "standby":
                return True
        except Exception:
            traceback.print_exc()
    return False


def record(state_file, state, ok, why, by):
    state = dict(state)
    state.update(previous_outcome=state.get("outcome"), outcome="died, parked" if ok else "died, park NOT confirmed",
                 chamber_parked=ok, parked_by=by, park_reason=why,
                 service_result=os.environ.get("SERVICE_RESULT"), exit_code=os.environ.get("EXIT_CODE"),
                 exit_status=os.environ.get("EXIT_STATUS"),
                 parked_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
    state_file.write(state)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Park the chamber (humidity OFF, STOP) after runRoutineV8.py died.")
    when = ap.add_mutually_exclusive_group(required=True)
    when.add_argument("--after-exit", action="store_true", help="the routine's unit has failed (OnFailure=)")
    when.add_argument("--on-boot", action="store_true", help="the host has just booted")
    ap.add_argument("--state-dir", default=STATE_DIR)
    ap.add_argument("--chamber-url", help="default: the run's URL from the state file, else %s" % url)
    args = ap.parse_args(argv)

    state_file = StateFile(os.path.join(args.state_dir, "state.json"))
    state = state_file.read()
    go, why = decide(state)
    print(f"parkChamberV8 ({'after exit' if args.after_exit else 'on boot'}, service result "
          f"{os.environ.get('SERVICE_RESULT')}): {'PARKING' if go else 'nothing to do'}: {why}")
    if not go:
        return 0

    # ORIGINAL (Lakitha) - runRoutineCustom.py:7-27 at main ccc8ab8; the URL and index from the state file, the outbox and the request_timeout ADDED BY CLAUDE
    import mintsXU4.especChamber.chamber as eC
    from  mintsXU4.especChamber.chamber import Chamber
    from mintsXU4 import mintsDefinitions as mD
    from mintsXU4 import mintsSensorReader as mSR

    install_outbox(mSR, outbox_folder(mD))
    chamber_url = args.chamber_url or state.get("chamber_url") or url
    credentials         = mD.credentials
    token               = credentials['chamber']['token']
    chamber_index = state.get("chamber_index") or eC.get_available_chamber_index(chamber_url, token)

    if chamber_index is None:
        print("No available chamber found: the chamber was NOT parked. Stop it at the panel.")
        record(state_file, state, False, why, "boot" if args.on_boot else "OnFailure")
        return 1

    chamber = Chamber(chamber_url, chamber_index, token, request_timeout=REQUEST_TIMEOUT_S)
    ok = park(chamber)
    record(state_file, state, ok, why, "boot" if args.on_boot else "OnFailure")
    print("Chamber parked: humidity OFF, STOP read back" if ok else "STOP NOT confirmed: stop the chamber at the panel.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
# END ADDED BY CLAUDE
