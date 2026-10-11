# Trace frontends

## Replay existing memtraces

The native macOS path replays existing x86 instruction/memory traces using the
DynamoRIO standalone reader and decoder. It does not instrument a live Mac
process. Begin with the [native build and run example](native-macos.md) or the
[Linux trace build](compiling-scarab.md#linux-trace-simulation).

The validated inputs include the encoded x86 traces used by the SPEC2017
`rate_int_v2` campaign and synthetic x86/REGDEPS traces in raw, gzip, and ZIP
containers. This does not establish support for every DynamoRIO format/version.
The six small fixtures can be generated from this repository; workload traces
must be supplied separately.

Scarab reads `PARAMS.in` in its working directory. Select the memtrace frontend
and trace path with:

```sh
/path/to/scarab --frontend memtrace --cbp_trace_r0=/absolute/path/to/trace.zip
```

Set instruction limits and warmup explicitly for reproducible experiments;
see the [complete example](native-macos.md#run-an-existing-trace). Compare the
same trace bytes and simulation configuration across hosts.

Older traces without embedded instruction encodings may depend on a matching
`modules.log`, workload binary, and libraries. A raw offline capture directory
is not automatically the same input as a processed encoded trace. Preserve the
metadata and conversion procedure associated with your trace collection.

## Capturing new traces

Capture and offline conversion are separate from simulation. Use the compatible
DynamoRIO instrumentation/conversion environment for the target workload.
The macOS build in this fork provides standalone replay components; it does
not build a native x86 instrumentation runtime. The repository's trace-fixture
generator constructs synthetic inputs and is not a general program tracer.

## Intel Processor Trace

Scarab also has a `pt` frontend. Native ARM64 macOS Intel PT recording and the
full PT workflow are outside the acceptance coverage described here. Enabling
`SCARAB_ENABLE_PT_MEMTRACE` builds trace support; it does not mean every frontend
or capture workflow has been validated. See [validation results](validation-results.md).
