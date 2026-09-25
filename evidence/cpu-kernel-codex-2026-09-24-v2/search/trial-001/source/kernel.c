#include <arm_sve.h>
#include <arm_sme.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

static void fallback(int n, const float *a, const float *b, float *c) {
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += a[(size_t)i * n + k] * b[(size_t)k * n + j];
            c[(size_t)i * n + j] = sum;
        }
    }
}

__attribute__((target("sme")))
__arm_locally_streaming
static size_t panel_width(void) {
    return 2 * (size_t)svcntsw();
}

/* Each panel contains n consecutive pairs of vectors. Edge lanes are zero. */
__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void pack(int n, const float *a, const float *b,
                 float *ap, float *bp) {
    const size_t vl = svcntsw();
    const size_t width = 2 * vl;
    const size_t N = (size_t)n;
    const svbool_t all = svptrue_b32();

    for (size_t i = 0; i < N; i += width) {
        float *panel = ap + (i / width) * N * width;
        for (size_t k = 0; k < N; k += vl) {
            const svbool_t pk = svwhilelt_b32((uint64_t)k, (uint64_t)N);
            const size_t count = N - k < vl ? N - k : vl;
            svzero_za();
            for (size_t r = 0; r < vl && i + r < N; ++r)
                svld1_hor_za32(0, (uint32_t)r, pk, a + (i + r) * N + k);
            for (size_t r = 0; r < vl && i + vl + r < N; ++r)
                svld1_hor_za32(1, (uint32_t)r, pk,
                              a + (i + vl + r) * N + k);
            for (size_t s = 0; s < count; ++s) {
                svst1_ver_za32(0, (uint32_t)s, all, panel + (k + s) * width);
                svst1_ver_za32(1, (uint32_t)s, all,
                              panel + (k + s) * width + vl);
            }
        }
    }

    for (size_t j = 0; j < N; j += width) {
        float *panel = bp + (j / width) * N * width;
        const svbool_t p0 = svwhilelt_b32((uint64_t)j, (uint64_t)N);
        const svbool_t p1 = svwhilelt_b32((uint64_t)(j + vl), (uint64_t)N);
        const size_t second = j + vl < N ? j + vl : j;
        for (size_t k = 0; k < N; ++k) {
            svfloat32_t b0 = svld1_f32(p0, b + k * N + j);
            svfloat32_t b1 = svld1_f32(p1, b + k * N + second);
            svst1_f32(all, panel + k * width, b0);
            svst1_f32(all, panel + k * width + vl, b1);
        }
    }
}

#define PRODUCT_STEP(OFFSET) do { \
    svfloat32_t a0 = svld1_f32(all, pa + (OFFSET) * width); \
    svfloat32_t a1 = svld1_f32(all, pa + (OFFSET) * width + vl); \
    svfloat32_t b0 = svld1_f32(all, pb + (OFFSET) * width); \
    svfloat32_t b1 = svld1_f32(all, pb + (OFFSET) * width + vl); \
    svmopa_za32_f32_m(0, all, all, a0, b0); \
    svmopa_za32_f32_m(1, all, all, a0, b1); \
    svmopa_za32_f32_m(2, all, all, a1, b0); \
    svmopa_za32_f32_m(3, all, all, a1, b1); \
} while (0)

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void multiply(int n, const float *ap, const float *bp, float *c) {
    const size_t vl = svcntsw();
    const size_t width = 2 * vl;
    const size_t N = (size_t)n;
    const size_t unrolled = N & ~(size_t)3;
    const svbool_t all = svptrue_b32();

    for (size_t i = 0; i < N; i += width) {
        const float *a_panel = ap + (i / width) * N * width;
        for (size_t j = 0; j < N; j += width) {
            const float *pa = a_panel;
            const float *pb = bp + (j / width) * N * width;
            svzero_za();
            size_t k = 0;
            for (; k < unrolled; k += 4) {
                PRODUCT_STEP(0);
                PRODUCT_STEP(1);
                PRODUCT_STEP(2);
                PRODUCT_STEP(3);
                pa += 4 * width;
                pb += 4 * width;
            }
            for (; k < N; ++k) {
                PRODUCT_STEP(0);
                pa += width;
                pb += width;
            }

            const svbool_t p0 = svwhilelt_b32((uint64_t)j, (uint64_t)N);
            const svbool_t p1 = svwhilelt_b32((uint64_t)(j + vl), (uint64_t)N);
            for (size_t r = 0; r < vl && i + r < N; ++r) {
                float *out = c + (i + r) * N + j;
                svst1_hor_za32(0, (uint32_t)r, p0, out);
                if (j + vl < N)
                    svst1_hor_za32(1, (uint32_t)r, p1, out + vl);
            }
            for (size_t r = 0; r < vl && i + vl + r < N; ++r) {
                float *out = c + (i + vl + r) * N + j;
                svst1_hor_za32(2, (uint32_t)r, p0, out);
                if (j + vl < N)
                    svst1_hor_za32(3, (uint32_t)r, p1, out + vl);
            }
        }
    }
}

#undef PRODUCT_STEP

void gemm(int n, const float *A, const float *B, float *C) {
    if (n <= 0)
        return;
    const size_t N = (size_t)n;
    const size_t width = panel_width();
    const size_t panels = N / width + (N % width != 0);
    if (panels > SIZE_MAX / width) {
        fallback(n, A, B, C);
        return;
    }
    const size_t padded = panels * width;
    if (N > SIZE_MAX / padded / (2 * sizeof(float))) {
        fallback(n, A, B, C);
        return;
    }
    const size_t elements = N * padded;
    float *storage = malloc(2 * elements * sizeof(float));
    if (!storage) {
        fallback(n, A, B, C);
        return;
    }
    float *ap = storage;
    float *bp = storage + elements;
    pack(n, A, B, ap, bp);
    multiply(n, ap, bp, C);
    free(storage);
}
