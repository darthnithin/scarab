#!/usr/bin/env python3
"""Negative gates for live-execution identity and process completion."""
import json
from pathlib import Path
import tempfile
import unittest

import execution_parity as execution


class ExecutionParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.a, self.b = [Path(self.temp.name) / name for name in ("linux", "mac")]
        for directory in (self.a, self.b):
            directory.mkdir()
            (directory / "core.stat.0.csv").write_text("Core,0,0\nNODE_CYCLE_count,0,305\n")
            (directory / "ramulator.stat.out").write_text("ramulator.reads 8 # count\n")
            (directory / "PARAMS.in").write_text("--num_cores 1\n")
            (directory / "PARAMS.out").write_text("--num_cores 1\n")
            (directory / "sim.log").write_text("Scarab finished at now\n")
            args = ["--frontend", "pin_exec_driven", "--inst_limit=10000"]
            record = {"program_sha256": "a" * 64, "pintool_sha256": "b" * 64,
                      "binary_sha256": "c" * 64, "params_sha256": execution.parity.sha256(directory / "PARAMS.in"),
                      "simulation_args": args, "simulator_command": ["/scarab"] + args,
                      "pin_command": ["setarch", "x86_64", "-R", "/pin", "-mt", "0", "-t", "/tool",
                                      "-socket_path", "/socket", "-core_id", "0", "--", "/program"],
                      "socket_protocol": "framed-v1", "scarab_exit_code": 0, "pin_exit_code": 0}
            (directory / "execution-run.json").write_text(json.dumps(record))
        record = self.record()
        record.update(execution_mode="ssh-relay", relay_exit_code=0, relay_helper_sha256="d" * 64)
        record["pin_invocation"] = execution.pin_invocation(record)
        del record["pin_command"]
        self.save(record)

    def record(self):
        return json.loads((self.b / "execution-run.json").read_text())

    def save(self, record):
        (self.b / "execution-run.json").write_text(json.dumps(record))

    def test_execution_provenance_without_trace_sidecars(self):
        result = execution.compare(self.a, self.b)
        self.assertTrue(result["passed"])
        self.assertFalse(result["trace_input_identity_verified"])
        self.assertTrue(result["execution_input_identity_verified"])

    def test_missing_record_fails(self):
        (self.b / "execution-run.json").unlink()
        self.assertFalse(execution.compare(self.a, self.b)["passed"])

    def test_identity_changes_fail(self):
        for field in ("program_sha256", "pintool_sha256", "params_sha256"):
            with self.subTest(field=field):
                original = self.record()
                changed = original.copy()
                changed[field] = "e" * 64
                self.save(changed)
                self.assertFalse(execution.compare(self.a, self.b)["passed"])
                self.save(original)

    def test_program_arguments_and_pin_options_fail(self):
        for field in ("program_command", "pin_options"):
            original = self.record()
            changed = json.loads(json.dumps(original))
            changed["pin_invocation"][field].append("changed")
            self.save(changed)
            self.assertFalse(execution.compare(self.a, self.b)["passed"])
            self.save(original)

    def test_all_process_exits_required(self):
        for field in ("scarab_exit_code", "pin_exit_code", "relay_exit_code"):
            original = self.record()
            for value in (None, 1, False):
                changed = original.copy()
                changed[field] = value
                self.save(changed)
                self.assertFalse(execution.compare(self.a, self.b)["passed"])
            self.save(original)

    def test_simulator_arguments_fail(self):
        record = self.record()
        record["simulation_args"][-1] = "--inst_limit=20"
        record["simulator_command"][-1] = "--inst_limit=20"
        self.save(record)
        self.assertFalse(execution.compare(self.a, self.b)["passed"])

    def test_manual_artifact_tamper_fails(self):
        (self.b / "relay.log").write_text("completed\n")
        record = self.record()
        record.update(imported_manual_run=True, manual_observation={"source": "test"})
        record["artifact_sha256"] = {name: execution.parity.sha256(self.b / name)
                                     for name in ("sim.log", "relay.log", "PARAMS.in")}
        self.save(record)
        self.assertTrue(execution.compare(self.a, self.b)["passed"])
        (self.b / "relay.log").write_text("changed\n")
        self.assertFalse(execution.compare(self.a, self.b)["passed"])

    def test_counter_difference_fails(self):
        (self.b / "core.stat.0.csv").write_text("Core,0,0\nNODE_CYCLE_count,0,306\n")
        result = execution.compare(self.a, self.b)
        self.assertTrue(result["execution_input_identity_verified"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
