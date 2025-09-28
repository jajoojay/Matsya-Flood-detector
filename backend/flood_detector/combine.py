#!/usr/bin/env python3
"""
combine.py

Runs the pipeline end-to-end. Stops on first failure.
"""
import subprocess
import sys

STEPS = [
    "python data_prep.py",
    "python train_river_model.py",
    "python train_flood_model.py",
    "python forecast_rainfall.py",
    "python forecast_gfs_upstream.py",
    "python predict_river_level.py",
    "python predict_flood.py",
    # dashboard manual run (user can run separately), keep but not mandatory
    "python final_flood_dashboard.py"
]

def run(cmd):
    print(f"\n--- Running: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"--- Step failed: {cmd}")
        sys.exit(res.returncode)
    print(f"--- Finished: {cmd}")

def main():
    for cmd in STEPS:
        run(cmd)
    print("\nAll steps completed successfully.")

if __name__ == "__main__":
    main()
