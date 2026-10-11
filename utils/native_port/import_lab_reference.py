#!/usr/bin/env python3
"""Verify and copy historical CSE220 outputs; never alter the original lab.

Provenance sidecars explicitly identify imported historical evidence. They are
not represented as new executions of the parity runner.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from parity import save_json, sha256, stats_csv


def require(condition, context):
    if not condition:
        raise ValueError(f"Historical provenance validation failed: {context}")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lab-root", type=Path, required=True)
parser.add_argument("--manifest", type=Path, required=True)
parser.add_argument("--trace-root", type=Path, required=True)
parser.add_argument("--params", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
cases = json.loads(args.manifest.read_text())["cases"]
binary_hash = "97b87093077cb72f0c99a0f857cfd96a7ef132b7427c19d24381f74f82ba4ac7"
params_hash = sha256(args.params)
verified = []
for case in cases:
    workload, filename = case["trace"].split("/")
    cluster = int(filename.removesuffix(".zip"))
    source = args.lab_root / "simulations/lab1/baseline/spec2017/rate_int_v2" / workload / str(cluster)
    destination = args.output / case["name"]
    if destination.exists():
        raise ValueError(f"Refusing to overwrite {destination}")
    trace_hash = sha256(args.trace_root / case["trace"])
    require(sha256(source / "PARAMS.in") == params_hash, source)
    expanded = (source / "PARAMS.out").read_text()
    for flag in case["args"]:
        key, value = flag.split("=", 1)
        require(re.search(r"^" + re.escape(key) + r"\s+" + re.escape(value) + r"\s*$", expanded, re.MULTILINE), (source, flag))
    require("Scarab gitrev: 108329f" in (source / "sim.log").read_text(), source)
    require("Scarab finished at " in (source / "sim.log").read_text(), source)
    stats, _ = stats_csv(source / "core.stat.0.csv")
    require(abs(stats[("Cumulative_Instructions", "0")] - 60_000_000) < 1000, source)
    require(abs(stats[("Periodic_Instructions", "0")] - 10_000_000) < 1000, source)
    evidence = []
    if (source / "provenance.json").exists():
        provenance = json.loads((source / "provenance.json").read_text())
        require(provenance["exit_code"] == 0, source)
        require(provenance["workload"] == workload and provenance["cluster_id"] == cluster, source)
        require(provenance["binary_sha256"] == binary_hash, source)
        require(provenance["params_sha256"] == params_hash, source)
        require(provenance["trace_sha256"] == trace_hash, source)
        require(provenance["segment_size"] == 10_000_000 and provenance["warmup"] == 50_000_000, source)
        evidence.append(source / "provenance.json")
    else:
        # The selected MCF point was run by the older verified hybrid controller.
        require(workload == "mcf_r" and cluster == 93581, source)
        checksums = (source / "input-checksums.txt").read_text()
        require(f"{binary_hash}  /home/ndanday/cse220-orbstack-check/runtime/scarab" in checksums, source)
        require(f"{trace_hash}  /home/ndanday/cse220-orbstack-check/traces/{cluster}.zip" in checksums, source)
        state_file = args.lab_root / "output/hybrid-mcf/state.json"
        state = json.loads(state_file.read_text())
        require(state["phase"] == "complete" and state["trace_sha256"][str(cluster)] == trace_hash, source)
        require(state["binary_sha256"] == binary_hash, source)
        accounting = args.lab_root / "output/hybrid-mcf/slurm-status.txt"
        require("800783_0|COMPLETED|0:0" in accounting.read_text(), accounting)
        evidence += [source / "input-checksums.txt", state_file, accounting]
    evidence += [source / "PARAMS.in", source / "PARAMS.out", source / "sim.log", source / "core.stat.0.csv"]
    shutil.copytree(source, destination)
    record = {"imported_historical_run": True, "source_directory": str(source.resolve()),
              "source_evidence": {str(p.resolve()): sha256(p) for p in evidence},
              "case": case["name"], "trace_sha256": trace_hash, "params_sha256": params_hash,
              "binary_sha256": binary_hash, "simulation_args": ["--frontend", "memtrace", *case["args"]],
              "exit_code": 0, "exit_code_source": "original worker provenance or recorded Slurm accounting"}
    save_json(destination / "parity-run.json", record)
    for original in source.iterdir():
        if original.is_file():
            require(sha256(original) == sha256(destination / original.name), original)
    verified.append(record)
save_json(args.output / "import-audit.json", {"cases": verified, "count": len(verified)})
print(f"Verified and copied {len(verified)} complete historical runs; originals untouched")
