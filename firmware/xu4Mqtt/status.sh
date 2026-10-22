#!/bin/bash
# v8 routine update: this file is ORIGINAL (Lakitha) code except the blocks marked ADDED BY CLAUDE.
#
sleep 1
echo "Routine status check"
echo "===================="
echo $(pgrep -f 'runRoutine.py')
# ADDED BY CLAUDE (v8 routine update, 2026-10-20) - also report the v8 routine - 'runRoutine.py' does not match runRoutineV8.py
echo "v8 routine (runRoutineV8.py)"
echo $(pgrep -f 'runRoutineV8.py')
# END ADDED BY CLAUDE
# ADDED BY CLAUDE (v8 must-fix review, 2026-10-22) - the MQTT publisher and the routine's last state
echo "v8 publisher (publishV8.py)"
echo $(pgrep -f 'publishV8.py')
echo "v8 state (v8/state/state.json)"
cat v8/state/state.json 2>/dev/null || echo "no v8 run recorded"
# END ADDED BY CLAUDE

