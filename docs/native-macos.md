# Native Scarab on Apple Silicon

Scarab builds as an ARM64 macOS executable and simulates x86 instruction streams
from existing traces. Intel XED and the DynamoRIO standalone decoder compile
for the host; replay does not require an instrumentation runtime or Linux VM.

The full 59-interval lab campaign passed Linux/native comparison. Read the
[recorded validation results](validation-results.md) for the tested configuration,
exact comparison contract, and coverage limits.

## Prerequisites

- An Apple Silicon Mac, using an ARM64 terminal (`uname -m` should print `arm64`).
- Xcode Command Line Tools: `xcode-select --install` if not already installed.
- Git, Python 3.9+, CMake, Boost headers, Snappy, and LZ4.
- Homebrew packages built for ARM64, normally under `/opt/homebrew`.

```sh
brew install python cmake boost snappy lz4
git clone --recurse-submodules https://github.com/darthnithin/scarab.git
cd scarab
make -C src -j4 opt
file src/build/opt/scarab
```

The final command must identify a Mach-O ARM64 executable. The same executable
is available through `src/scarab`. For an existing checkout, initialize missing
submodules with `git submodule update --init --recursive` before building.
The macOS build enables the memtrace frontend by default and skips the Pin tool.

The four build workers are a starting point; adjust to your machine. Use
`make -C src clean` only when you intend to remove the simulator build directories
and `src/scarab` symlink. Simulation results stored elsewhere are unaffected.

## First smoke test

The [README quick start](../README.md#try-it-without-downloading-a-workload)
generates and runs six small x86/REGDEPS traces in raw, gzip, and ZIP formats.
It needs no licensed workloads. A successful local smoke run establishes that
your build can execute those cases; it does not itself perform a Linux comparison.

## Run an existing trace

Use an encoded x86 memtrace compatible with Scarab. Replace `TRACE_FILE` with an
absolute path. Run the following from the repository root:

```sh
SCARAB_REPO="$PWD"
TRACE_FILE=/absolute/path/to/trace.zip
mkdir -p results/first-trace
cp src/PARAMS.golden_cove results/first-trace/PARAMS.in
cd results/first-trace
"$SCARAB_REPO/src/build/opt/scarab" \
  --frontend memtrace --cbp_trace_r0="$TRACE_FILE" \
  --inst_limit=1100000 --full_warmup=100000 --use_fetched_count=1 \
  > sim.log 2>&1
```

This requests 100,000 warmup instructions followed by 1,000,000 measured
instructions. For the full lab configuration, use `--inst_limit=60000000`
and `--full_warmup=50000000` with the appropriate SimPoint trace. Keep the
trace, configuration, and limits identical when comparing hosts. Use a fresh
result directory for each run.

Check the process exit code, the `Scarab finished at` marker in `sim.log`, and
the recorded instruction counts. The `*.stat.0.csv` files contain both periodic
and cumulative statistics; use the measured counters for post-warmup analysis.
Scarab emits raw statistics. Workload weighting and report plots are separate
postprocessing steps, such as those in the course's Scarab infrastructure.

`PARAMS.in` describes the simulated processor. Choosing Golden Cove does not
require an Intel host, and the traces are not converted to ARM instructions.
Traces without embedded encodings may need their matching binaries/module data;
see [trace formats](memtrace.md).

## Alternative CMake build

```sh
cmake -S src -B build/macos \
  -DCMAKE_BUILD_TYPE=SCARABOPT -DSCARAB_ENABLE_PT_MEMTRACE=ON
cmake --build build/macos --target scarab --parallel 4
```

That executable is `build/macos/scarab`; this route does not create the Makefile's
`src/scarab` symlink. Substitute its build directory when generating fixtures.
`SCARABOPT` retains Scarab's assertion behavior. Standard CMake `Release` defines
`NDEBUG`, so it is not equivalent. `opt-avx` requires an x86 execution host.

CMake locates the macOS SDK and builds XED in each CMake build directory. Keep
macOS and Linux builds separate. Submodules stay at their pinned revisions; the
native decoder adapter builds standalone readers, not DynamoRIO injection.

## Troubleshooting

- **Wrong architecture:** check `uname -m`, `file` on the executable, and your
  package prefix. Reconfigure in a fresh build directory from an ARM64 shell.
- **Missing SDK:** check `xcode-select -p` and `xcrun --show-sdk-path`; finish the
  Command Line Tools installation before retrying.
- **Missing headers or libraries:** install the packages above. For a custom
  prefix, add `-DCMAKE_PREFIX_PATH=/your/prefix` to the CMake configuration.
- **Nonempty parity output directory:** choose a new `--output`; existing
  simulation results are deliberately protected.
- **Missing or incompatible trace:** confirm the path and trace format. The
  synthetic smoke test helps separate build problems from workload inputs.

## Live programs and Pin

Native Intel Pin instrumentation on Apple Silicon is not implemented.
The [experimental remote launcher](remote-pin.md) runs the x86 program and Pin
on Linux while the simulator runs on the Mac. It requires SSH and Slurm and has
passed two small single-threaded checks. General application, multicore,
checkpoint, and native Intel PT recording support are outside that validation.
