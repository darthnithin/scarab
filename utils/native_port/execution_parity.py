#!/usr/bin/env python3
"""Compare live Pin execution results with execution-specific provenance.

This consumes execution-run.json records; it never creates trace sidecars.
Records may come from a runner or a transparently labeled manual-run import.
"""
import argparse
import json
from pathlib import Path
import re

import parity


HASH_FIELDS = ("program_sha256", "pintool_sha256", "params_sha256", "binary_sha256")


def pin_invocation(record):
    """Ignore only transport socket and tool location, retaining executable argv."""
    if "pin_command" not in record:
        invocation = record["pin_invocation"]
        if not isinstance(invocation, dict):
            raise ValueError("pin_invocation must be an object")
        required = {"launcher", "pin_executable", "pin_options", "program_command"}
        if set(invocation) != required:
            raise ValueError("Incomplete canonical Pin invocation")
        for key in ("launcher", "pin_options", "program_command"):
            if not isinstance(invocation[key], list) or not invocation[key] or not all(
                    isinstance(value, str) and value for value in invocation[key]):
                raise ValueError("Invalid Pin invocation field: " + key)
        if not isinstance(invocation["pin_executable"], str) or not invocation["pin_executable"]:
            raise ValueError("Missing Pin executable")
        return invocation
    command = record["pin_command"]
    if not isinstance(command, list) or command[:3] != ["setarch", "x86_64", "-R"]:
        raise ValueError("Expected fixed-address x86_64 Pin invocation")
    divider = command.index("--")
    if divider < 5 or len(command) <= divider + 1:
        raise ValueError("Pin invocation lacks executable arguments")
    options = command[4:divider].copy()
    for flag, replacement in (("-t", "<pintool_sha256>"), ("-socket_path", "<transport_socket>")):
        if options.count(flag) != 1:
            raise ValueError("Expected one " + flag)
        index = options.index(flag)
        if index + 1 == len(options):
            raise ValueError("Missing value for " + flag)
        options[index + 1] = replacement
    return {"launcher": command[:3], "pin_executable": command[3],
            "pin_options": options, "program_command": command[divider + 1:]}


def load_record(directory):
    path = directory / "execution-run.json"
    record = json.loads(path.read_text())
    for key in HASH_FIELDS:
        if not isinstance(record.get(key), str) or not re.fullmatch("[0-9a-f]{64}", record[key]):
            raise ValueError("Missing or invalid " + key)
    if parity.sha256(directory / "PARAMS.in") != record["params_sha256"]:
        raise ValueError("PARAMS.in does not match execution record")
    arguments = record.get("simulation_args")
    if not isinstance(arguments, list) or not arguments or not all(isinstance(x, str) for x in arguments):
        raise ValueError("Missing simulator arguments")
    if arguments[:2] != ["--frontend", "pin_exec_driven"]:
        raise ValueError("Record does not select pin_exec_driven")
    command = record.get("simulator_command")
    if not isinstance(command, list) or command[1:] != arguments:
        raise ValueError("Simulator command does not match recorded arguments")
    for key in ("scarab_exit_code", "pin_exit_code"):
        if type(record.get(key)) is not int or record[key] != 0:
            raise ValueError("Unsuccessful or missing " + key)
    mode = record.get("execution_mode", "direct")
    if mode not in ("direct", "ssh-relay") or ("pin_command" not in record and mode != "ssh-relay"):
        raise ValueError("Unknown or incomplete execution mode")
    if mode == "ssh-relay":
        if type(record.get("relay_exit_code")) is not int or record["relay_exit_code"] != 0:
            raise ValueError("Unsuccessful or missing relay_exit_code")
        if not re.fullmatch("[0-9a-f]{64}", record.get("relay_helper_sha256", "")):
            raise ValueError("Missing relay helper identity")
    if record.get("socket_protocol") != "framed-v1":
        raise ValueError("Execution gate currently requires framed-v1")
    if record.get("imported_manual_run"):
        if not record.get("manual_observation") or not record.get("artifact_sha256"):
            raise ValueError("Manual import lacks observation/artifact audit")
        if not {"PARAMS.in", "sim.log", "relay.log"}.issubset(record["artifact_sha256"]):
            raise ValueError("Manual import lacks required artifact hashes")
    for name, digest in record.get("artifact_sha256", {}).items():
        if Path(name).name != name or parity.sha256(directory / name) != digest:
            raise ValueError("Imported artifact changed: " + name)
    identity = {key: record[key] for key in ("program_sha256", "pintool_sha256", "params_sha256",
                                             "simulation_args", "socket_protocol")}
    identity["pin_invocation"] = pin_invocation(record)
    return record, identity


def compare(reference, candidate):
    reference, candidate = Path(reference), Path(candidate)
    result = parity.compare(reference, candidate)
    result["trace_input_identity_verified"] = result.pop("input_identity_verified")
    result["execution_input_identity_verified"] = False
    result["execution_provenance_errors"] = []
    result["execution_provenance"] = {}
    identities = []
    for side, directory in (("reference", reference), ("candidate", candidate)):
        try:
            record, identity = load_record(directory)
            result["execution_provenance"][side] = record
            identities.append(identity)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result["execution_provenance_errors"].append({"side": side, "error": str(error)})
    if len(identities) == 2:
        for key in identities[0]:
            if identities[0][key] != identities[1][key]:
                result["execution_provenance_errors"].append({"field": key,
                    "reference": identities[0][key], "candidate": identities[1][key]})
        result["execution_input_identity_verified"] = not result["execution_provenance_errors"]
    result["passed"] = result["simulation_equal"] and result["execution_input_identity_verified"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.reference, args.candidate)
    parity.save_json(args.report, result)
    print(json.dumps({key: result[key] for key in ("passed", "simulation_equal",
        "execution_input_identity_verified", "matched_csv_fields")}))
    return not result["passed"]


if __name__ == "__main__":
    raise SystemExit(main())
