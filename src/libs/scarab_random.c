#include "scarab_random.h"

#include <stdint.h>

/* Additive recurrence x[n] = x[n-31] + x[n-3] modulo 2^32,
 * with Park-Miller initialization and 310 discarded feedback values.
 * Mathematical algorithm: https://www.mathstat.dal.ca/~selinger/random/
 * Fixed-width arithmetic also defines overflow on every supported host. */
static uint32_t state[31];
static unsigned int cursor;
static int initialized;

static uint32_t next_word(void) {
  const unsigned int recent = (cursor + 28) % 31;
  state[cursor] += state[recent];
  const uint32_t value = state[cursor];
  cursor = (cursor + 1) % 31;
  return value;
}

void scarab_srand(unsigned int seed) {
  if (seed == 0)
    seed = 1;
  state[0] = seed;
  /* glibc interprets the initial seed as a signed 32-bit number. Avoid
   * implementation-defined unsigned-to-signed conversions for high seeds. */
  int64_t value = seed <= INT32_MAX ? (int64_t)seed : (int64_t)seed - INT64_C(4294967296);
  for (unsigned int i = 1; i < 31; ++i) {
    value = (INT64_C(16807) * value) % INT64_C(2147483647);
    if (value < 0)
      value += INT64_C(2147483647);
    state[i] = (uint32_t)value;
  }
  cursor = 3;
  for (unsigned int i = 0; i < 310; ++i)
    (void)next_word();
  initialized = 1;
}

int scarab_rand(void) {
  if (!initialized)
    scarab_srand(1);
  return (int)(next_word() >> 1);
}

int scarab_rand_replacement(void) {
  /* The legacy zero-initialized rand_repl_state[31] passed to setstate()
   * selects glibc's small-state LCG, not the default additive generator. */
  static uint32_t replacement_state;
  replacement_state = (UINT32_C(1103515245) * replacement_state + UINT32_C(12345)) & UINT32_C(0x7fffffff);
  return (int)replacement_state;
}
