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

#define FULL_PRODUCT(A0, A1, B0, B1) do { \
    svmopa_za32_f32_m(0, all, all, A0, B0); \
    svmopa_za32_f32_m(1, all, all, A0, B1); \
    svmopa_za32_f32_m(2, all, all, A1, B0); \
    svmopa_za32_f32_m(3, all, all, A1, B1); \
} while (0)

#define EDGE_STEP(K) do { \
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
    const svbool_t all = svptrue_b32();

    for (size_t i = 0; i < N; i += width) {
        const size_t remaining = N - i;
        const size_t rows0 = remaining < vl ? remaining : vl;
        const size_t rows1 = remaining > vl
            ? (remaining - vl < vl ? remaining - vl : vl) : 0;
        const size_t a_second = rows1 != 0 ? vl : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)i, (uint64_t)N);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)(i + vl),
                                         (uint64_t)N);

        /* Four tiles transpose a 2VL by 2VL block into one A panel. */
        for (size_t k = 0; k < N; k += width) {
            const size_t left = N - k;
            const size_t cols0 = left < vl ? left : vl;
            const size_t cols1 = left > vl
                ? (left - vl < vl ? left - vl : vl) : 0;
            const svbool_t pk0 = svwhilelt_b32((uint64_t)k,
                                              (uint64_t)N);
            const svbool_t pk1 = svwhilelt_b32((uint64_t)(k + vl),
                                              (uint64_t)N);
            for (size_t r = 0; r < rows0; ++r) {
                const float *src = a + (i + r) * N + k;
                svld1_hor_za32(0, (uint32_t)r, pk0, src);
                if (cols1 != 0)
                    svld1_hor_za32(1, (uint32_t)r, pk1, src + vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                const float *src = a + (i + vl + r) * N + k;
                svld1_hor_za32(2, (uint32_t)r, pk0, src);
                if (cols1 != 0)
                    svld1_hor_za32(3, (uint32_t)r, pk1, src + vl);
            }
            for (size_t s = 0; s < cols0; ++s) {
                float *dst = panel + (k + s) * stride;
                svst1_ver_za32(0, (uint32_t)s, pi0, dst);
                if (rows1 != 0)
                    svst1_ver_za32(2, (uint32_t)s, pi1, dst + vl);
            }
            for (size_t s = 0; s < cols1; ++s) {
                float *dst = panel + (k + vl + s) * stride;
                svst1_ver_za32(1, (uint32_t)s, pi0, dst);
                if (rows1 != 0)
                    svst1_ver_za32(3, (uint32_t)s, pi1, dst + vl);
            }
        }

        for (size_t j = 0; j < N; j += width) {
            const size_t b_second = N - j > vl ? vl : 0;
            const svbool_t pj0 = svwhilelt_b32((uint64_t)j, (uint64_t)N);
            const svbool_t pj1 = svwhilelt_b32((uint64_t)(j + vl),
                                             (uint64_t)N);
            svzero_za();

            if (remaining >= width && N - j >= width) {
                const float *pa = panel;
                const float *pb = b + j;
                for (size_t k = 0; k < paired; k += 2) {
                    svfloat32_t a00 = svld1_f32(all, pa);
                    svfloat32_t a01 = svld1_f32(all, pa + vl);
                    svfloat32_t b00 = svld1_f32(all, pb);
                    svfloat32_t b01 = svld1_f32(all, pb + vl);
                    svfloat32_t a10 = svld1_f32(all, pa + width);
                    svfloat32_t a11 = svld1_f32(all, pa + width + vl);
                    svfloat32_t b10 = svld1_f32(all, pb + N);
                    svfloat32_t b11 = svld1_f32(all, pb + N + vl);
                    FULL_PRODUCT(a00, a01, b00, b01);
                    FULL_PRODUCT(a10, a11, b10, b11);
                    if (N - k > 2) {
                        pa += 2 * width;
                        pb += 2 * N;
                    }
                }
                if (paired != N) {
                    svfloat32_t a0 = svld1_f32(all, pa);
                    svfloat32_t a1 = svld1_f32(all, pa + vl);
                    svfloat32_t b0 = svld1_f32(all, pb);
                    svfloat32_t b1 = svld1_f32(all, pb + vl);
                    FULL_PRODUCT(a0, a1, b0, b1);
                }
                for (size_t r = 0; r < vl; ++r) {
                    float *dst0 = c + (i + r) * N + j;
                    float *dst1 = c + (i + vl + r) * N + j;
                    svst1_hor_za32(0, (uint32_t)r, all, dst0);
                    svst1_hor_za32(1, (uint32_t)r, all, dst0 + vl);
                    svst1_hor_za32(2, (uint32_t)r, all, dst1);
                    svst1_hor_za32(3, (uint32_t)r, all, dst1 + vl);
                }
            } else {
                size_t k = 0;
                for (; k < paired; k += 2) {
                    EDGE_STEP(k);
                    EDGE_STEP(k + 1);
                }
                if (k < N)
                    EDGE_STEP(k);
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
}

#undef FULL_PRODUCT
#undef EDGE_STEP

void gemm(int n, const float *A, const float *B, float *C) {
    if (n <= 0)
        return;
    const size_t N = (size_t)n;
    if (N > SIZE_MAX / sizeof(float) / N) {
        fallback(n, A, B, C);
        return;
    }
    float *panel = malloc(N * N * sizeof(float));
    if (panel == NULL) {
        fallback(n, A, B, C);
        return;
    }
    panel_gemm(n, A, B, C, panel);
    free(panel);
}
