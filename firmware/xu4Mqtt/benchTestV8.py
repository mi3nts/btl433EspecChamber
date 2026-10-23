"""
benchTestV8.py - bench test of the v8 commands before the first v8 run (v8 routine update, 2026-10-20; host duty 10).

NEW FILE on branch feature/v8-routine-update.

WHAT. With an operator AT THE CHAMBER and the chamber at lab conditions (door closed, nothing humid inside):
start CONSTANT at the current temperature, switch the humidity system ON / OFF and the dry-air purge ON / OFF with
the new Chamber.set_humidity_enabled / set_dry_air_purge, read each one back from the summary and print PASS or FAIL.
It always ends with humidity OFF and STOP. ``--cable-pull`` then reads the summary every 10 s for the cable-pull check
(V8_ROUTINE_UPDATE.md, "Bench test"): each read must give up within the 10-s request timeout while the cable is out.

PROVENANCE. The credentials / chamber-index / Chamber set-up block is Lakitha's (runRoutineCustom.py); everything
else was written by Claude for this branch. It calls the pipeline (Chamber, sensorFinisher) without modifying it, so
every command it sends is logged to BTL433ESC001CHNG like any other.

It refuses to run without --i-am-at-the-chamber.

    python3 benchTestV8.py --i-am-at-the-chamber
    python3 benchTestV8.py --i-am-at-the-chamber --cable-pull
"""

# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - bench test settings and steps
import argparse
import sys
import time
import traceback

from runRoutineV8 import REQUEST_TIMEOUT_S, install_outbox, outbox_folder, url, wait_standby


def check(name, ok):
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return bool(ok)


def read(chamber):
    chamber.get_and_write_summary(expanded=True)
    return bool(chamber.validity)


def bench(chamber):
    results = []
    if not read(chamber):
        return [check("summary readable", False)]
    if chamber.operationLabel not in ("standby", "constant"):
        print(f"The chamber is in {chamber.operationLabel!r} mode: stop it at the panel first")
        return [check("chamber in standby or constant", False)]
    chamber.set_temperature_value(round(chamber.temperature_process_value, 1))
    chamber.set_humidity_enabled(False)
    chamber.start_constant_mode()
    results.append(check("CONSTANT mode started", read(chamber) and chamber.operationLabel == "constant"))
    for state in (True, False):
        chamber.set_humidity_enabled(state)
        time.sleep(5)
        results.append(check(f"humidity system {'ON' if state else 'OFF'} read back",
                             read(chamber) and chamber.humidity_enable == int(state)))
    for state in (True, False):
        sent = chamber.set_dry_air_purge(state)
        time.sleep(5)
        results.append(check(f"dry-air purge {'ON' if state else 'OFF'} read back (group {chamber.dap_group!r})",
                             sent and read(chamber) and chamber.dap_enable == int(state)))
    return results


def cable_pull(chamber, minutes=6):
    print(f"Cable-pull check: pull the chamber's network cable after 3 reads, plug it back after 3 failed reads.")
    durations, failed, recovered = [], 0, False
    t_end = time.time() + minutes * 60
    while time.time() < t_end and not recovered:
        t0 = time.time()
        valid = read(chamber)
        dt = time.time() - t0
        print(f"read {'valid' if valid else 'NO VALID READING'} in {dt:.1f} s")
        if not valid:
            failed += 1
            durations.append(dt)
        recovered = valid and failed >= 3
        time.sleep(10)
    ok = check(f"each failed read gave up within the timeout ({REQUEST_TIMEOUT_S} s connect + read)",
               failed >= 3 and max(durations) <= 2 * REQUEST_TIMEOUT_S + 5)
    return [ok, check("reads valid again after the cable is back", recovered)]


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Bench test of the v8 humidity / purge commands (operator present).")
    ap.add_argument("--i-am-at-the-chamber", action="store_true", help="required: an operator is at the chamber")
    ap.add_argument("--cable-pull", action="store_true", help="then run the cable-pull check")
    ap.add_argument("--chamber-url", default=url)
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if not args.i_am_at_the_chamber:
        print("Refused: run this only with an operator at the chamber (--i-am-at-the-chamber).")
        return 2
    # END ADDED BY CLAUDE

    # ORIGINAL (Lakitha) - runRoutineCustom.py:7-27 at main ccc8ab8; the url from --chamber-url, the request_timeout and "return 1" ADDED BY CLAUDE
    import mintsXU4.especChamber.chamber as eC
    from  mintsXU4.especChamber.chamber import Chamber
    from mintsXU4 import mintsDefinitions as mD

    # ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - must-fix 4: as runRoutineV8.py, CSV and the outbox only, so the cable-pull timings are the chamber's alone
    from mintsXU4 import mintsSensorReader as mSR
    install_outbox(mSR, outbox_folder(mD))
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

    # ADDED BY CLAUDE (v8 routine update, 2026-10-20) - run the checks; always end with humidity OFF and STOP
    results = []
    try:
        results += bench(chamber)
        if args.cable_pull and all(results):
            results += cable_pull(chamber)
    except BaseException:
        traceback.print_exc()
        results.append(False)
    finally:
        for name, fn in (("humidity OFF", lambda: chamber.set_humidity_enabled(False)), ("STOP", chamber.stop_chamber)):
            try:
                fn()
            except Exception:
                traceback.print_exc()
        stopped = wait_standby(lambda: read(chamber), chamber)   # 2026-10-23: one read right after STOP still said 'constant'
        results.append(check("chamber STOPPED (humidity OFF)", stopped))
        if not stopped:
            print("STOP the chamber at the panel now.")
    print(f"Bench test {'PASSED' if all(results) else 'FAILED'} ({sum(results)}/{len(results)} checks)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
# END ADDED BY CLAUDE
