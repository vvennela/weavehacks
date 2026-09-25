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
                sum += a[(size_t)i * n + k] * b[(size_t)k * n + j];
            c[(size_t)i * n + j] = sum;
        }
    }
}

/* Each expansion updates the four output tiles for one k value. */
#define FULL_STEP(T) do { \
    svfloat32_t a0 = svld1_f32(all, ap + (size_t)(T) * width); \
    svfloat32_t a1 = svld1_f32(all, ap + (size_t)(T) * width + vl); \
    svfloat32_t b0 = svld1_f32(all, bp + (size_t)(T) * stride); \
    svfloat32_t b1 = svld1_f32(all, bp + (size_t)(T) * stride + vl); \
    svmopa_za32_f32_m(0, all, all, a0, b0); \
    svmopa_za32_f32_m(1, all, all, a0, b1); \
    svmopa_za32_f32_m(2, all, all, a1, b0); \
    svmopa_za32_f32_m(3, all, all, a1, b1); \
} while (0)

__attribute__((target("sme")))
__arm_new("za") __arm_locally_streaming
static void panel_gemm(int n, const float *a, const float *b,
                       float *c, float *packed) {
    const int vl = (int)svcntsw();
    const int width = 2 * vl;
    const size_t stride = (size_t)n;
    const svbool_t all = svptrue_b32();

    for (int i = 0; i < n; ) {
        const int height = n - i < width ? n - i : width;
        const int rows0 = height < vl ? height : vl;
        const int rows1 = height > vl ? height - vl : 0;
        const svbool_t pi0 = svwhilelt_b32(0, rows0);
        const svbool_t pi1 = svwhilelt_b32(0, rows1);

        /* ZA transposes A into packed[k * height + row]. */
        for (int k = 0; k < n; ) {
            const int count = n - k < width ? n - k : width;
            const int cols0 = count < vl ? count : vl;
            const int cols1 = count > vl ? count - vl : 0;
            const svbool_t pk0 = svwhilelt_b32(0, cols0);
            const svbool_t pk1 = svwhilelt_b32(0, cols1);

            for (int r = 0; r < rows0; ++r) {
                const float *src = a + (size_t)(i + r) * stride + k;
                svld1_hor_za32(0, r, pk0, src);
                if (cols1)
                    svld1_hor_za32(1, r, pk1, src + vl);
            }
            for (int r = 0; r < rows1; ++r) {
                const float *src = a + (size_t)(i + vl + r) * stride + k;
                svld1_hor_za32(2, r, pk0, src);
                if (cols1)
                    svld1_hor_za32(3, r, pk1, src + vl);
            }
            for (int s = 0; s < cols0; ++s) {
                float *dst = packed + (size_t)(k + s) * height;
                svst1_ver_za32(0, s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(2, s, pi1, dst + vl);
            }
            for (int s = 0; s < cols1; ++s) {
                float *dst = packed + (size_t)(k + vl + s) * height;
                svst1_ver_za32(1, s, pi0, dst);
                if (rows1)
                    svst1_ver_za32(3, s, pi1, dst + vl);
            }
            k += count;
        }

        for (int j = 0; j < n; ) {
            const int columns = n - j < width ? n - j : width;
            svzero_za();

            if (height == width && columns == width) {
                int k = 0;
                for (; k <= n - 4; k += 4) {
                    const float *ap = packed + (size_t)k * width;
                    const float *bp = b + (size_t)k * stride + j;
                    FULL_STEP(0);
                    FULL_STEP(1);
                    FULL_STEP(2);
                    FULL_STEP(3);
                }
                for (; k < n; ++k) {
                    const float *ap = packed + (size_t)k * width;
                    const float *bp = b + (size_t)k * stride + j;
                    FULL_STEP(0);
                }
                for (int r = 0; r < vl; ++r) {
                    float *dst0 = c + (size_t)(i + r) * stride + j;
                    float *dst1 = c + (size_t)(i + vl + r) * stride + j;
                    svst1_hor_za32(0, r, all, dst0);
                    svst1_hor_za32(1, r, all, dst0 + vl);
                    svst1_hor_za32(2, r, all, dst1);
                    svst1_hor_za32(3, r, all, dst1 + vl);
                }
            } else {
                const int cols0 = columns < vl ? columns : vl;
                const int cols1 = columns > vl ? columns - vl : 0;
                const svbool_t pj0 = svwhilelt_b32(0, cols0);
                const svbool_t pj1 = svwhilelt_b32(0, cols1);
                const int aoffset = rows1 ? vl : 0;
                const int boffset = cols1 ? vl : 0;

                for (int k = 0; k < n; ++k) {
                    const float *ap = packed + (size_t)k * height;
                    const float *bp = b + (size_t)k * stride + j;
                    svfloat32_t a0 = svld1_f32(pi0, ap);
                    svfloat32_t a1 = svld1_f32(pi1, ap + aoffset);
                    svfloat32_t b0 = svld1_f32(pj0, bp);
                    svfloat32_t b1 = svld1_f32(pj1, bp + boffset);
                    svmopa_za32_f32_m(0, pi0, pj0, a0, b0);
                    svmopa_za32_f32_m(1, pi0, pj1, a0, b1);
                    svmopa_za32_f32_m(2, pi1, pj0, a1, b0);
                    svmopa_za32_f32_m(3, pi1, pj1, a1, b1);
                }
                for (int r = 0; r < rows0; ++r) {
                    float *dst = c + (size_t)(i + r) * stride + j;
                    svst1_hor_za32(0, r, pj0, dst);
                    if (cols1)
                        svst1_hor_za32(1, r, pj1, dst + vl);
                }
                for (int r = 0; r < rows1; ++r) {
                    float *dst = c + (size_t)(i + vl + r) * stride + j;
                    svst1_hor_za32(2, r, pj0, dst);
                    if (cols1)
                        svst1_hor_za32(3, r, pj1, dst + vl);
                }
            }
            j += columns;
        }
        i += height;
    }
}

#undef FULL_STEP

__attribute__((target("sme")))
void gemm(int n, const float *restrict A, const float *restrict B,
          float *restrict C) {
    if (n <= 0)
        return;

    /* svcntsw reports streaming vector length without entering streaming mode. */
    size_t panel_rows = 2 * (size_t)svcntsw();
    if (panel_rows > (size_t)n)
        panel_rows = (size_t)n;
    if ((size_t)n > SIZE_MAX / sizeof(float) / panel_rows) {
        scalar_gemm(n, A, B, C);
        return;
    }
    float *packed = malloc((size_t)n * panel_rows * sizeof(float));
    if (!packed) {
        scalar_gemm(n, A, B, C);
        return;
    }
    panel_gemm(n, A, B, C, packed);
    free(packed);
}
