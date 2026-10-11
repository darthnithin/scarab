/* Host support for the pinned DynamoRIO static decoder on ARM64 macOS.
 * Trace decoding never executes guest instructions or reads guest registers
 * from the host. The two upstream assembly helpers below are host services,
 * not part of the instruction decoder.
 */
#include <fenv.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

void dr_fpu_exception_init(void) {
  /* Equivalent to upstream's host FPCR/FPSR reset before private formatting. */
  fesetenv(FE_DFL_ENV);
}

void get_mmx_val(uint64_t* value, unsigned int index) {
  (void)value;
  (void)index;
  /* reg_get_value_ex's legacy MMX path reads physical host registers. That
   * operation cannot describe an x86 guest on ARM, and replay never uses it. */
  fputs("DynamoRIO: live MMX register reads are unavailable on an ARM64 host\n", stderr);
  abort();
}
