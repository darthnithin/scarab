# Native host differential validation

`parity.py` runs the same x86 workload trace through two Scarab executables and
compares their complete simulation results. It requires only Python 3.9+.
The workload ISA remains x86; the candidate **host executable** must be ARM64
Mach-O for a native macOS claim. The runner records `file` output and host
architecture; an x86 Linux executable under Rosetta does not prove native parity.

## Comparison contract

The gate compares every field of every `*.stat.*.csv` file, including cumulative,
periodic, floating-point, alternative branch predictor, warmup, periodic dump,
and ROI files. It also compares every token of corresponding human-readable
statistics, **all Ramulator statistics**, the complete input parameters, expanded
output parameters, and simulation logs. Missing files, missing or duplicate
fields, differing parameters, unsuccessful process exits, and incomplete logs
fail. Decimal comparison uses **zero tolerance** and does not round integers
through Python `float` (including counters above 2^53).

The following host-dependent data is retained in the JSON audit but excluded
from simulation equality:

* The two `SIM_HOST_WALL_SECONDS` CSV fields and that row in text statistics.
* Input trace and output-directory paths in `PARAMS.out`. With runner provenance,
  both trace SHA-256 hashes must match despite different path names.
* Git revision, start/end timestamps, and KIPS host-throughput fields in logs.

`EXECUTION_TIME` is simulated processor time and **is compared**. No simulator
cycle, instruction, cache, predictor, prefetcher, DRAM, or simulated-time values
are discarded. Libc formatting differences (padding, NaN signs, decimal spelling)
are numerically equivalent but remain visible in `raw_byte_differences`.
`--strict-bytes` fails on any byte difference, including host metadata. Therefore
`simulation_equal: true` alone must not be described as byte-identical output.

Runner provenance additionally checks identical trace bytes, `PARAMS.in` bytes,
simulation arguments, and successful process exits. Require it for new runs:

```sh
python3 utils/native_port/parity.py compare results/linux/CASE results/macos/CASE \
  --require-provenance --report results/CASE-parity.json
```

Historical run folders can be compared without `--require-provenance`, but the
JSON then says `input_identity_verified: false`. Independently check historical
input checksums before using such a comparison as end-to-end evidence.

## Reproducible suite

`suite.json` selects one trace for each of the 20 SPEC2017 `rate_int_v2` workload
and input variants, using 100,000 warmup and 1,000,000 measured instructions.
Two additional MCF cases use small caches with RANDOM (1) and BRRIP (17)
replacement to exercise host-independent random numbers. A final MCF case uses
the original lab quickcheck: fast-forward 49M, warm up 1M, measure 1M.

The licensed traces are not committed. Supply them as
`TRACE_ROOT/<workload>/<cluster_id>.zip`, following the manifest. For example:

```sh
python3 utils/native_port/parity.py run \
  --manifest utils/native_port/suite.json \
  --binary build/native/scarab --params src/PARAMS.golden_cove \
  --trace-root /path/to/traces --output results/macos
```

Select one or several cases using repeated `--case NAME`. The runner refuses
to overwrite a nonempty case directory. Use `--jobs 4` to run four independent
cases concurrently within the machine's CPU and memory budget. On Linux, use `--library-path` when
running a bundled baseline with shared libraries. The simulator binary's hash
may differ across host architectures; the input trace and parameters may not.

For this user's previously downloaded Hummingbird corpus,
`hummingbird_worker.py` adapts the same suite to the CSE220 runtime and trace
paths. It refuses to run outside a Slurm allocation. Stage the three Python/C
files and manifest in `~/scarab-native-parity/tools`, create the parent
`results` directory, then use:

```sh
~/dev/perch/bin/perch run --host ndanday@hb.ucsc.edu \
  --workdir /home/ndanday/scarab-native-parity --partition 256x44 \
  --cpus 1 --mem 4G --time 10m --array '0-22%4' --name scarab-parity \
  --module miniconda3/3.13 --submit -- \
  python3 /home/ndanday/scarab-native-parity/tools/hummingbird_worker.py
```

The adapter uses the existing known Linux oracle; it is not a rebuild check.
After source changes, also build and run the modified source on Linux and
compare it to that oracle to detect changes shared by both new host builds.
The old course binary hangs with BRRIP because strategy-cache initialization
leaves tag-folding fields unset. That case requires the corresponding fixed
Linux build as its oracle; a hang cannot provide reference counters. Keep this
exception explicit when reporting results from the original course binary.

Run comparator failure-injection tests with:

```sh
python3 -m unittest discover -s utils/native_port -p 'test_parity.py' -v
```

`compare-suite` takes two result roots plus `--manifest suite.json --report
results/parity.json --require-provenance` and checks every selected case. Missing
or unfinished cases fail the suite. `test_random.py` compiles the portable PRNG
at O0 and O2 and compares 1.4 million samples against the committed glibc fixture
under `fixtures/`, including its independent cache-replacement generator and
the untouched global stream. The adjacent JSON records source hashes and the
compute-node toolchain that generated the reference.

## Coverage boundaries

The suite is broad real-workload regression, not an exhaustive x86 ISA proof.
It does not prove every optional simulator feature, cache policy, DRAM type,
multi-core configuration, REGDEPS/ARM trace format, or legacy Pin trace format.
Raw/gzip/zip input transport should be checked independently on equivalent
bytes. The existing 59 full 60M lab intervals provide a longer-duration gate
and must be rerun on the native candidate before claiming that entire campaign
matches. Reusing their measured outputs alone cannot prove a new binary.

Pin execution-driven tracing, checkpoint restore, and Intel PT recording are
separate from offline simulation. Passing this suite does not imply that native
ARM macOS can launch Linux/x86 workloads through Intel Pin.
