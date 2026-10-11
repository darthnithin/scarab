# Experimental remote Pin execution

**Validated scope:** two fixed-address, single-threaded `simple_loop` cases.
General application and multicore compatibility remain unverified. For the
fully tested trace workflow, start with [native macOS replay](native-macos.md).

The native ARM64 Scarab simulator can exchange execution-driven frontend
messages with a Linux Intel Pin process through SSH. The x86 program and Pin
run on the Linux compute node; Scarab's pipeline, caches, branch prediction, and
memory simulation run in the native Mac process. This requires a Linux host
with Slurm, Python 3.9+, a supported Intel Pin runtime, and a rebuilt Scarab Pin
tool. It does not provide native ARM64 Pin instrumentation.

The initial launcher supports one simulated core and one application thread.
It disables ASLR and Pin multithreading for repeatable fixed-address inputs.
Programs must already exist at their specified absolute Linux paths. Trace
replay remains entirely local and does not require this launcher or a VM.

## Prepare Linux

Build `pin_exec.so` from the same source revision as the native simulator,
using the existing `src/pin/pin_exec` makefile and a compatible `PIN_ROOT`.
The validated runtime was SDE 9.44's `pinkit` (Pin 3.31); build in plain Pin mode,
without `SCARAB_ENABLE_PINPLAY` or `ENABLE_PINPLAY`. Run compilation inside a
Slurm allocation according to the site's policy.

Copy `bin/scarab_remote_pin.py` to a remote absolute path and use that path for
`--helper`. The helper refuses to start Pin outside a Slurm allocation. The
local launcher requests one CPU, 2 GB, and ten minutes by default; select an
allowed partition and adjust `--mem` and `--time` for the workload. It prints
the Slurm job ID and node to stderr. SSH uses existing noninteractive login
credentials and no publicly exposed TCP listener.

## Launch

In a fresh local result directory containing the desired `PARAMS.in`, start:

```sh
SCARAB_SOCKET_PROTOCOL=framed-v1 /path/to/native/scarab \
  --frontend pin_exec_driven --pin_exec_driven_fe_socket ./pin_exec.socket \
  --inst_limit=10000 --full_warmup=0 > scarab.log 2>&1
```

From another terminal, connect the relay (replace the paths and host):

```sh
python3 bin/scarab_remote_pin.py local \
  --socket /absolute/local/result/pin_exec.socket \
  --host user@cluster.example.edu \
  --helper /home/user/scarab_remote_pin.py \
  --pin /home/user/pinkit/pin \
  --tool /home/user/scarab/src/pin/pin_exec/obj-intel64/pin_exec.so \
  --partition allowed-partition --time 00:10:00 --mem 2G \
  -- /home/user/program argument1
```

Use `--print-command` to inspect the SSH/Slurm command without submitting.
`--pin-arg=VALUE` appends one tool argument; repeat it for each argument.
The remote job uses a private temporary Unix socket. Its stdout carries only
base64 transport lines; Pin and program output go to stderr. Program stdin is closed
using `/dev/null`, so this launcher does not provide interactive input.
The default connection timeout
is 60 seconds per local/remote socket connection; Slurm queue time is separate.

## Transport and verification

Both endpoints must use `SCARAB_SOCKET_PROTOCOL=framed-v1`. This opt-in protocol
adds a versioned header and payload length, preserving messages when SSH splits
or combines writes. The relay additionally encodes its standard streams as
base64 lines, so Slurm's line buffering cannot stall a binary handshake.
Existing local Pin workflows retain the default legacy
protocol. Payloads use Scarab's packed little-endian ABI; both architectures
must use matching source and structure layouts. The transport probe checks
20-byte commands, 24-byte register values, and 1,071-byte operations.

Run the transport and relay tests with:

```sh
python3 -m unittest discover -s utils/native_port -p 'test_*.py'
```

The C++ probe exercises fragmented and coalesced messages, empty and maximum
payloads, malformed/truncated frames, interrupted partial writes, and message
reuse. The Python relay test exchanges more than 6 MB in both directions with
backpressure and half-close behavior. These checks establish transport behavior;
compare a real Linux-only execution with the native-Mac/remote-Pin execution
before claiming simulator parity for a program.

The initial fixed-address `src/pin/pin_exec/testing/simple_loop.s` checks pass:
natural termination retires 70 instructions in 305 simulated cycles, and an
instruction limit of 20 retires 20 instructions in 248 cycles. Both modes match
all 12,703 statistic fields, text statistics, Ramulator output, and normalized
logs against Linux-only execution; both simulator and Pin exit successfully.
This establishes these two single-core checks, not arbitrary application or
multicore execution coverage. Host wall time includes SSH latency and differs.
