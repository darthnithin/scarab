#!/usr/bin/env python3
"""Relay Linux Pin to a native Scarab Unix socket through SSH and Slurm.

Copy this file to the remote --helper path first. Pin and the simulated program
execute inside one Slurm job; all simulator stages remain in the local Scarab
process. Both Scarab and the rebuilt Pin tool must enable framed-v1.
"""
import argparse
import base64
import errno
import os
from pathlib import Path
import selectors
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time


BUFFER_LIMIT = 1024 * 1024


def relay(sock, input_fd, output_fd, encode_stdio=False, exit_on_socket_eof=False):
    """Bidirectional bounded relay; preserve bytes across short reads/writes."""
    sock.setblocking(False)
    os.set_blocking(input_fd, False)
    os.set_blocking(output_fd, False)
    to_socket = bytearray()
    to_output = bytearray()
    encoded_input = bytearray()
    input_eof = socket_eof = socket_write_closed = output_closed = False
    with selectors.DefaultSelector() as selector:
        while True:
            if input_eof and not to_socket and not socket_write_closed:
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError as error:
                    if error.errno not in (errno.ENOTCONN, errno.EPIPE):
                        raise
                socket_write_closed = True
            if socket_eof and not to_output and not output_closed:
                os.close(output_fd)
                output_closed = True
            if socket_eof and not to_output and exit_on_socket_eof:
                if to_socket:
                    raise RuntimeError("Pin closed with undelivered simulator commands")
                break
            if input_eof and socket_eof and not to_socket and not to_output:
                break
            for key in list(selector.get_map().values()):
                selector.unregister(key.fd)
            socket_events = 0
            if not socket_eof and len(to_output) < BUFFER_LIMIT:
                socket_events |= selectors.EVENT_READ
            if to_socket:
                socket_events |= selectors.EVENT_WRITE
            if socket_events:
                selector.register(sock, socket_events, "socket")
            if not input_eof and len(to_socket) < BUFFER_LIMIT:
                selector.register(input_fd, selectors.EVENT_READ, "input")
            if to_output:
                selector.register(output_fd, selectors.EVENT_WRITE, "output")
            for key, events in selector.select():
                try:
                    if key.data == "input":
                        data = os.read(input_fd, min(65536, BUFFER_LIMIT - len(to_socket)))
                        if data:
                            if encode_stdio:
                                encoded_input.extend(data)
                                while b"\n" in encoded_input:
                                    line, _, rest = encoded_input.partition(b"\n")
                                    if len(line) > 87384:
                                        raise RuntimeError("Oversized SSH relay line")
                                    to_socket.extend(base64.b64decode(line, validate=True))
                                    encoded_input = bytearray(rest)
                                if len(encoded_input) > 87384:
                                    raise RuntimeError("Oversized SSH relay line")
                            else:
                                to_socket.extend(data)
                        else:
                            if encoded_input:
                                raise RuntimeError("Truncated SSH relay line")
                            input_eof = True
                    elif key.data == "output":
                        count = os.write(output_fd, to_output)
                        del to_output[:count]
                    else:
                        if events & selectors.EVENT_READ:
                            data = sock.recv(min(65536, BUFFER_LIMIT - len(to_output)))
                            if data:
                                # Slurm may hold task output until a newline.
                                # ASCII framing also avoids terminal byte conversion.
                                to_output.extend(base64.b64encode(data) + b"\n"
                                                 if encode_stdio else data)
                            else:
                                socket_eof = True
                        if events & selectors.EVENT_WRITE:
                            count = sock.send(to_socket)
                            del to_socket[:count]
                except (BlockingIOError, InterruptedError):
                    continue


