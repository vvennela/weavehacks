#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

__attribute__((target("sme")))
__arm_locally_streaming
static int panel_width(void) {
    return 2 * (int)svcntsw();
}

static void scalar_gemm(int n, const float *a, const float *b, float *c) {
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            float sum = 0.0f;
            for (int k = 0; k < n; ++k)
                sum += a[(size_t)i*n+k] * b[(size_t)k*n+j];
            c[(size_t)i*n+j] = sum;
        }
    }
}

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void panel_gemm(int n, const float *a, const float *b,
                       float *c, float *packed) {
    const int vl = (int)svcntsw();
    const size_t width = (size_t)2 * vl;
    const size_t nn = (size_t)n;
    for (size_t i = 0; i < nn; i += width) {
        const int rows0 = nn-i < (size_t)vl ? (int)(nn-i) : vl;
        const int rows1 = nn-i > (size_t)vl
            ? (nn-i-vl < (size_t)vl ? (int)(nn-i-vl) : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)i, (uint64_t)nn);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)(i+vl), (uint64_t)nn);

        /* A panel is stored as packed[k * width + local_row]. */
        for (size_t k = 0; k < nn; k += width) {
            const int cols0 = nn-k < (size_t)vl ? (int)(nn-k) : vl;
            const int cols1 = nn-k > (size_t)vl
                ? (nn-k-vl < (size_t)vl ? (int)(nn-k-vl) : vl) : 0;
            const svbool_t pk0 = svwhilelt_b32((uint64_t)k, (uint64_t)nn);
            const svbool_t pk1 = svwhilelt_b32((uint64_t)(k+vl), (uint64_t)nn);
            for (int r = 0; r < rows0; ++r) {
                svld1_hor_za32(0, r, pk0, a+(i+r)*nn+k);
                if (cols1)
                    svld1_hor_za32(1, r, pk1, a+(i+r)*nn+k+vl);
            }
            for (int r = 0; r < rows1; ++r) {
                svld1_hor_za32(2, r, pk0, a+(i+vl+r)*nn+k);
                if (cols1)
                    svld1_hor_za32(3, r, pk1, a+(i+vl+r)*nn+k+vl);
            }
            for (int s = 0; s < cols0; ++s) {
                svst1_ver_za32(0, s, pi0, packed+(k+s)*width);
                if (rows1)
                    svst1_ver_za32(2, s, pi1, packed+(k+s)*width+vl);
            }
            for (int s = 0; s < cols1; ++s) {
                svst1_ver_za32(1, s, pi0, packed+(k+vl+s)*width);
                if (rows1)
                    svst1_ver_za32(3, s, pi1, packed+(k+vl+s)*width+vl);
            }
        }

        for (size_t j = 0; j < nn; j += width) {
            const svbool_t pj0 = svwhilelt_b32((uint64_t)j, (uint64_t)nn);
            const svbool_t pj1 = svwhilelt_b32((uint64_t)(j+vl), (uint64_t)nn);
            const size_t second_col = j+vl < nn ? (size_t)vl : 0;
            const float *ap = packed;
            const float *bp = b+j;
            svzero_za();
            for (int k = 0; k < n; ++k) {
                svfloat32_t a0 = svld1_f32(pi0, ap);
                svfloat32_t a1 = svld1_f32(pi1, ap+vl);
                svfloat32_t b0 = svld1_f32(pj0, bp);
                svfloat32_t b1 = svld1_f32(pj1, bp+second_col);
                svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
                ap += width;
                if (k+1 < n) bp += nn;
            }
            for (int r = 0; r < rows0; ++r) {
                svst1_hor_za32(0, r, pj0, c+(i+r)*nn+j);
                if (second_col)
                    svst1_hor_za32(1, r, pj1, c+(i+r)*nn+j+vl);
            }
            for (int r = 0; r < rows1; ++r) {
                svst1_hor_za32(2, r, pj0, c+(i+vl+r)*nn+j);
                if (second_col)
                    svst1_hor_za32(3, r, pj1, c+(i+vl+r)*nn+j+vl);
            }
        }
    }
}

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0) return;
    const size_t width = (size_t)panel_width();
    if ((size_t)n > SIZE_MAX / sizeof(float) / width) {
        scalar_gemm(n, A, B, C);
        return;
    }
    float *packed = malloc((size_t)n * width * sizeof(float));
    if (!packed) {
        scalar_gemm(n, A, B, C);
        return;
    }
    panel_gemm(n, A, B, C, packed);
    free(packed);
}
