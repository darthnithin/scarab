# Scarab on Apple Silicon

Run Scarab's x86 microarchitecture simulations natively on an Apple Silicon Mac.
This fork of [UCSC's Scarab](https://github.com/litz-lab/scarab) adds an ARM64
macOS build and differential validation against Linux. The simulator runs as a
native Mac executable; the workload instruction stream remains x86.

**Verified:** all 59 CSE220 Lab 1 SimPoints across 20 SPEC2017 `rate_int_v2`
workload/input variants were rerun on macOS with 50M warmup + 10M measured
instructions each. All **1,498,954 compared numeric fields** matched the Linux
reference with zero tolerance. Host timing and metadata are excluded. See the
[validation results and scope](docs/validation-results.md).

## Support at a glance

| Workflow | Status in this fork |
| --- | --- |
| Replay existing x86 memtraces on Apple Silicon | Native ARM64; full 59-interval campaign verified |
| Generate and replay small synthetic traces locally | Six x86/REGDEPS smoke cases; no course traces needed |
| Run Scarab and Intel Pin together on x86 Linux | Existing Linux workflow |
| Mac simulator with Intel Pin on remote x86 Linux | Experimental SSH/Slurm launcher; two single-threaded checks verified |
| Run Intel Pin natively on Apple Silicon | Not implemented |
| Native checkpoint restore or Intel PT recording on macOS | Not validated or provided by this port |

Trace replay needs no VM, container, Pin installation, VPN, or remote machine.
You do need compatible trace files. This repository includes a synthetic trace
generator; SPEC binaries and course traces are not included.

## Quick start: macOS

Install Xcode Command Line Tools with `xcode-select --install` if needed.
With Homebrew installed, run:

```sh
brew install python cmake boost snappy lz4
git clone --recurse-submodules https://github.com/darthnithin/scarab.git
cd scarab
make -C src -j4 opt
file src/build/opt/scarab
```

The executable should be reported as `Mach-O 64-bit executable arm64`.
`src/scarab` is a symlink to the build. Use an ARM64 terminal and ARM64 Homebrew
packages; the [build guide](docs/native-macos.md) covers troubleshooting and
alternative build directories.

### Try it without downloading a workload

From the repository root, generate six small traces and run them:

```sh
python3 utils/native_port/trace_fixtures.py --build-dir src/build/opt
python3 utils/native_port/parity.py run \
  --manifest build/native-trace-fixtures/suite.json \
  --binary src/build/opt/scarab --params src/PARAMS.golden_cove \
  --trace-root build/native-trace-fixtures --output results/macos-smoke
```

Each case prints `exit=0` on success. Its directory under `results/macos-smoke`
contains `sim.log`, `PARAMS.in`, `PARAMS.out`, statistics, and `parity-run.json`.
Choose a new output directory when rerunning: the runner protects existing
results. This is a local smoke test; a Linux/native comparison requires both
result sets and the [parity checks](utils/native_port/README.md).

### Run your own trace

See [running a memtrace](docs/native-macos.md#run-an-existing-trace) for a complete
command, including the parameter file and instruction limits. The architecture
in `PARAMS.in` describes the simulated processor, not the Mac's CPU.

## Documentation

- [Native macOS build and first simulation](docs/native-macos.md)
- [System requirements](docs/system_requirements.md) and [Linux builds](docs/compiling-scarab.md)
- [Trace formats and replay](docs/memtrace.md)
- [Verification](docs/verification.md), [recorded results](docs/validation-results.md), and [differential harness](utils/native_port/README.md)
- [Experimental remote Pin execution](docs/remote-pin.md)
- [Linux execution-driven simulations](docs/running-scarab.md)
- [Troubleshooting](docs/common-problems.md)

## About Scarab

Scarab is a cycle-accurate simulator for out-of-order x86 processors. It models
fetch, decode, rename, scheduling and retirement, speculative execution,
branch prediction, prefetching, caches, and DRAM through Ramulator. It supports
SimPoints and configurable microarchitectures, including the Golden Cove
configuration used in this fork's validation.

The native port does not extend the simulated ISA to ARM. The validation here
also does not establish every optional feature or multicore configuration.
Scarab's broader limitations include no SMT, no modeled system-code performance,
and no full OS virtual-to-physical address translation.

For problems with this fork, [open an issue here](https://github.com/darthnithin/scarab/issues).
Include the source revision, host architecture, build command, configuration,
and a small reproducer where possible. Contributions can be proposed through
[this fork's pull requests](https://github.com/darthnithin/scarab/pulls).

## Credits and citation

Scarab was created by HPS and SAFARI with sponsorship from Intel Labs. Scarab
v2.0 and the underlying simulator work come from UCSC and the upstream project.
This is an independent fork adding macOS portability and validation tooling.

If you use Scarab v2.0 in research, retain the upstream citation:

```
@inproceedings{oh2024udp,
  author = {Oh, Surim and Xu, Mingsheng and Khan, Tanvir Ahmed and Kasikci, Baris and Litz, Heiner},
  title = {UDP: Utility-Driven Fetch Directed Instruction Prefetching},
  booktitle = {Proceedings of the 51st International Symposium on Computer Architecture (ISCA)},
  series = {ISCA 2024},
  year = {2024},
  month = jun,
}
```

## License

See [LICENSE](LICENSE) for the simulator's license and copyright notices.
Third-party dependencies retain their own licenses.
