#!/usr/bin/env python3
"""Run Scarab cases and compare deterministic simulation outputs without tolerance.

No third-party Python dependencies. See README.md for the comparison contract.
"""

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time


HOST_STATS = {"SIM_HOST_WALL_SECONDS_value", "SIM_HOST_WALL_SECONDS_total_value"}
PATH_PARAMS = {"cbp_trace_r0", "cbp_trace_r1", "cbp_trace_r2", "cbp_trace_r3", "output_dir"}
STAT_PATTERN = re.compile(r"\.stat(?:\.\d+)*\.(?:csv|out)(?:\.(?:warmup|period\.\d+|roi\.\d+))*$")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def numeric(value):
    """Lossless decimal equality, including printed precision; no float rounding."""
    try:
        number = Decimal(value.strip().rstrip("%"))
    except InvalidOperation:
        return value
    if number.is_nan():
        return "NaN"
    return number


def stats_csv(path):
    values, host = {}, {}
    with path.open(newline="") as source:
        for line, row in enumerate(csv.reader(source), 1):
            if not row or all(not value.strip() for value in row):
                continue
            if len(row) != 3:
                raise ValueError(f"{path}:{line}: expected three CSV fields")
            name, group, value = (value.strip() for value in row)
            key = (name, group)
            target = host if name in HOST_STATS else values
            if key in target:
                raise ValueError(f"{path}:{line}: duplicate statistic {key}")
            target[key] = numeric(value)
    if not values:
        raise ValueError(f"{path}: empty statistics file")
    return values, host


def text_stats(path):
    """Compare all text fields as well, preserving row/column ordering."""
    rows, excluded = [], []
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("SIM_HOST_WALL_SECONDS "):
            excluded.append(line)
            continue
        # NaN sign and padding are libc presentation details, recorded by byte audit.
        rows.append(tuple(numeric(token) for token in line.split()))
    if not rows:
        raise ValueError(f"{path}: empty statistics file")
    return rows, excluded


def params(path):
    values, paths = [], []
    for line in path.read_text().splitlines():
        match = re.match(r"^--(\S+)\s+(.*)$", line)
        if match and match.group(1) in PATH_PARAMS:
            paths.append((match.group(1), match.group(2)))
            values.append((match.group(1), "<host-path>"))
        else:
            fields = line.split()
            if fields and (re.fullmatch(r"CBP_TRACE_R\d+", fields[0]) or fields[0] == "OUTPUT_DIR"):
                paths.append(tuple(fields))
                values.append((fields[0], "<host-path>"))
            else:
                values.append(tuple(fields))
    return values, paths


def simulation_log(path):
    result, omitted = [], []
    for line in path.read_text().splitlines():
        if re.match(r"^Scarab (gitrev:|started at |finished at )", line):
            omitted.append(line)
            continue
        if line.startswith("** Heartbeat:") or line.startswith("** Core "):
            line, _, speed = line.partition(" -- ") if line.startswith("** Heartbeat:") else (line, "", "")
            # Heartbeat includes progress then counts then KIPS. Keep progress/counts.
            if speed:
                count, _, timing = speed.partition(" -- ")
                line += " -- " + count
                if timing:
                    omitted.append(timing)
            elif " KIPS" in line:
                line, _, timing = line.rpartition(" -- ")
                omitted.append(timing)
        result.append(tuple(line.split()))
    return result, omitted


