#!/usr/bin/env python3
"""Regression tests for failure detection in the differential gate."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("parity", Path(__file__).with_name("parity.py"))
parity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parity)


class ParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.a, self.b = [Path(self.temp.name) / name for name in ("a", "b")]
        for root in (self.a, self.b):
            root.mkdir()
            (root / "core.stat.0.csv").write_text(
                "Core, 0, 0\nNODE_CYCLE_count, 0, 9007199254740993\n"
                "FLOAT_value, 0, 0.000001\nSIM_HOST_WALL_SECONDS_value, 0, 1.0\n")
            (root / "core.stat.0.out").write_text("NODE_CYCLE 9007199254740993 9007199254740993\n")
            (root / "ramulator.stat.out").write_text("ramulator.reads 8 # count\n")
            (root / "PARAMS.in").write_text("--inst_limit 100\n")
            (root / "PARAMS.out").write_text("--inst_limit 100\nCBP_TRACE_R0 NULL /trace/a\n")
            (root / "sim.log").write_text("Scarab gitrev: test\nScarab started at now\nScarab finished at later\n")
            (root / "parity-run.json").write_text(json.dumps({"trace_sha256": "trace", "params_sha256": "params",
                "simulation_args": ["--inst_limit", "100"], "exit_code": 0}))

    def alter(self, name, old, new):
        path = self.b / name
        path.write_text(path.read_text().replace(old, new))

    def test_identical(self):
        result = parity.compare(self.a, self.b)
        self.assertTrue(result["simulation_equal"])
        self.assertTrue(result["byte_identical"])

    def test_catches_integer_difference_above_float_precision(self):
        self.alter("core.stat.0.csv", "9007199254740993", "9007199254740992")
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_no_floating_tolerance(self):
        self.alter("core.stat.0.csv", "0.000001", "0.000002")
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_missing_stat_file_fails(self):
        (self.b / "core.stat.0.out").unlink()
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_ramulator_change_fails(self):
        self.alter("ramulator.stat.out", "reads 8", "reads 9")
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_host_fields_are_explicitly_audited(self):
        self.alter("core.stat.0.csv", "SECONDS_value, 0, 1.0", "SECONDS_value, 0, 9.0")
        self.alter("PARAMS.out", "/trace/a", "/trace/b")
        result = parity.compare(self.a, self.b)
        self.assertTrue(result["simulation_equal"])
        self.assertFalse(result["byte_identical"])
        self.assertEqual(set(result["raw_byte_differences"]), {"core.stat.0.csv", "PARAMS.out"})

    def test_config_change_fails(self):
        self.alter("PARAMS.out", "inst_limit 100", "inst_limit 101")
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_different_trace_bytes_fail_even_with_same_counters(self):
        self.alter("parity-run.json", '"trace"', '"different"')
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])

    def test_duplicate_field_rejected(self):
        with (self.b / "core.stat.0.csv").open("a") as destination:
            destination.write("NODE_CYCLE_count, 0, 1\n")
        with self.assertRaises(ValueError):
            parity.compare(self.a, self.b)

    def test_incomplete_run_fails(self):
        self.alter("sim.log", "Scarab finished at later", "")
        self.assertFalse(parity.compare(self.a, self.b)["simulation_equal"])


if __name__ == "__main__":
    unittest.main()
