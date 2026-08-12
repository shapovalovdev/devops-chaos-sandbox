#!/usr/bin/env python3
# Time-guarded chaos scheduler for DevOps Chaos Sandbox
# Resolves #3.

import os
import sys
import time
import random
import datetime
import subprocess
from pathlib import Path

# Slot constraints (Sat=5, Sun=6)
ALLOWED_DAYS = {5, 6}
START_HOUR = 12
END_HOUR = 18

INSTALL_DIR = Path("/opt/chaos-sandbox")
LOCAL_DIR = Path(__file__).resolve().parent

def is_inside_slot():
    # Force bypass for testing / debugging
    if os.environ.get("FORCE_CHAOS") == "1":
        print("DEBUG: FORCE_CHAOS=1 is set. Bypassing slot checks.")
        return True

    now = datetime.datetime.now()
    weekday = now.weekday()
    hour = now.hour

    if weekday in ALLOWED_DAYS and (START_HOUR <= hour < END_HOUR):
        return True
    return False

def get_scenarios():
    # Look in install dir first, fall back to local dir for development
    scenarios_dir = INSTALL_DIR / "scenarios"
    if not scenarios_dir.is_dir():
        scenarios_dir = LOCAL_DIR / "scenarios"
        
    if not scenarios_dir.is_dir():
        print(f"ERROR: Scenarios directory not found at {scenarios_dir}")
        return []

    return sorted(list(scenarios_dir.glob("*.sh")))

def main():
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Chaos Scheduler invoked.")

    if not is_inside_slot():
        print(f"[{timestamp}] INFO: Outside allowed study slots (Sat/Sun {START_HOUR}:00-{END_HOUR}:00). Skipping chaos injection.")
        sys.exit(0)

    scenarios = get_scenarios()
    if not scenarios:
        print(f"[{timestamp}] WARNING: No chaos scenario scripts found. Exiting.")
        sys.exit(0)

    # Randomly select a failure scenario
    chosen = random.choice(scenarios)
    print(f"[{timestamp}] Selected Scenario: {chosen.name}")
    print(f"[{timestamp}] Running scenario execution: {chosen}")

    try:
        # Run script as root/subprocess
        result = subprocess.run(
            [str(chosen)], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            timeout=30
        )
        print(f"[{timestamp}] Execution finished. Code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout.strip()}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr.strip()}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"[{timestamp}] ERROR: Scenario execution timed out (30s limit).", file=sys.stderr)
    except Exception as e:
        print(f"[{timestamp}] ERROR during scenario run: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
