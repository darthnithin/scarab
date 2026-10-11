/* Native, sanitizer-friendly test of ordering and large/small scratch buffers. */
#include "libs/scarab_sort.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t priority; size_t insertion; unsigned char payload[37]; } entry;
static int compare(const void* a, const void* b) {
  const entry *x = a, *y = b;
  return (x->priority > y->priority) - (x->priority < y->priority);
}
int main(void) {
  for (size_t count = 0; count < 257; ++count) {
    for (unsigned pattern = 0; pattern < 5; ++pattern) {
      entry values[257];
      for (size_t i = 0; i < count; ++i) {
        values[i].priority = pattern == 0 ? 0 : pattern == 1 ? i :
                             pattern == 2 ? count - i : (i * 177 + 42) % (pattern * 3);
        values[i].insertion = i;
        memset(values[i].payload, (int)(i & 255), sizeof(values[i].payload));
      }
      scarab_stable_sort(values, count, sizeof(entry), compare);
      for (size_t i = 0; i < count; ++i) {
        for (size_t j = 0; j < sizeof(values[i].payload); ++j)
          assert(values[i].payload[j] == (values[i].insertion & 255));
        if (i > 0) {
          assert(values[i-1].priority <= values[i].priority);
          if (values[i-1].priority == values[i].priority)
            assert(values[i-1].insertion < values[i].insertion);
        }
      }
    }
  }
  puts("1285 stable sort cases passed");
}
