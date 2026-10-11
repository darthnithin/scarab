#!/usr/bin/env python3
"""Compile and exercise both socket message paths without the Pin runtime."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


class SocketTests(unittest.TestCase):
    def test_stream_transport_and_packed_abi(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "socket_probe"
            subprocess.run([
                os.environ.get("CXX", "c++"), "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-DGTEST_COMPILE", "-I", str(ROOT / "src"), str(HERE / "socket_probe.cc"),
                str(ROOT / "src/pin/pin_lib/message_queue_interface_lib.cc"), "-o", str(binary)
            ], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30, check=True)
            self.assertIn("PASS: fragmented/coalesced frames", result.stdout)
            self.assertIn("ABI: command=20 register=24 operation=1071", result.stdout)


if __name__ == "__main__":
    unittest.main()
