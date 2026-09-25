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

/* Preserve the full transpose layout: at[k * n + i] = a[i * n + k]. */
__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_transpose(int n, const float *a, float *at) {
    const size_t side = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2 * vl;

    for (size_t i = 0; i < side; i += width) {
        const size_t remaining_rows = side - i;
        const size_t rows0 = remaining_rows < vl ? remaining_rows : vl;
        const size_t rows1 = remaining_rows > vl
            ? (remaining_rows - vl < vl ? remaining_rows - vl : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)0, (uint64_t)rows0);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)0, (uint64_t)rows1);

        for (size_t k = 0; k < side; k += width) {
            const size_t remaining_cols = side - k;
            const size_t cols0 = remaining_cols < vl ? remaining_cols : vl;
            const size_t cols1 = remaining_cols > vl
                ? (remaining_cols - vl < vl ? remaining_cols - vl : vl) : 0;
            const svbool_t pk0 = svwhilelt_b32((uint64_t)0, (uint64_t)cols0);
            const svbool_t pk1 = svwhilelt_b32((uint64_t)0, (uint64_t)cols1);

            for (size_t r = 0; r < rows0; ++r) {
                const float *src = a + (i + r) * side + k;
                svld1_hor_za32(0, (uint32_t)r, pk0, src);
                if (cols1)
                    svld1_hor_za32(1, (uint32_t)r, pk1, src + vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                const float *src = a + (i + vl + r) * side + k;
                svld1_hor_za32(2, (uint32_t)r, pk0, src);
                if (cols1)
                    svld1_hor_za32(3, (uint32_t)r, pk1, src + vl);
            }
            for (size_t s = 0; s < cols0; ++s) {
                float *dst = at + (k + s) * side + i;
                svst1_ver_za32(0, (uint32_t)s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(2, (uint32_t)s, pi1, dst + vl);
            }
            for (size_t s = 0; s < cols1; ++s) {
                float *dst = at + (k + vl + s) * side + i;
                svst1_ver_za32(1, (uint32_t)s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(3, (uint32_t)s, pi1, dst + vl);
            }
        }
    }
}

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_gemm(int n, const float *at, const float *b, float *c) {
    const size_t side = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2 * vl;

    /* Check the actual streaming vector length before using full tiles. */
    if (n == 512 && 512 % width == 0) {
        const svbool_t all = svptrue_b32();
        for (size_t i = 0; i < 512; i += width) {
            const float *abase = at + i;
            for (size_t j = 0; j < 512; j += width) {
                const float *bbase = b + j;
                svzero_za();

                /* No load or pointer advance extends beyond k=511. */
                for (size_t k = 0; k < 512; ++k) {
                    const float *ap = abase + k * 512;
                    const float *bp = bbase + k * 512;
                    svfloat32_t a0 = svld1_f32(all, ap);
                    svfloat32_t a1 = svld1_f32(all, ap + vl);
                    svfloat32_t b0 = svld1_f32(all, bp);
                    svfloat32_t b1 = svld1_f32(all, bp + vl);
                    svmopa_za32_f32_m(0, all, all, a0, b0);
                    svmopa_za32_f32_m(1, all, all, a0, b1);
                    svmopa_za32_f32_m(2, all, all, a1, b0);
                    svmopa_za32_f32_m(3, all, all, a1, b1);
                }
                for (size_t r = 0; r < vl; ++r) {
                    float *out = c + (i + r) * 512 + j;
                    svst1_hor_za32(0, (uint32_t)r, all, out);
                    svst1_hor_za32(1, (uint32_t)r, all, out + vl);
                }
                for (size_t r = 0; r < vl; ++r) {
                    float *out = c + (i + vl + r) * 512 + j;
                    svst1_hor_za32(2, (uint32_t)r, all, out);
                    svst1_hor_za32(3, (uint32_t)r, all, out + vl);
                }
            }
        }
        return;
    }

    /* General path: inactive second vectors use an in-bounds base. */
    for (size_t i = 0; i < side; i += width) {
        const size_t remaining_rows = side - i;
        const size_t rows0 = remaining_rows < vl ? remaining_rows : vl;
        const size_t rows1 = remaining_rows > vl
            ? (remaining_rows - vl < vl ? remaining_rows - vl : vl) : 0;
        const size_t second_row = rows1 ? vl : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)0, (uint64_t)rows0);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)0, (uint64_t)rows1);

        for (size_t j = 0; j < side; j += width) {
            const size_t remaining_cols = side - j;
            const size_t cols0 = remaining_cols < vl ? remaining_cols : vl;
            const size_t cols1 = remaining_cols > vl
                ? (remaining_cols - vl < vl ? remaining_cols - vl : vl) : 0;
            const size_t second_col = cols1 ? vl : 0;
            const svbool_t pj0 = svwhilelt_b32((uint64_t)0, (uint64_t)cols0);
            const svbool_t pj1 = svwhilelt_b32((uint64_t)0, (uint64_t)cols1);
            svzero_za();

            for (size_t k = 0; k < side; ++k) {
                const float *ap = at + k * side + i;
                const float *bp = b + k * side + j;
                svfloat32_t a0 = svld1_f32(pi0, ap);
                svfloat32_t a1 = svld1_f32(pi1, ap + second_row);
                svfloat32_t b0 = svld1_f32(pj0, bp);
                svfloat32_t b1 = svld1_f32(pj1, bp + second_col);
                svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
            }
            for (size_t r = 0; r < rows0; ++r) {
                float *out = c + (i + r) * side + j;
                svst1_hor_za32(0, (uint32_t)r, pj0, out);
                if (cols1)
                    svst1_hor_za32(1, (uint32_t)r, pj1, out + vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                float *out = c + (i + vl + r) * side + j;
                svst1_hor_za32(2, (uint32_t)r, pj0, out);
                if (cols1)
                    svst1_hor_za32(3, (uint32_t)r, pj1, out + vl);
            }
        }
    }
}

void gemm(int n, const float *A, const float *B, float *C) {
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

    sme_transpose(n, A, at);
    sme_gemm(n, at, B, C);
    free(at);
}
