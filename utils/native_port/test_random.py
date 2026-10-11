#!/usr/bin/env python3
"""Compare the portable generator against samples obtained from Linux glibc."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class RandomCompatibilityTests(unittest.TestCase):
    def test_linux_reference_provenance_and_native_sequence(self):
        fixture = HERE / "fixtures" / "random-glibc.txt"
        provenance = json.loads(fixture.with_suffix(".json").read_text())
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), provenance["fixture_sha256"])
        self.assertEqual(hashlib.sha256((HERE / "random_probe.c").read_bytes()).hexdigest(), provenance["probe_source_sha256"])
        with tempfile.TemporaryDirectory() as directory:
            for optimization in ("-O0", "-O2"):
                with self.subTest(optimization=optimization):
                    binary = Path(directory) / "probe"
                    subprocess.run([os.environ.get("CC", "cc"), "-std=c11", optimization, "-Wall", "-Wextra", "-Werror",
                        "-I", str(ROOT / "src"), str(HERE / "random_probe.c"), str(ROOT / "src/libs/scarab_random.c"),
                        "-o", str(binary)], check=True)
                    self.assertEqual(subprocess.check_output([str(binary)]), fixture.read_bytes())


if __name__ == "__main__":
    unittest.main()
