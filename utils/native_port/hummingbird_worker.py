#!/usr/bin/env python3
"""Compute-node-only adapter for the previously downloaded CSE220 corpus.

Submit through Slurm/Perch; do not run this script on a login node.
The corpus/runtime root can be overridden with SCARAB_LINUX_ORACLE_ROOT.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

if "SLURM_JOB_ID" not in os.environ:
    sys.exit("This adapter must run inside a Slurm allocation")

root = Path(__file__).resolve().parent.parent
oracle = Path(os.environ.get("SCARAB_LINUX_ORACLE_ROOT", str(Path.home() / "cse220-orbstack-check")))
manifest = Path(__file__).with_name("suite.json")
case = json.loads(manifest.read_text())["cases"][int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))]
workload, filename = case["trace"].split("/")
source = oracle / "traces" / "spec2017" / "rate_int_v2" / workload / "simp" / filename
if workload == "mcf_r":
    source = oracle / "traces" / filename
target = root / "traces" / case["trace"]
target.parent.mkdir(parents=True, exist_ok=True)
try:
    target.symlink_to(source)
except FileExistsError:
    if target.resolve() != source.resolve():
        raise ValueError(f"Existing trace link points elsewhere: {target}")
if os.environ.get("SLURM_ARRAY_TASK_ID", "0") == "0":
    probe = root / "results" / "random-glibc-probe"
    subprocess.run(["cc", "-DUSE_HOST_LIBC", str(Path(__file__).with_name("random_probe.c")), "-o", str(probe)], check=True)
    with (root / "results" / "random-glibc.txt").open("w") as output:
        subprocess.run([str(probe)], stdout=output, check=True)
sys.exit(subprocess.call([sys.executable, str(Path(__file__).with_name("parity.py")), "run",
    "--manifest", str(manifest), "--case", case["name"], "--binary", str(oracle / "runtime" / "scarab"),
    "--params", str(oracle / "runtime" / "PARAMS.golden_cove"), "--trace-root", str(root / "traces"),
    "--output", str(root / "results" / "linux-x86"), "--library-path", str(oracle / "runtime" / "lib")]))
