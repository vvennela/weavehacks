#include <arm_sve.h>
#include <arm_sme.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>

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
static void sme_transpose(int n, const float *a, float *at) {
    const size_t nn = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    for (size_t i = 0; i < nn; i += 2*vl) {
        const size_t rows0 = nn-i < vl ? nn-i : vl;
        const size_t rows1 = nn-i > vl ? (nn-i-vl < vl ? nn-i-vl : vl) : 0;
        svbool_t pi0 = svwhilelt_b32((uint64_t)i, (uint64_t)nn);
        svbool_t pi1 = svwhilelt_b32((uint64_t)(i+vl), (uint64_t)nn);
        for (size_t k = 0; k < nn; k += 2*vl) {
            const size_t cols0 = nn-k < vl ? nn-k : vl;
            const size_t cols1 = nn-k > vl ? (nn-k-vl < vl ? nn-k-vl : vl) : 0;
            svbool_t pk0 = svwhilelt_b32((uint64_t)k, (uint64_t)nn);
            svbool_t pk1 = svwhilelt_b32((uint64_t)(k+vl), (uint64_t)nn);
            for (size_t r = 0; r < rows0; ++r) {
                svld1_hor_za32(0, r, pk0, a+(i+r)*nn+k);
                if (cols1)
                    svld1_hor_za32(1, r, pk1, a+(i+r)*nn+k+vl);
            }
            for (size_t r = 0; r < rows1; ++r) {
                svld1_hor_za32(2, r, pk0, a+(i+vl+r)*nn+k);
                if (cols1)
                    svld1_hor_za32(3, r, pk1, a+(i+vl+r)*nn+k+vl);
            }
            for (size_t s = 0; s < cols0; ++s) {
                svst1_ver_za32(0, s, pi0, at+(k+s)*nn+i);
                if (rows1)
                    svst1_ver_za32(2, s, pi1, at+(k+s)*nn+i+vl);
            }
            for (size_t s = 0; s < cols1; ++s) {
                svst1_ver_za32(1, s, pi0, at+(k+vl+s)*nn+i);
                if (rows1)
                    svst1_ver_za32(3, s, pi1, at+(k+vl+s)*nn+i+vl);
            }
        }
    }
}

/* Consume the current vectors and fetch the next valid reduction step.
 * Each ZA tile receives contributions in increasing k order. */
#define PIPE_STEP() do { \
    ap += nn; \
    bp += nn; \
    svfloat32_t next_a0 = svld1_f32(all, ap+i); \
    svmopa_za32_f32_m(0, all, all, a0, b0); \
    svmopa_za32_f32_m(1, all, all, a0, b1); \
    svfloat32_t next_a1 = svld1_f32(all, ap+i+vl); \
    svmopa_za32_f32_m(2, all, all, a1, b0); \
    svfloat32_t next_b0 = svld1_f32(all, bp+j); \
    svmopa_za32_f32_m(3, all, all, a1, b1); \
    svfloat32_t next_b1 = svld1_f32(all, bp+j+vl); \
    a0 = next_a0; \
    a1 = next_a1; \
    b0 = next_b0; \
    b1 = next_b1; \
} while (0)

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void sme_gemm(int n, const float *at, const float *b, float *c) {
    const size_t nn = (size_t)n;
    const size_t vl = (size_t)svcntsw();
    const size_t width = 2*vl;
    const svbool_t all = svptrue_b32();
    for (size_t i = 0; i < nn; i += width) {
        const size_t rows0 = nn-i < vl ? nn-i : vl;
        const size_t rows1 = nn-i > vl ? (nn-i-vl < vl ? nn-i-vl : vl) : 0;
        const svbool_t pi0 = svwhilelt_b32((uint64_t)i, (uint64_t)nn);
        const svbool_t pi1 = svwhilelt_b32((uint64_t)(i+vl), (uint64_t)nn);
        for (size_t j = 0; j < nn; j += width) {
            svzero_za();
            if (nn-i >= width && nn-j >= width) {
                const float *ap = at;
                const float *bp = b;
                svfloat32_t a0 = svld1_f32(all, ap+i);
                svfloat32_t a1 = svld1_f32(all, ap+i+vl);
                svfloat32_t b0 = svld1_f32(all, bp+j);
                svfloat32_t b1 = svld1_f32(all, bp+j+vl);
                size_t k = 0;
                for (; k+4 < nn; k += 4) {
                    PIPE_STEP();
                    PIPE_STEP();
                    PIPE_STEP();
                    PIPE_STEP();
                }
                for (; k+1 < nn; ++k)
                    PIPE_STEP();
                svmopa_za32_f32_m(0, all, all, a0, b0);
                svmopa_za32_f32_m(1, all, all, a0, b1);
                svmopa_za32_f32_m(2, all, all, a1, b0);
                svmopa_za32_f32_m(3, all, all, a1, b1);
                for (size_t r = 0; r < vl; ++r) {
                    float *out0 = c+(i+r)*nn+j;
                    float *out1 = c+(i+vl+r)*nn+j;
                    svst1_hor_za32(0, r, all, out0);
                    svst1_hor_za32(1, r, all, out0+vl);
                    svst1_hor_za32(2, r, all, out1);
                    svst1_hor_za32(3, r, all, out1+vl);
                }
            } else {
                const size_t aoffset = rows1 ? vl : 0;
                const size_t boffset = nn-j > vl ? vl : 0;
                const svbool_t pj0 = svwhilelt_b32((uint64_t)j, (uint64_t)nn);
                const svbool_t pj1 = svwhilelt_b32((uint64_t)(j+vl), (uint64_t)nn);
                const float *ap = at;
                const float *bp = b;
                for (size_t k = 0; k < nn; ++k) {
                    svfloat32_t a0 = svld1_f32(pi0, ap+i);
                    svfloat32_t a1 = svld1_f32(pi1, ap+i+aoffset);
                    svfloat32_t b0 = svld1_f32(pj0, bp+j);
                    svfloat32_t b1 = svld1_f32(pj1, bp+j+boffset);
                    svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                    svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                    svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                    svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
                    ap += nn;
                    bp += nn;
                }
                for (size_t r = 0; r < rows0; ++r) {
                    float *out = c+(i+r)*nn+j;
                    svst1_hor_za32(0, r, pj0, out);
                    if (boffset)
                        svst1_hor_za32(1, r, pj1, out+vl);
                }
                for (size_t r = 0; r < rows1; ++r) {
                    float *out = c+(i+vl+r)*nn+j;
                    svst1_hor_za32(2, r, pj0, out);
                    if (boffset)
                        svst1_hor_za32(3, r, pj1, out+vl);
                }
            }
        }
    }
}

#undef PIPE_STEP

void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0)
        return;
    const size_t side = (size_t)n;
    float *at = NULL;
    if (side <= SIZE_MAX / sizeof(float) / side)
        at = malloc(side*side*sizeof(float));
    if (!at) {
        scalar_gemm(n, A, B, C);
        return;
    }
    sme_transpose(n, A, at);
    sme_gemm(n, at, B, C);
    free(at);
}
