#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

static void scalar_gemm(int n, const float *a, const float *b, float *c) {
    const size_t nn = (size_t)n;
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += a[(size_t)i * nn + k] * b[(size_t)k * nn + j];
            c[(size_t)i * nn + j] = sum;
        }
    }
}

/* Padding changes cache mapping without adding transpose stores. */
__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_transpose(int n, const float *a, float *at, size_t pitch) {
    const size_t nn = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2 * vl;
    for (size_t i = 0; i < nn; i += width) {
        const size_t remaining_rows = nn - i;
        const int rows0 = (int)(remaining_rows < vl ? remaining_rows : vl);
        const int rows1 = remaining_rows > vl
            ? (int)(remaining_rows - vl < vl ? remaining_rows - vl : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)0, (uint64_t)rows0);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)0, (uint64_t)rows1);
        for (size_t k = 0; k < nn; k += width) {
            const size_t remaining_cols = nn - k;
            const int cols0 = (int)(remaining_cols < vl ? remaining_cols : vl);
            const int cols1 = remaining_cols > vl
                ? (int)(remaining_cols - vl < vl ? remaining_cols - vl : vl) : 0;
            const svbool_t pk0 = svwhilelt_b32((uint64_t)0, (uint64_t)cols0);
            const svbool_t pk1 = svwhilelt_b32((uint64_t)0, (uint64_t)cols1);
            for (int r = 0; r < rows0; ++r) {
                svld1_hor_za32(0, r, pk0, a + (i + r) * nn + k);
                if (cols1)
                    svld1_hor_za32(1, r, pk1, a + (i + r) * nn + k + vl);
            }
            for (int r = 0; r < rows1; ++r) {
                svld1_hor_za32(2, r, pk0, a + (i + vl + r) * nn + k);
                if (cols1)
                    svld1_hor_za32(3, r, pk1, a + (i + vl + r) * nn + k + vl);
            }
            for (int s = 0; s < cols0; ++s) {
                svst1_ver_za32(0, s, pi0, at + (k + s) * pitch + i);
                if (rows1)
                    svst1_ver_za32(2, s, pi1, at + (k + s) * pitch + i + vl);
            }
            for (int s = 0; s < cols1; ++s) {
                svst1_ver_za32(1, s, pi0, at + (k + vl + s) * pitch + i);
                if (rows1)
                    svst1_ver_za32(3, s, pi1, at + (k + vl + s) * pitch + i + vl);
            }
        }
    }
}

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_gemm(int n, const float *at, size_t pitch,
                     const float *b, float *c) {
    const size_t nn = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2 * vl;
    for (size_t i = 0; i < nn; i += width) {
        const size_t remaining_rows = nn - i;
        const int rows0 = (int)(remaining_rows < vl ? remaining_rows : vl);
        const int rows1 = remaining_rows > vl
            ? (int)(remaining_rows - vl < vl ? remaining_rows - vl : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)0, (uint64_t)rows0);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)0, (uint64_t)rows1);
        const size_t second_row = rows1 ? vl : 0;
        for (size_t j = 0; j < nn; j += width) {
            const size_t remaining_cols = nn - j;
            const int cols0 = (int)(remaining_cols < vl ? remaining_cols : vl);
            const int cols1 = remaining_cols > vl
                ? (int)(remaining_cols - vl < vl ? remaining_cols - vl : vl) : 0;
            const svbool_t pj0 = svwhilelt_b32((uint64_t)0, (uint64_t)cols0);
            const svbool_t pj1 = svwhilelt_b32((uint64_t)0, (uint64_t)cols1);
            const size_t second_col = cols1 ? vl : 0;
            svzero_za();
            for (size_t k = 0; k < nn; ++k) {
                svfloat32_t a0 = svld1_f32(pi0, at + k * pitch + i);
                svfloat32_t a1 = svld1_f32(pi1, at + k * pitch + i + second_row);
                svfloat32_t b0 = svld1_f32(pj0, b + k * nn + j);
                svfloat32_t b1 = svld1_f32(pj1, b + k * nn + j + second_col);
                svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
            }
            for (int r = 0; r < rows0; ++r) {
                float *out = c + (i + r) * nn + j;
                svst1_hor_za32(0, r, pj0, out);
                if (cols1)
                    svst1_hor_za32(1, r, pj1, out + vl);
            }
            for (int r = 0; r < rows1; ++r) {
                float *out = c + (i + vl + r) * nn + j;
                svst1_hor_za32(2, r, pj0, out);
                if (cols1)
                    svst1_hor_za32(3, r, pj1, out + vl);
            }
        }
    }
}

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0)
        return;
    const size_t nn = (size_t)n;
    const size_t pitch = nn + 32;
    float *at = NULL;
    if (nn <= SIZE_MAX / sizeof(float) / pitch)
        at = malloc(nn * pitch * sizeof(float));
    if (!at) {
        scalar_gemm(n, A, B, C);
        return;
    }
    sme_transpose(n, A, at, pitch);
    sme_gemm(n, at, pitch, B, C);
    free(at);
}
