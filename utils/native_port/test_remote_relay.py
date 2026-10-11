#!/usr/bin/env python3
"""Real pipe/socket checks for the SSH relay's duplex and EOF behavior."""
import concurrent.futures
import base64
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RelayTests(unittest.TestCase):
    def start_relay(self, *, encode_stdio=False, exit_on_socket_eof=False):
        parent, child = socket.socketpair()
        parent.settimeout(5)
        script = (
            "import importlib.util,socket,sys; "
            "spec=importlib.util.spec_from_file_location('relay',sys.argv[1]); "
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m); "
            "m.relay(socket.socket(fileno=int(sys.argv[2])),0,1,"
            "encode_stdio=sys.argv[3]=='1',exit_on_socket_eof=sys.argv[4]=='1')"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(ROOT / "bin/scarab_remote_pin.py"),
             str(child.fileno()), str(int(encode_stdio)), str(int(exit_on_socket_eof))],
            pass_fds=(child.fileno(),), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child.close()
        self.addCleanup(self.close_relay, parent, process)
        return parent, process

    @staticmethod
    def close_relay(parent, process):
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        parent.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()

    @staticmethod
    def receive_exact(sock, length):
        result = bytearray()
        while len(result) < length:
            data = sock.recv(min(7919, length - len(result)))
            if not data:
                raise AssertionError("Relay closed before the full payload arrived")
            result.extend(data)
        return bytes(result)

    def test_encoded_duplex_through_line_buffering(self):
        local, local_process = self.start_relay(encode_stdio=True)
        remote, remote_process = self.start_relay(encode_stdio=True)

        def forward_complete_lines(source, destination):
            # Model an intermediary that withholds every byte until a newline.
            # Fragment each line again to exercise incremental decoding.
            for line in iter(source.stdout.readline, b""):
                self.assertTrue(line.endswith(b"\n"))
                for offset in range(0, len(line), 7919):
                    destination.stdin.write(line[offset:offset + 7919])
                    destination.stdin.flush()
            destination.stdin.close()

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        pumps = [executor.submit(forward_complete_lines, local_process, remote_process),
                 executor.submit(forward_complete_lines, remote_process, local_process)]
        try:
            # Each peer waits for the reply before sending anything else. Raw
            # binary without newlines deadlocks at this handshake boundary.
            hello = b"SCB1\x00\x00\x00\x14Client Init Message\x00"
            reply = b"SCB1\x00\x00\x00\x14Server Init Message\x00"
            local.sendall(hello)
            self.assertEqual(self.receive_exact(remote, len(hello)), hello)
            remote.sendall(reply)
            self.assertEqual(self.receive_exact(local, len(reply)), reply)

            outgoing = bytes(range(256)) * 4097
            incoming = bytes(reversed(range(256))) * 4111
            writers = [executor.submit(local.sendall, outgoing),
                       executor.submit(remote.sendall, incoming)]
            readers = [executor.submit(self.receive_exact, remote, len(outgoing)),
                       executor.submit(self.receive_exact, local, len(incoming))]
            for writer in writers:
                writer.result(timeout=10)
            self.assertEqual(readers[0].result(timeout=10), outgoing)
            self.assertEqual(readers[1].result(timeout=10), incoming)
            local.shutdown(socket.SHUT_WR)
            remote.shutdown(socket.SHUT_WR)
            self.assertEqual(local.recv(1), b"")
            self.assertEqual(remote.recv(1), b"")
            for pump in pumps:
                pump.result(timeout=5)
            for process in (local_process, remote_process):
                process.wait(timeout=5)
                self.assertEqual(process.returncode, 0, process.stderr.read().decode())
        finally:
            # Kill the helpers before waiting for threads on a failing check,
            # so an intentional handshake regression cannot hang the test run.
            for process in (local_process, remote_process):
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
            local.close()
            remote.close()
            executor.shutdown(wait=True)

    def test_remote_socket_eof_exits_with_stdin_still_open(self):
        peer, process = self.start_relay(encode_stdio=True, exit_on_socket_eof=True)
        payload = b"final Pin data\x00\xff"
        peer.sendall(payload)
        peer.close()
        # Keep the upstream writer open: srun/SSH may not close their streams
        # until this helper exits. Waiting for stdin EOF would create a cycle.
        self.assertFalse(process.stdin.closed)
        process.wait(timeout=5)
        encoded = process.stdout.read()
        self.assertEqual(b"".join(base64.b64decode(line, validate=True)
                                  for line in encoded.splitlines()), payload)
        self.assertEqual(process.returncode, 0, process.stderr.read().decode())
        self.assertFalse(process.stdin.closed)

    def test_rejects_malformed_encoded_lines(self):
        cases = (
            (b"A" * 87385 + b"\n", "Oversized SSH relay line"),
            (b"A" * 87385, "Oversized SSH relay line"),
            (base64.b64encode(b"unterminated"), "Truncated SSH relay line"),
            (b"%%%invalid%%%\n", "Only base64 data is allowed"),
            (b"YQ=\n", "Incorrect padding"),
        )
        for payload, diagnostic in cases:
            with self.subTest(diagnostic=diagnostic, size=len(payload)):
                _, process = self.start_relay(encode_stdio=True)
                _, errors = process.communicate(input=payload, timeout=5)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn(diagnostic, errors.decode())

    def test_duplex_backpressure_and_half_close(self):
        parent, child = socket.socketpair()
        input_read, input_write = os.pipe()
        output_read, output_write = os.pipe()
        script = (
            "import importlib.util,socket,sys; "
            "spec=importlib.util.spec_from_file_location('relay',sys.argv[1]); "
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m); "
            "m.relay(socket.socket(fileno=int(sys.argv[2])),int(sys.argv[3]),int(sys.argv[4]))"
        )
        process = subprocess.Popen(
            [sys.executable, "-c", script, str(ROOT / "bin/scarab_remote_pin.py"),
             str(child.fileno()), str(input_read), str(output_write)],
            pass_fds=(child.fileno(), input_read, output_write), stderr=subprocess.PIPE)
        child.close()
        os.close(input_read)
        os.close(output_write)
        outgoing = bytes(range(256)) * 12289
        incoming = bytes(reversed(range(256))) * 12317

        def write_input():
            view = memoryview(incoming)
            try:
                while view:
                    count = os.write(input_write, view[:7919])
                    view = view[count:]
            finally:
                os.close(input_write)

        def write_socket():
            for i in range(0, len(outgoing), 4093):
                parent.sendall(outgoing[i:i + 4093])
            parent.shutdown(socket.SHUT_WR)

        def read_socket():
            result = bytearray()
            while True:
                data = parent.recv(511)
                if not data:
                    return bytes(result)
                result.extend(data)

        def read_output():
            result = bytearray()
            try:
                while True:
                    data = os.read(output_read, 277)
                    if not data:
                        return bytes(result)
                    result.extend(data)
            finally:
                os.close(output_read)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                writers = [executor.submit(write_input), executor.submit(write_socket)]
                socket_result = executor.submit(read_socket)
                output_result = executor.submit(read_output)
                for writer in writers:
                    writer.result(timeout=20)
                self.assertEqual(socket_result.result(timeout=20), incoming)
                self.assertEqual(output_result.result(timeout=20), outgoing)
            _, errors = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, errors.decode())
        finally:
            parent.close()
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
