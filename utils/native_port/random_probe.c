/* Compare this program linked against Scarab on any host with Linux glibc.
 * Build with -DUSE_HOST_LIBC to generate the reference without Scarab code. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#ifndef USE_HOST_LIBC
#include "libs/scarab_random.h"
#define rand scarab_rand
#define srand scarab_srand
#endif

static void sample(const char *label, int (*next)(void)) {
  uint64_t hash = UINT64_C(14695981039346656037);
  for (int i = 0; i < 100000; ++i) {
    unsigned int value = (unsigned int)next();
    /* Hash explicit bytes so the evidence is independent of host byte order. */
    for (unsigned int j = 0; j < 4; ++j) {
      hash ^= (value >> (8 * j)) & 255;
      hash *= UINT64_C(1099511628211);
    }
  }
  printf("%s %016llx\n", label, (unsigned long long)hash);
}

int main(void) {
  const unsigned int seeds[] = {0, 1, 2, 17, 42, 12345, 0x7fffffffU,
                               0x80000000U, 0xdeadbeefU, 0xffffffffU};
  sample("default", rand);
  for (unsigned int i = 0; i < sizeof(seeds) / sizeof(seeds[0]); ++i) {
    char label[32];
    snprintf(label, sizeof(label), "%u", seeds[i]);
    srand(seeds[i]);
    sample(label, rand);
  }
  srand(1);
  sample("reseed-1", rand);
#ifdef USE_HOST_LIBC
  /* Scarab's historical cache replacement state is zero initialized, with
   * type word 0. Preserve/restore the default generator as cache_lib did. */
  uint32_t replacement_state[8] = {0};
  char *prior_state = setstate((char *)replacement_state);
  sample("replacement", rand);
  setstate(prior_state);
#else
  sample("replacement", scarab_rand_replacement);
#endif
  sample("global-after-replacement", rand);
  return 0;
}
