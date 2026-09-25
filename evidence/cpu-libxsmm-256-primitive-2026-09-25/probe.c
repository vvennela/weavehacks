/* Correctness-only dense row-major 256-square adapter. */
#include "primitive.c"
void probe(const float *A, const float *B, float *C) {
    const void *parameters[22] = {0};
    parameters[4] = B;
    parameters[10] = A;
    parameters[16] = C;
    sera_libxsmm_256(parameters);
}
