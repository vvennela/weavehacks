/* Correctness-only ABI adapter: no layout conversion or performance claim. */
#include "ta.c"
#include "tb.c"
#include "tt.c"
void probe(int variant, const float *x, const float *y, float *c) {
    const void *parameters[22] = {0};
    parameters[4] = x;
    parameters[10] = y;
    parameters[16] = c;
    if (variant == 1) sera_libxsmm_ta(parameters);
    else if (variant == 2) sera_libxsmm_tb(parameters);
    else if (variant == 3) sera_libxsmm_tt(parameters);
}
