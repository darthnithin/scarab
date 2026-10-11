# Compiling Scarab

For Apple Silicon, follow the [native macOS guide](native-macos.md). It includes
a complete build and smoke test and does not require `PIN_ROOT`.

## Linux trace simulation

Install the compiler and library prerequisites in
[system requirements](system_requirements.md), then initialize the pinned
submodules. A direct CMake build of the simulator does not require the Pin runtime:

```sh
git submodule update --init --recursive
cmake -S src -B build/linux \
  -DCMAKE_BUILD_TYPE=SCARABOPT -DSCARAB_ENABLE_PT_MEMTRACE=ON
cmake --build build/linux --target scarab --parallel 4
```

The executable is `build/linux/scarab`. Use a separate build directory for each
host/toolchain. `SCARABOPT` is the optimized configuration used by the validation
suite; CMake `Release` changes assertion behavior and is not equivalent.

## Linux with the Pin execution frontend

The convenience Makefile also builds `pin_exec.so` on Linux. It therefore needs
`PIN_ROOT` to point at a compatible Intel Pin installation:

```sh
export PIN_ROOT=/absolute/path/to/pin
export SCARAB_ENABLE_PT_MEMTRACE=1
make -C src -j4 opt
```

This creates `src/build/opt/scarab` and updates the `src/scarab` symlink.
Pin version requirements depend on the workflow; see the
[tested runtimes](system_requirements.md#intel-pin-and-checkpoints) and
[remote execution guide](remote-pin.md). Pin is downloaded separately.

Use `make -C src -j4 dbg` for a debug build with AddressSanitizer. `opt-avx` adds
Haswell/AVX2 host instructions and is for compatible x86 hosts only.
`make -C src clean` removes the local Makefile build directories and symlink.
