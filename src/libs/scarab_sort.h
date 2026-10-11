#ifndef SCARAB_SORT_H
#define SCARAB_SORT_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Stable ordering is part of simulated scheduling: equal-priority requests
 * retain their previous order, regardless of the host libc's qsort algorithm. */
void scarab_stable_sort(void* base, size_t count, size_t size,
                        int (*compare)(const void*, const void*));

#ifdef __cplusplus
}
#endif
#endif
