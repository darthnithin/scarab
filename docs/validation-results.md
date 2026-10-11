# Recorded validation results

These results describe specific binaries and inputs tested on October 11, 2026.
They establish the scope below; future changes need their own validation.

## Full native macOS lab rerun

All **59 SimPoints across 20 SPEC2017 `rate_int_v2` workload/input variants**
were rerun with the native ARM64 macOS executable and Golden Cove parameters.
Each interval used 50 million warmup plus 10 million measured instructions:
3.54 billion configured instructions in total.

- All 59 comparisons passed with **1,498,954 exact numeric fields**.
- Complete text statistics, Ramulator output, parameters, and normalized logs
  also matched the historical Linux reference.
- The four aggregated report CSVs were byte-identical to the Linux versions.
- Every simulator execution in the rerun ran on the Mac. A remote host supplied
  missing input files only.

The native executable SHA-256 was
`d74785483f1bd23aa6521ac94ad8419ac560618f8a6caf02aebc823f0be6f86f`.
Its embedded revision label is `4ce1913`; the executable hash is the immutable
identity for this result. The parameter hash and per-case trace/result hashes
are in the [machine-readable record](../utils/native_port/lab1-validation-2026-10-11.json).
The [59-case manifest](../utils/native_port/suite-lab1.json) identifies the inputs
and arguments. Trace data and coursework reports are not distributed here.

### What “matches Linux” means

Simulation counters use exact decimal comparison with zero tolerance. This
includes simulated cycles, instructions, cache and predictor counts, DRAM
statistics, and simulated `EXECUTION_TIME`. Host wall-clock time, KIPS throughput,
timestamps, filesystem paths, and source-revision labels naturally differ.
Whitespace, decimal spelling, and NaN-sign formatting can differ while retaining
the same numeric values. See the [comparison contract](../utils/native_port/README.md#comparison-contract).

The historical Linux runs predate the harness's `parity-run.json` sidecars.
Their original trace/configuration hashes, command flags, completion records,
and worker or hybrid-run provenance were checked independently. The public
record preserves that distinction: `runner_input_identity_verified` is false,
while `historical_input_audit_passed` is true. New two-host runs should require
runner provenance on both sides.

One original wrapper invocation (`mcf_r/85716`) included an unused positional
`None` argument. The first native run matched every numeric field but differed
in that parameter-log token. The final run restored the original argument and
passed the strict comparison too; it was not waived or excluded.

## Earlier port acceptance

| Comparison | Cases | Exact numeric fields |
| --- | ---: | ---: |
| Original Linux → native ARM64, short workloads | 22 | 558,932 |
| Current-source Linux → native ARM64, including BRRIP | 23 | 584,338 |
| Original Linux → current-source Linux, short workloads | 22 | 558,932 |
| Historical Linux → native ARM64, selected full-length intervals | 20 | 508,120 |
| Current-source Linux → native ARM64, x86/REGDEPS fixtures | 6 | 152,436 |
| Original Linux → native ARM64, x86 fixtures | 3 | 76,218 |

The [earlier acceptance record](../utils/native_port/validation-2026-10-11.json)
contains its own binary and input hashes. Those checks used earlier immutable
binaries. The original course binary hangs in the BRRIP-specific test, so that
case used a fixed Linux build as its reference; it is excluded from the two
22-case legacy-oracle rows.

## Experimental remote execution

Two fixed-address `simple_loop` tests used Intel Pin on x86 Linux with Scarab
running natively on the Mac:

| Stop condition | Retired instructions | Simulated cycles | Exact numeric fields |
| --- | ---: | ---: | ---: |
| Natural program exit | 70 | 305 | 12,703 |
| Instruction limit of 20 | 20 | 248 | 12,703 |

Both Scarab and Pin exited successfully. Text/Ramulator statistics and normalized
parameters/logs also matched Linux-only execution. The
[execution record](../utils/native_port/execution-validation-2026-10-11.json)
binds the program, Pin tool, configuration, and result artifacts by hash.
See the [launcher guide](remote-pin.md) for requirements.

This verifies those two single-threaded cases only. It does not establish
arbitrary program compatibility, multicore execution, checkpoint restore,
Intel PT recording, or native Pin instrumentation on Apple Silicon.

## Reproduce a comparison

Start with the [synthetic smoke test](../README.md#try-it-without-downloading-a-workload),
then follow the [differential harness guide](../utils/native_port/README.md).
The workload manifests are public; compatible licensed/course traces must be
obtained separately. Raw historical run folders remain outside Git, so the
committed summaries are audit records, not a self-contained replay of those
historical comparisons.