def stop_process(process, group=False):
    if process.poll() is not None:
        return
    if group:
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if group:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def remote(args):
    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("The remote Pin process must run inside a Slurm allocation")
    print("Scarab Pin job {} on {}".format(os.environ["SLURM_JOB_ID"], socket.gethostname()),
          file=sys.stderr, flush=True)
    for candidate in (args.pin, args.tool, args.program[0]):
        if not Path(candidate).is_file():
            raise FileNotFoundError(candidate)
    environment = os.environ.copy()
    environment["SCARAB_SOCKET_PROTOCOL"] = "framed-v1"
    pin_root = Path(args.pin).resolve().parent
    environment["LD_LIBRARY_PATH"] = ":".join(
        [str(pin_root / "extras/xed-intel64/lib"), str(pin_root / "intel64/runtime/pincrt")]
        + ([environment["LD_LIBRARY_PATH"]] if environment.get("LD_LIBRARY_PATH") else []))
    with tempfile.TemporaryDirectory(prefix="scarab-pin-") as directory:
        path = str(Path(directory) / "pin.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen(1)
            listener.settimeout(0.2)
            command = ["setarch", "x86_64", "-R", args.pin, "-mt", "0", "-t", args.tool,
                       "-socket_path", path, "-core_id", "0"]
            command.extend(args.pin_arg)
            command.extend(["--"] + args.program)
            # Keep stdout exclusively for the binary transport.
            process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=sys.stderr,
                                       stderr=sys.stderr, start_new_session=True)
            try:
                deadline = time.monotonic() + args.connect_timeout
                while True:
                    try:
                        connection, _ = listener.accept()
                        break
                    except socket.timeout:
                        if process.poll() is not None:
                            raise RuntimeError("Pin exited before connecting (status {})".format(process.returncode))
                        if time.monotonic() > deadline:
                            raise TimeoutError("Pin did not connect to its relay socket")
                with connection:
                    relay(connection, sys.stdin.fileno(), sys.stdout.fileno(),
                          encode_stdio=True, exit_on_socket_eof=True)
                return process.wait(timeout=30)
            finally:
                stop_process(process, group=True)


def local(args):
    command = ["srun", "--job-name=scarab-pin-remote", "--ntasks=1", "--cpus-per-task=1",
               "--mem=" + args.mem, "--time=" + args.time, "--partition=" + args.partition]
    command.extend(["python3", args.helper, "remote", "--pin", args.pin, "--tool", args.tool,
                    "--connect-timeout", str(args.connect_timeout)])
    for value in args.pin_arg:
        command.append("--pin-arg=" + value)
    command.extend(["--"] + args.program)
    ssh_command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
                   "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                   args.host, shlex.join(command)]
    if args.print_command:
        print(shlex.join(ssh_command))
        return 0
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        deadline = time.monotonic() + args.connect_timeout
        while True:
            try:
                connection.connect(args.socket)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if time.monotonic() > deadline:
                    raise TimeoutError("Start local Scarab with framed-v1 and socket " + args.socket)
                time.sleep(0.1)
        process = subprocess.Popen(ssh_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   bufsize=0)
        try:
            # Duplicate pipe fds because relay closes its output on EOF, while
            # Popen retains ownership of the original file objects.
            input_fd = os.dup(process.stdout.fileno())
            output_fd = os.dup(process.stdin.fileno())
            process.stdout.close()
            process.stdin.close()
            try:
                relay(connection, input_fd, output_fd, encode_stdio=True)
            finally:
                os.close(input_fd)
                try:
                    os.close(output_fd)
                except OSError as error:
                    if error.errno != errno.EBADF:
                        raise
            return process.wait(timeout=30)
        finally:
            stop_process(process)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="mode", required=True)
    client = commands.add_parser("local", help="Connect local Scarab to a Linux Slurm Pin job")
    server = commands.add_parser("remote", help=argparse.SUPPRESS)
    client.add_argument("--socket", required=True)
    client.add_argument("--host", required=True)
    client.add_argument("--helper", required=True, help="Absolute remote path to this script")
    client.add_argument("--partition", required=True)
    client.add_argument("--time", default="00:10:00")
    client.add_argument("--mem", default="2G")
    client.add_argument("--print-command", action="store_true")
    for item in (client, server):
        item.add_argument("--pin", required=True, help="Absolute Linux Pin executable path")
        item.add_argument("--tool", required=True, help="Absolute rebuilt Linux pin_exec.so path")
        item.add_argument("--pin-arg", action="append", default=[], help="One Pin tool argument (use = for flags)")
        item.add_argument("--connect-timeout", type=float, default=60)
        item.add_argument("program", nargs=argparse.REMAINDER)
    return result


def main():
    arguments = parser().parse_args()
    if arguments.program and arguments.program[0] == "--":
        arguments.program = arguments.program[1:]
    if not arguments.program:
        parser().error("Pass an absolute Linux program path after --")
    def interrupted(_signal, _frame):
        raise KeyboardInterrupt
    for number in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, interrupted)
    try:
        return local(arguments) if arguments.mode == "local" else remote(arguments)
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print("Scarab remote Pin: " + str(error), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
