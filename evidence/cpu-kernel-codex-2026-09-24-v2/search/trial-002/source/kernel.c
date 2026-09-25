#include <arm_sve.h>
#include <arm_sme.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

static void fallback(int n, const float *a, const float *b, float *c) {
    const size_t N = (size_t)n;
    for (size_t i = 0; i < N; ++i) {
        for (size_t j = 0; j < N; ++j) {
            float sum = 0.0f;
            for (size_t k = 0; k < N; ++k)
                sum += a[i * N + k] * b[k * N + j];
            c[i * N + j] = sum;
        }
    }
}

#define PRODUCT_STEP(K) do { \
    const float *pa = panel + (K) * stride; \
    const float *pb = b + (K) * N + j; \
    svfloat32_t a0 = svld1_f32(pi0, pa); \
    svfloat32_t a1 = svld1_f32(pi1, pa + a_second); \
    svfloat32_t b0 = svld1_f32(pj0, pb); \
    svfloat32_t b1 = svld1_f32(pj1, pb + b_second); \
    svmopa_za32_f32_m(0, pi0, pj0, a0, b0); \
    svmopa_za32_f32_m(1, pi0, pj1, a0, b1); \
    svmopa_za32_f32_m(2, pi1, pj0, a1, b0); \
    svmopa_za32_f32_m(3, pi1, pj1, a1, b1); \
} while (0)

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void panel_gemm(int n, const float *a, const float *b,
                       float *c, float *panel) {
    const size_t N = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2 * vl;
    const size_t stride = N < width ? N : width;
    const size_t paired = N & ~(size_t)1;

    for (size_t i = 0; i < N; i += width) {
        const size_t remaining = N - i;
        const size_t rows0 = remaining < vl ? remaining : vl;
        const size_t rows1 = remaining > vl
            ? (remaining - vl < vl ? remaining - vl : vl) : 0;
        const size_t a_second = rows1 != 0 ? vl : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)i, (uint64_t)N);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)(i + vl),
                                         (uint64_t)N);

        /* Store only valid rows; the product loads use the same predicates. */
        for (size_t k = 0; k < N; k += vl) {
            const size_t cols = N - k < vl ? N - k : vl;
            const svbool_t pk = svwhilelt_b32((uint64_t)k, (uint64_t)N);
            for (size_t r = 0; r < rows0; ++r)
                svld1_hor_za32(0, (uint32_t)r, pk,
                              a + (i + r) * N + k);
            for (size_t r = 0; r < rows1; ++r)
                svld1_hor_za32(1, (uint32_t)r, pk,
                              a + (i + vl + r) * N + k);
            for (size_t s = 0; s < cols; ++s) {
                float *dst = panel + (k + s) * stride;
                svst1_ver_za32(0, (uint32_t)s, pi0, dst);
                if (rows1 != 0)
                    svst1_ver_za32(1, (uint32_t)s, pi1, dst + vl);
            }
        }

        for (size_t j = 0; j < N; j += width) {
            const size_t b_second = N - j > vl ? vl : 0;
            const svbool_t pj0 = svwhilelt_b32((uint64_t)j, (uint64_t)N);
            const svbool_t pj1 = svwhilelt_b32((uint64_t)(j + vl),
                                             (uint64_t)N);
            svzero_za();
            size_t k = 0;
            for (; k < paired; k += 2) {
                PRODUCT_STEP(k);
                PRODUCT_STEP(k + 1);
            }
            if (k < N)
                PRODUCT_STEP(k);

            for (size_t r = 0; r < rows0; ++r) {
                float *dst = c + (i + r) * N + j;
                svst1_hor_za32(0, (uint32_t)r, pj0, dst);
                if (b_second != 0)
                    svst1_hor_za32(1, (uint32_t)r, pj1, dst + vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                float *dst = c + (i + vl + r) * N + j;
                svst1_hor_za32(2, (uint32_t)r, pj0, dst);
                if (b_second != 0)
                    svst1_hor_za32(3, (uint32_t)r, pj1, dst + vl);
            }
        }
    }
}

#undef PRODUCT_STEP

void gemm(int n, const float *A, const float *B, float *C) {
    if (n <= 0)
        return;
    const size_t N = (size_t)n;
    if (N > SIZE_MAX / sizeof(float) / N) {
        fallback(n, A, B, C);
        return;
    }
    /* Retain the baseline allocation size; touch only one A panel. */
    float *panel = malloc(N * N * sizeof(float));
    if (panel == NULL) {
        fallback(n, A, B, C);
        return;
    }
    panel_gemm(n, A, B, C, panel);
    free(panel);
}
