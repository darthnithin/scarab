# System requirements

Requirements depend on whether you replay an existing trace or instrument a
live program. The simulated workload ISA is x86 even on an ARM64 host.

## Native Apple Silicon replay

Use Xcode Command Line Tools, Git, Python 3.9+, CMake, Boost headers, Snappy, and
LZ4. The [macOS guide](native-macos.md) provides Homebrew and build commands.
The validated host is Apple Silicon macOS; Intel Macs are outside this port's
acceptance coverage. Intel Pin and a Linux VM are not required for replay.

## Linux builds

The Linux comparison and Pin workflows were validated on x86-64 Linux.
Use a C99/C++17 compiler toolchain, Git, Python 3, CMake (Scarab requires 3.13 or
newer), Boost headers, and the development headers/libraries for Snappy, LZ4,
and zlib. Python validation/relay tools require Python 3.9+.
On Linux, the memtrace frontend also links the system `dl`, `rt`, and pthread
libraries. Intel XED, mbuild, and DynamoRIO are pinned Git submodules.
See [compiling Scarab](compiling-scarab.md) for the trace-only CMake build.

Older upstream documentation listed GCC/G++ 7.3.1, Clang 5.0.1, and Python 3.6.3.
Those are historical versions, not the requirements of this fork's newer tools.

## Intel Pin and checkpoints

Pin is needed to instrument live x86 programs, not to replay existing memtraces.
The existing Linux workflows documented Pin 3.15 and PinPlay 3.5. The experimental
remote-execution checks used SDE 9.44's `pinkit` (Pin 3.31) in plain Pin mode,
with `pin_exec.so` rebuilt from this fork. These are workflow-specific records,
not a guarantee that interchangeable Pin versions work.

The legacy checkpoint creation scripts depend on PinPlay. Native ARM64 Pin,
macOS checkpoint restore, and Intel PT recording are not provided by this port.
See [remote Pin execution](remote-pin.md) for the supported experimental path.

## Optional tools

The native build and differential harness do not require the legacy Python
launcher packages. For those launchers, install `bin/requirements.txt` in a
separate Python environment appropriate to the workflow.

Power modeling uses external McPAT/CACTI tooling and Perl. Upstream documented
McPAT 1.0 and CACTI 6.5; this native port has not validated that toolchain.
Optional GTest-based checks likewise require their own dependencies.
