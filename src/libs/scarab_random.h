/* Reproducible simulator randomness, independent of the host C library. */
#ifndef SCARAB_RANDOM_H
#define SCARAB_RANDOM_H

#ifdef __cplusplus
extern "C" {
#endif

/* Matches Linux glibc rand()/srand(), including the default seed of 1.
 * One shared stream intentionally preserves the existing simulator's call order.
 * This is simulation state, not a cryptographic random-number generator. */
int scarab_rand(void);
void scarab_srand(unsigned int seed);
/* Historical REPL_RANDOM uses a separate glibc TYPE_0 stream, seeded with 0. */
int scarab_rand_replacement(void);

#ifdef __cplusplus
}
#endif
#endif
