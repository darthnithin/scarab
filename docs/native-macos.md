# Building Scarab on Apple Silicon

Scarab can build as an ARM64 macOS executable while continuing to simulate the
x86 instruction streams in existing traces. The host architecture and the
simulated instruction set are separate: Intel XED decodes x86 instructions in
portable C, and the DynamoRIO standalone decoder and trace readers also compile
for the host. Replay does not need a Linux VM or an instrumentation runtime.

## Prerequisites and build

Install Xcode Command Line Tools, Python 3, CMake, Boost headers, Snappy, and LZ4.
With Homebrew, the additional packages are:

```sh
brew install cmake boost snappy lz4
git submodule update --init --recursive
make -C src -j4 opt
file src/build/opt/scarab
```

The final command must identify a Mach-O ARM64 executable on Apple Silicon.
The executable is also available through `src/scarab`. The macOS build enables
`SCARAB_ENABLE_PT_MEMTRACE` by default and skips the Intel Pin tool build.
Use `make -C src clean` to remove local simulator build products.

For a separate CMake build directory:

```sh
cmake -S src -B build/macos \
  -DCMAKE_BUILD_TYPE=SCARABOPT -DSCARAB_ENABLE_PT_MEMTRACE=ON
cmake --build build/macos --target scarab --parallel 4
```

`SCARABOPT` retains Scarab's established assertion behavior; standard CMake
`Release` also defines `NDEBUG` and is not the equivalent configuration.
`opt-avx` is specific to an x86 execution host and is rejected on ARM64.

CMake locates the macOS SDK for the XED build. It builds XED inside each CMake
build directory, so native macOS and Linux artifacts cannot overwrite each
other. Dependencies retain their pinned submodule revisions. The native
DynamoRIO build uses the upstream standalone decoder and readers, with a small
host adapter for filesystem queries and decoder support; it does not build
runtime injection or x86 host assembly.

## Run and validate

Run the executable in a directory containing `PARAMS.in`, using the same trace
and arguments as the Linux run. Existing encoded x86 trace inputs remain x86;
there is no conversion to ARM instructions.

The differential harness records binary architecture, input hashes, parameters,
exit status, and all simulator statistics. Follow
[`utils/native_port/README.md`](../utils/native_port/README.md) for the case
manifest and exact comparison commands. A successful build is not evidence that
simulation results match: run the Linux and native executables against the same
inputs and inspect the comparison report.

Wall-clock duration, timestamps, host throughput, filesystem paths, and source
revision identify a particular execution and naturally differ between hosts.
The comparison report retains those differences separately. Simulated cycles,
execution time, cache and branch statistics, DRAM results, and instruction counts
must compare without numerical tolerance. Byte identity is a separate strict
mode and must not be inferred from numerical equality.

Intel Pin execution-driven tracing, Linux checkpoint launch, and Intel PT
recording require their existing supported execution environments. A native
replay executable does not make those instrumentation tools available on ARM64
macOS; traces collected in the existing Linux workflow remain usable inputs.
For live execution with the simulator on the Mac and Intel Pin on a Linux
compute node, see [the SSH execution frontend](remote-pin.md).
