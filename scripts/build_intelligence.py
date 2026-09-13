"""Rebuild every model, evidence table and demo snapshot, then verify contracts.

python scripts/build_intelligence.py
Uses cached input files; no network or external service required.
"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    environment = dict(os.environ, OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", LOKY_MAX_CPU_COUNT="2")
    for script in ("benchmark_intelligence.py", "benchmark_decision.py", "benchmark_battle.py", "benchmark_clock.py", "benchmark_recovery.py", "export_recovery_evidence.py", "benchmark_clock_decision.py", "challenge_tyre_response.py", "export_tyre_response.py"):
        subprocess.run([sys.executable,str(ROOT/"scripts"/script)],cwd=ROOT,env=environment,check=True)
    subprocess.run([sys.executable,"-m","unittest","discover","-s","tests","-v"],
                   cwd=ROOT,env=environment,check=True)