def compare(reference, candidate):
    reference, candidate = Path(reference), Path(candidate)
    result = {"reference": str(reference), "candidate": str(candidate), "differences": [],
              "raw_byte_differences": [], "host_metadata": {}, "matched_csv_fields": 0,
              "matched_files": 0, "contract": "exact-numeric-and-token-v1"}
    differences = result["differences"]
    inventories = [{p.name for p in directory.iterdir() if p.is_file() and STAT_PATTERN.search(p.name)}
                   for directory in (reference, candidate)]
    if not inventories[0] or not any(".csv" in name for name in inventories[0]):
        differences.append({"kind": "missing_reference_statistics"})
    for missing in sorted(inventories[0] - inventories[1]):
        differences.append({"kind": "missing_candidate_file", "file": missing})
    for extra in sorted(inventories[1] - inventories[0]):
        differences.append({"kind": "extra_candidate_file", "file": extra})
    names = sorted(inventories[0] & inventories[1]) + ["PARAMS.in", "PARAMS.out", "sim.log"]
    for name in names:
        paths = [directory / name for directory in (reference, candidate)]
        if not all(path.exists() for path in paths):
            differences.append({"kind": "missing_required_file", "file": name})
            continue
        if paths[0].read_bytes() != paths[1].read_bytes():
            result["raw_byte_differences"].append(name)
        if name == "sim.log":
            for path in paths:
                if "Scarab finished at " not in path.read_text():
                    differences.append({"kind": "incomplete_run", "file": str(path)})
            parser = simulation_log
        elif name == "PARAMS.out":
            parser = params
        elif name == "PARAMS.in":
            parser = lambda path: (path.read_bytes(), [])
        elif ".csv" in name:
            parser = stats_csv
        else:
            parser = text_stats
        left, host_left = parser(paths[0])
        right, host_right = parser(paths[1])
        if host_left or host_right:
            result["host_metadata"][name] = {"reference": str(host_left), "candidate": str(host_right)}
        if isinstance(left, dict):
            for key in sorted(left.keys() | right.keys()):
                if key not in left or key not in right or left[key] != right[key]:
                    differences.append({"file": name, "field": list(key), "reference": str(left.get(key)),
                                        "candidate": str(right.get(key))})
                else:
                    result["matched_csv_fields"] += 1
        elif left != right:
            for index in range(max(len(left), len(right))):
                a = left[index] if index < len(left) else "<missing>"
                b = right[index] if index < len(right) else "<missing>"
                if a != b:
                    differences.append({"file": name, "row": index + 1, "reference": str(a), "candidate": str(b)})
        else:
            result["matched_files"] += 1
    # Runner provenance verifies that differing trace path names identify the same bytes.
    provenance = [directory / "parity-run.json" for directory in (reference, candidate)]
    result["input_identity_verified"] = all(path.exists() for path in provenance)
    if result["input_identity_verified"]:
        a, b = [json.loads(path.read_text()) for path in provenance]
        for key in ("trace_sha256", "params_sha256", "simulation_args"):
            if a[key] != b[key]:
                differences.append({"kind": "input_identity_mismatch", "field": key,
                                    "reference": a[key], "candidate": b[key]})
        for item in (a, b):
            if item.get("exit_code") != 0:
                differences.append({"kind": "unsuccessful_exit", "provenance": item})
    result["simulation_equal"] = not differences
    result["byte_identical"] = not result["raw_byte_differences"] and not differences
    return result


