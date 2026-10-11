#include "scarab_sort.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static void merge_sort(unsigned char* base, size_t count, size_t size,
                       int (*compare)(const void*, const void*), unsigned char* scratch) {
  if (count < 2)
    return;
  const size_t middle = count / 2;
  merge_sort(base, middle, size, compare, scratch);
  merge_sort(base + middle * size, count - middle, size, compare, scratch);
  size_t left = 0, right = middle, next = 0;
  while (left < middle && right < count) {
    /* Select the left element on ties, preserving Linux's reference order. */
    const size_t chosen = compare(base + left * size, base + right * size) <= 0 ? left++ : right++;
    memcpy(scratch + next++ * size, base + chosen * size, size);
  }
  if (left < middle) {
    memcpy(scratch + next * size, base + left * size, (middle - left) * size);
    next += middle - left;
  }
  /* The untouched tail of the right half is already at its final position. */
  memcpy(base, scratch, next * size);
}

void scarab_stable_sort(void* base, size_t count, size_t size,
                        int (*compare)(const void*, const void*)) {
  if (count < 2 || size == 0)
    return;
  if (count > SIZE_MAX / size)
    abort();
  const size_t bytes = count * size;
  unsigned char local[1024];
  unsigned char* scratch = bytes <= sizeof(local) ? local : malloc(bytes);
  if (scratch == NULL)
    abort(); /* Never silently change tie ordering after an allocation failure. */
  merge_sort(base, count, size, compare, scratch);
  if (scratch != local)
    free(scratch);
}
