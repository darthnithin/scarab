# Verifying Scarab

Choose a check that matches the workflow you intend to use.

## Native build smoke test

Follow the [README smoke test](../README.md#try-it-without-downloading-a-workload)
to generate and run six synthetic trace cases. No course or SPEC traces are
needed. Check for exit zero and completed output in every case directory.

## Exact Linux/macOS comparison

The [differential harness](../utils/native_port/README.md) runs matching inputs
on two hosts and compares complete simulator statistics with zero numerical
tolerance. It retains host timing and metadata differences separately.

The [recorded validation](validation-results.md) includes the full 59-interval
lab rerun, short regression suites, synthetic trace formats, and two limited
remote-Pin execution checks. Those results describe the tested binaries and
inputs; revalidate after changes that could affect simulation behavior.

For the harness, portable random generator, and socket/relay checks:

```sh
python3 -m unittest discover -s utils/native_port -p 'test_*.py'
```

Some tests compile small C/C++ probes, so a working host compiler is required.
A passing harness test suite is distinct from a workload parity run.

## Legacy Linux execution sanity check

`utils/qsort` contains a small program that sorts random data with libc's
`qsort()`. With the Linux Pin environment and launcher dependencies configured:

```sh
python3 bin/scarab_test_qsort.py /path/to/new-results-directory
```

`utils/qsort/ref_stats` contains historical reference statistics. They may differ
because the workload binary depends on its compiler. This is not the native
macOS trace smoke test and does not establish exact cross-host parity.