def run_case(args):
    manifest = json.loads(Path(args.manifest).read_text())
    cases = manifest["cases"]
    unknown = set(args.case or []) - {case["name"] for case in cases}
    if unknown:
        raise ValueError(f"Unknown case names: {sorted(unknown)}")
    cases = [case for case in cases if not args.case or case["name"] in args.case]
    if not cases:
        raise ValueError("No cases selected")
    binary = Path(args.binary).resolve()
    params_file = Path(args.params).resolve()
    def execute(case):
        trace = Path(args.trace_root).resolve() / case["trace"]
        if not trace.is_file():
            raise FileNotFoundError(trace)
        output = Path(args.output).resolve() / case["name"]
        if output.exists() and any(output.iterdir()):
            raise ValueError(f"Refusing to overwrite existing case: {output}")
        output.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(params_file, output / "PARAMS.in")
        sim_args = ["--frontend", case.get("frontend", "memtrace"), *case["args"]]
        command = [str(binary), *sim_args, f"--cbp_trace_r0={trace}"]
        environment = os.environ.copy()
        if args.library_path:
            environment["LD_LIBRARY_PATH"] = args.library_path
        start = time.monotonic()
        record = {"case": case["name"], "trace_sha256": sha256(trace),
                  "params_sha256": sha256(params_file), "binary_sha256": sha256(binary),
                  "simulation_args": sim_args, "command": command, "platform": platform.platform(),
                  "host": platform.node(), "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                  "machine": platform.machine(), "binary_format": subprocess.check_output(["file", str(binary)], text=True).strip()}
        save_json(output / "parity-run.json", record)
        with (output / "sim.log").open("w") as log:
            try:
                process = subprocess.run(command, cwd=output, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                         timeout=args.timeout)
                exit_code = process.returncode
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                exit_code = 124
        record.update(exit_code=exit_code, wall_seconds=time.monotonic() - start)
        save_json(output / "parity-run.json", record)
        print(f"{case['name']}: exit={exit_code} elapsed={record['wall_seconds']:.3f}s", flush=True)
        return exit_code != 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        return any(list(pool.map(execute, cases)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    for name in ("manifest", "binary", "params", "trace-root", "output"):
        run.add_argument("--" + name, required=True)
    run.add_argument("--case", action="append")
    run.add_argument("--library-path")
    run.add_argument("--jobs", type=int, default=1, help="Independent simulator processes to run concurrently")
    run.add_argument("--timeout", type=float, help="Maximum wall seconds per case; records exit 124 on timeout")
    check = commands.add_parser("compare")
    check.add_argument("reference")
    check.add_argument("candidate")
    check.add_argument("--report", required=True)
    check.add_argument("--require-provenance", action="store_true")
    check.add_argument("--strict-bytes", action="store_true")
    suite = commands.add_parser("compare-suite")
    suite.add_argument("reference")
    suite.add_argument("candidate")
    suite.add_argument("--manifest", required=True)
    suite.add_argument("--report", required=True)
    suite.add_argument("--require-provenance", action="store_true")
    suite.add_argument("--strict-bytes", action="store_true")
    suite.add_argument("--case", action="append")
    args = parser.parse_args()
    if args.command == "run":
        return run_case(args)
    if args.command == "compare-suite":
        cases = json.loads(Path(args.manifest).read_text())["cases"]
        unknown = set(args.case or []) - {case["name"] for case in cases}
        if unknown:
            raise ValueError(f"Unknown case names: {sorted(unknown)}")
        cases = [case for case in cases if not args.case or case["name"] in args.case]
        outcomes = []
        for case in cases:
            try:
                outcome = compare(Path(args.reference) / case["name"], Path(args.candidate) / case["name"])
            except (OSError, ValueError) as error:
                outcome = {"simulation_equal": False, "byte_identical": False, "input_identity_verified": False,
                           "matched_csv_fields": 0, "differences": [{"error": str(error)}]}
            outcome["case"] = case["name"]
            outcome["passed"] = outcome["simulation_equal"] and (not args.strict_bytes or outcome["byte_identical"]) and (not args.require_provenance or outcome["input_identity_verified"])
            outcomes.append(outcome)
        summary = {"passed": bool(outcomes) and all(item["passed"] for item in outcomes),
                   "cases": outcomes, "cases_passed": sum(item["passed"] for item in outcomes),
                   "matched_csv_fields": sum(item["matched_csv_fields"] for item in outcomes)}
        save_json(args.report, summary)
        print(json.dumps({key: value for key, value in summary.items() if key != "cases"}))
        for item in outcomes:
            if not item["passed"]:
                print(item["case"], json.dumps(item["differences"][:3]))
        return not summary["passed"]
    result = compare(args.reference, args.candidate)
    save_json(args.report, result)
    print(json.dumps({key: result[key] for key in ("simulation_equal", "byte_identical", "input_identity_verified", "matched_csv_fields")}))
    if result["differences"]:
        print(json.dumps(result["differences"][:10], indent=2))
    return not result["simulation_equal"] or (args.strict_bytes and not result["byte_identical"]) or (args.require_provenance and not result["input_identity_verified"])


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(f"parity: {error}", file=sys.stderr)
        sys.exit(2)
