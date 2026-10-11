#!/usr/bin/env python3
"""Generate redistributable x86/REGDEPS traces for native-host parity.

Build Scarab first, then:
  python3 utils/native_port/trace_fixtures.py --build-dir src/build/native
The resulting suite.json can be run by parity.py with the output as --trace-root.
The generator decodes x86 bytes using the pinned DynamoRIO decoder and verifies
that its synthetic REGDEPS instructions can be encoded and decoded again.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=Path("src/build/native"))
    parser.add_argument("--output", type=Path, default=Path("build/native-trace-fixtures"))
    parser.add_argument("--decoder-library", type=Path, help="Override the built static or shared DynamoRIO decoder")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    build = args.build_dir.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    binary = output / "trace-fixtures"
    library = (args.decoder_library or build / "deps/libdrdecode.a").resolve()
    dynamic = library.suffix in {".so", ".dylib"}
    command = shlex.split(os.environ.get("CXX", "c++")) + [
        "-std=c++17", "-DX86_64", "-DMACOS" if platform.system() == "Darwin" else "-DLINUX", "-O2", "-g0",
        "-I" + str(build / "deps/dynamorio/include"),
        "-I" + str(root / "src/deps/dynamorio/clients/drcachesim/common"),
        str(root / "utils/native_port/trace_fixtures.cc"),
        str(library), "-o", str(binary)]
    if dynamic:
        command += ["-DSCARAB_DYNAMIC_DECODER", "-Wl,-rpath," + str(library.parent)]
    subprocess.run(command, check=True)
    result = subprocess.run([str(binary), str(output)], check=True, stdout=subprocess.PIPE)
    (output / "decoder.txt").write_bytes(result.stdout)
    cases = []
    files = {}
    for isa in ("x86", "regdeps"):
        raw = (output / f"{isa}.trace").read_bytes()
        (output / f"{isa}.trace.gz").write_bytes(gzip.compress(raw, mtime=0))
        with zipfile.ZipFile(output / f"{isa}.trace.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo(f"{isa}.trace", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
        for format_name, suffix in (("plain", ""), ("gzip", ".gz"), ("zip", ".zip")):
            trace = f"{isa}.trace{suffix}"
            files[trace] = hashlib.sha256((output / trace).read_bytes()).hexdigest()
            cases.append({"name": f"synthetic-{isa}-{format_name}", "trace": trace,
                          "args": ["--inst_limit=3000", "--full_warmup=200", "--use_fetched_count=1"]})
    descriptor = {"schema_version": 1, "description": "Synthetic x86 and REGDEPS traces in plain, gzip and ZIP containers.",
                  "coverage": ["integer load/store", "conditional branch taken/untaken", "direct call/return/jump",
                               "VEX vector register dependencies", "x87 stack operations", "cached and changed encodings",
                               "warmup and measurement"], "cases": cases}
    (output / "suite.json").write_text(json.dumps(descriptor, indent=2) + "\n")
    (output / "fixture-sha256.json").write_text(json.dumps(files, indent=2, sort_keys=True) + "\n")
    print(output / "suite.json")


if __name__ == "__main__":
    main()
