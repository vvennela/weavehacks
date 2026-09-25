#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_transpose(int n, const float *a, float *at) {
    const int vl = (int)svcntsw();
    for (int i = 0; i < n; i += 2 * vl) {
        const int rows0 = n-i < vl ? n-i : vl;
        const int rows1 = n-i-vl < vl ? n-i-vl : vl;
        svbool_t pi0 = svwhilelt_b32(i, n);
        svbool_t pi1 = svwhilelt_b32(i+vl, n);
        for (int k = 0; k < n; k += 2 * vl) {
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

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_gemm(int n, const float *at, const float *b, float *c) {
    const int vl = (int)svcntsw();
    const size_t stride = (size_t)n;
    for (int i = 0; i < n; i += 2 * vl) {
        const int a_offset = n-i > vl ? vl : 0;
        const int rows0 = n-i < vl ? n-i : vl;
        const int rows1 = n-i-vl < vl ? n-i-vl : vl;
        svbool_t pi0 = svwhilelt_b32(i, n);
        svbool_t pi1 = svwhilelt_b32(i+vl, n);
        for (int j = 0; j < n; j += 2 * vl) {
            const int b_offset = n-j > vl ? vl : 0;
            svbool_t pj0 = svwhilelt_b32(j, n);
            svbool_t pj1 = svwhilelt_b32(j+vl, n);
            const float *ap = at;
            const float *bp = b;
            svzero_za();
            int k = 0;
            for (; k < n-1; k += 2) {
                /* Eight live input vectors feed four resident ZA tiles. */
                svfloat32_t a00 = svld1_f32(pi0, ap+i);
                svfloat32_t a01 = svld1_f32(pi1, ap+i+a_offset);
                svfloat32_t b00 = svld1_f32(pj0, bp+j);
                svfloat32_t b01 = svld1_f32(pj1, bp+j+b_offset);
                svfloat32_t a10 = svld1_f32(pi0, ap+stride+i);
                svfloat32_t a11 = svld1_f32(pi1, ap+stride+i+a_offset);
                svfloat32_t b10 = svld1_f32(pj0, bp+stride+j);
                svfloat32_t b11 = svld1_f32(pj1, bp+stride+j+b_offset);
                svmopa_za32_f32_m(0, pi0, pj0, a00, b00);
                svmopa_za32_f32_m(1, pi0, pj1, a00, b01);
                svmopa_za32_f32_m(2, pi1, pj0, a01, b00);
                svmopa_za32_f32_m(3, pi1, pj1, a01, b01);
                svmopa_za32_f32_m(0, pi0, pj0, a10, b10);
                svmopa_za32_f32_m(1, pi0, pj1, a10, b11);
                svmopa_za32_f32_m(2, pi1, pj0, a11, b10);
                svmopa_za32_f32_m(3, pi1, pj1, a11, b11);
                ap += 2 * stride;
                bp += 2 * stride;
            }
            if (k < n) {
                svfloat32_t a0 = svld1_f32(pi0, ap+i);
                svfloat32_t a1 = svld1_f32(pi1, ap+i+a_offset);
                svfloat32_t b0 = svld1_f32(pj0, bp+j);
                svfloat32_t b1 = svld1_f32(pj1, bp+j+b_offset);
                svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
            }
            for (int r = 0; r < rows0; ++r) {
                float *out = c+(size_t)(i+r)*stride+j;
                svst1_hor_za32(0, r, pj0, out);
                if (b_offset) svst1_hor_za32(1, r, pj1, out+vl);
            }
            for (int r = 0; r < rows1; ++r) {
                float *out = c+(size_t)(i+vl+r)*stride+j;
                svst1_hor_za32(2, r, pj0, out);
                if (b_offset) svst1_hor_za32(3, r, pj1, out+vl);
            }
        }
    }
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

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0) return;
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
