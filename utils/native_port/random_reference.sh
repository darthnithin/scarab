#!/bin/bash
# Run within a Linux allocation to refresh the known glibc reference.
set -euo pipefail
cd "$(dirname "$0")"
cc -D_DEFAULT_SOURCE -DUSE_HOST_LIBC -std=c99 random_probe.c -o ../results/random-glibc-probe
../results/random-glibc-probe > ../results/random-glibc.txt
{
  uname -a
  getconf GNU_LIBC_VERSION
  cc --version
} > ../results/random-glibc-system.txt
