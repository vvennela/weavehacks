#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

static void scalar_gemm(int n, const float *a, const float *b, float *c) {
    const size_t stride = (size_t)n;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += a[(size_t)i * stride + k] *
                       b[(size_t)k * stride + j];
            c[(size_t)i * stride + j] = sum;
        }
    }
}

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_run(int n, const float *a, const float *b,
                    float *c, float *at) {
    const size_t nn = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const svbool_t all = svptrue_b32();

    /* Preserve the baseline's four-tile ZA transpose. */
    for (size_t i = 0; i < nn; i += 2 * vl) {
        const size_t rows0 = nn - i < vl ? nn - i : vl;
        const size_t rows1 = nn - i > vl
            ? (nn - i - vl < vl ? nn - i - vl : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)0, (uint64_t)rows0);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)0, (uint64_t)rows1);
        for (size_t k = 0; k < nn; k += 2 * vl) {
            const size_t cols0 = nn - k < vl ? nn - k : vl;
            const size_t cols1 = nn - k > vl
                ? (nn - k - vl < vl ? nn - k - vl : vl) : 0;
            const svbool_t pk0 = svwhilelt_b32((uint64_t)0, (uint64_t)cols0);
            const svbool_t pk1 = svwhilelt_b32((uint64_t)0, (uint64_t)cols1);
            for (size_t r = 0; r < rows0; ++r) {
                const float *src = a + (i + r) * nn + k;
                svld1_hor_za32(0, (uint32_t)r, pk0, src);
                if (cols1)
                    svld1_hor_za32(1, (uint32_t)r, pk1, src + vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                const float *src = a + (i + vl + r) * nn + k;
                svld1_hor_za32(2, (uint32_t)r, pk0, src);
                if (cols1)
                    svld1_hor_za32(3, (uint32_t)r, pk1, src + vl);
            }
            for (size_t s = 0; s < cols0; ++s) {
                float *dst = at + (k + s) * nn + i;
                svst1_ver_za32(0, (uint32_t)s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(2, (uint32_t)s, pi1, dst + vl);
            }
            for (size_t s = 0; s < cols1; ++s) {
                float *dst = at + (k + vl + s) * nn + i;
                svst1_ver_za32(1, (uint32_t)s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(3, (uint32_t)s, pi1, dst + vl);
            }
        }
    }

    /* Four tiles share the same row vector and cover adjacent columns. */
    for (size_t i = 0; i < nn; i += vl) {
        const size_t rows = nn - i < vl ? nn - i : vl;
        const svbool_t pi = svwhilelt_b32((uint64_t)0, (uint64_t)rows);
        for (size_t j = 0; j < nn; j += 4 * vl) {
            svzero_za();
            if (rows == vl && nn - j >= 4 * vl) {
                for (size_t k = 0; k < nn; ++k) {
                    const float *bp = b + k * nn + j;
                    svfloat32_t av = svld1_f32(all, at + k * nn + i);
                    svfloat32_t b0 = svld1_f32(all, bp);
                    svfloat32_t b1 = svld1_f32(all, bp + vl);
                    svfloat32_t b2 = svld1_f32(all, bp + 2 * vl);
                    svfloat32_t b3 = svld1_f32(all, bp + 3 * vl);
                    svmopa_za32_f32_m(0, all, all, av, b0);
                    svmopa_za32_f32_m(1, all, all, av, b1);
                    svmopa_za32_f32_m(2, all, all, av, b2);
                    svmopa_za32_f32_m(3, all, all, av, b3);
                }
                for (size_t r = 0; r < vl; ++r) {
                    float *dst = c + (i + r) * nn + j;
                    svst1_hor_za32(0, (uint32_t)r, all, dst);
                    svst1_hor_za32(1, (uint32_t)r, all, dst + vl);
                    svst1_hor_za32(2, (uint32_t)r, all, dst + 2 * vl);
                    svst1_hor_za32(3, (uint32_t)r, all, dst + 3 * vl);
                }
            } else {
                const size_t remaining = nn - j;
                const size_t off1 = remaining > vl ? vl : 0;
                const size_t off2 = remaining > 2 * vl ? 2 * vl : 0;
                const size_t off3 = remaining > 3 * vl ? 3 * vl : 0;
                const svbool_t p0 = svwhilelt_b32((uint64_t)0, (uint64_t)remaining);
                const svbool_t p1 = svwhilelt_b32((uint64_t)vl, (uint64_t)remaining);
                const svbool_t p2 = svwhilelt_b32((uint64_t)(2 * vl), (uint64_t)remaining);
                const svbool_t p3 = svwhilelt_b32((uint64_t)(3 * vl), (uint64_t)remaining);
                for (size_t k = 0; k < nn; ++k) {
                    const float *bp = b + k * nn + j;
                    svfloat32_t av = svld1_f32(pi, at + k * nn + i);
                    svfloat32_t b0 = svld1_f32(p0, bp);
                    svfloat32_t b1 = svld1_f32(p1, bp + off1);
                    svfloat32_t b2 = svld1_f32(p2, bp + off2);
                    svfloat32_t b3 = svld1_f32(p3, bp + off3);
                    svmopa_za32_f32_m(0, pi, p0, av, b0);
                    svmopa_za32_f32_m(1, pi, p1, av, b1);
                    svmopa_za32_f32_m(2, pi, p2, av, b2);
                    svmopa_za32_f32_m(3, pi, p3, av, b3);
                }
                for (size_t r = 0; r < rows; ++r) {
                    float *dst = c + (i + r) * nn + j;
                    svst1_hor_za32(0, (uint32_t)r, p0, dst);
                    if (off1)
                        svst1_hor_za32(1, (uint32_t)r, p1, dst + off1);
                    if (off2)
                        svst1_hor_za32(2, (uint32_t)r, p2, dst + off2);
                    if (off3)
                        svst1_hor_za32(3, (uint32_t)r, p3, dst + off3);
                }
            }
        }
    }
}

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0)
        return;
    const size_t side = (size_t)n;
    float *at = NULL;
    if (side <= SIZE_MAX / sizeof(float) / side)
        at = malloc(side * side * sizeof(float));
    if (!at) {
        scalar_gemm(n, A, B, C);
        return;
    }
    sme_run(n, A, B, C, at);
    free(at);
}
