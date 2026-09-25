#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>

/* Transpose layout: at[k*n+i]. */
__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_transpose(int n, const float *a, float *at) {
    const int vl = (int)svcntsw();
    for (int i = 0; i < n; i += 2*vl) {
        const int rows0 = n-i < vl ? n-i : vl;
        const int rows1 = n-i-vl < vl ? n-i-vl : vl;
        svbool_t pi0 = svwhilelt_b32(i, n);
        svbool_t pi1 = svwhilelt_b32(i+vl, n);
        for (int k = 0; k < n; k += 2*vl) {
            const int cols0 = n-k < vl ? n-k : vl;
            const int cols1 = n-k-vl < vl ? n-k-vl : vl;
            svbool_t pk0 = svwhilelt_b32(k, n);
            svbool_t pk1 = svwhilelt_b32(k+vl, n);
            for (int r = 0; r < rows0; ++r) {
                svld1_hor_za32(0, r, pk0, a+(size_t)(i+r)*n+k);
                if (cols1 > 0)
                    svld1_hor_za32(1, r, pk1, a+(size_t)(i+r)*n+k+vl);
            }
            for (int r = 0; r < rows1; ++r) {
                svld1_hor_za32(2, r, pk0, a+(size_t)(i+vl+r)*n+k);
                if (cols1 > 0)
                    svld1_hor_za32(3, r, pk1, a+(size_t)(i+vl+r)*n+k+vl);
            }
            for (int s = 0; s < cols0; ++s) {
                svst1_ver_za32(0, s, pi0, at+(size_t)(k+s)*n+i);
                if (rows1 > 0)
                    svst1_ver_za32(2, s, pi1, at+(size_t)(k+s)*n+i+vl);
            }
            for (int s = 0; s < cols1; ++s) {
                svst1_ver_za32(1, s, pi0, at+(size_t)(k+vl+s)*n+i);
                if (rows1 > 0)
                    svst1_ver_za32(3, s, pi1, at+(size_t)(k+vl+s)*n+i+vl);
            }
        }
    }
}

/* Four FP32 ZA tiles hold one 2VL x 2VL output block. */
__attribute__((target("sme2")))
__arm_new("za") __arm_locally_streaming
static void sme_gemm(int n, const float *at, const float *b, float *c) {
    const int vl = (int)svcntsw();
    for (int i = 0; i < n; i += 2*vl) {
        svbool_t pi0 = svwhilelt_b32(i, n);
        svbool_t pi1 = svwhilelt_b32(i+vl, n);
        for (int j = 0; j < n; j += 2*vl) {
            svbool_t pj0 = svwhilelt_b32(j, n);
            svbool_t pj1 = svwhilelt_b32(j+vl, n);
            svzero_za();

            if (n == 512 && i+2*vl <= n && j+2*vl <= n) {
                /* Both vectors of each pair are within the current row. */
                svcount_t count = svptrue_c32();
                for (int k = 0; k < n; ++k) {
                    svfloat32x2_t av = svld1_f32_x2(count, at+(size_t)k*n+i);
                    svfloat32x2_t bv = svld1_f32_x2(count, b+(size_t)k*n+j);
                    svfloat32_t a0 = svget2_f32(av, 0);
                    svfloat32_t a1 = svget2_f32(av, 1);
                    svfloat32_t b0 = svget2_f32(bv, 0);
                    svfloat32_t b1 = svget2_f32(bv, 1);
                    svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                    svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                    svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                    svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
                }
            } else {
                /* Original reduction for other sizes and partial tiles. */
                for (int k = 0; k < n; ++k) {
                    svfloat32_t a0 = svld1_f32(pi0, at+(size_t)k*n+i);
                    svfloat32_t a1 = svld1_f32(pi1, at+(size_t)k*n+(i+vl<n ? i+vl : i));
                    svfloat32_t b0 = svld1_f32(pj0, b+(size_t)k*n+j);
                    svfloat32_t b1 = svld1_f32(pj1, b+(size_t)k*n+(j+vl<n ? j+vl : j));
                    svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                    svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                    svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                    svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
                }
            }

            for (int r = 0; r < vl && i+r < n; ++r) {
                svst1_hor_za32(0, r, pj0, c+(size_t)(i+r)*n+j);
                if (j+vl < n)
                    svst1_hor_za32(1, r, pj1, c+(size_t)(i+r)*n+j+vl);
            }
            for (int r = 0; r < vl && i+vl+r < n; ++r) {
                svst1_hor_za32(2, r, pj0, c+(size_t)(i+vl+r)*n+j);
                if (j+vl < n)
                    svst1_hor_za32(3, r, pj1, c+(size_t)(i+vl+r)*n+j+vl);
            }
        }
    }
}

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0)
        return;

    float *at = malloc((size_t)n*n*sizeof(float));
    if (!at) {
        for (int i = 0; i < n; ++i) {
            for (int j = 0; j < n; ++j) {
                float x = 0;
                for (int k = 0; k < n; ++k)
                    x += A[(size_t)i*n+k]*B[(size_t)k*n+j];
                C[(size_t)i*n+j] = x;
            }
        }
        return;
    }

    sme_transpose(n, A, at);
    sme_gemm(n, at, B, C);
    free(at);
}
