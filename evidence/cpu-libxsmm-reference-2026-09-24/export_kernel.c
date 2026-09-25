/* Offline generation only. The exported kernel has no LIBXSMM runtime dependency. */
#include <libxsmm.h>
#include <stddef.h>
#include <stdio.h>

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    libxsmm_init();
    const libxsmm_gemm_shape shape = libxsmm_create_gemm_shape(
        512, 512, 512, 512, 512, 512,
        LIBXSMM_DATATYPE_F32, LIBXSMM_DATATYPE_F32,
        LIBXSMM_DATATYPE_F32, LIBXSMM_DATATYPE_F32);
    libxsmm_gemmfunction kernel = libxsmm_dispatch_gemm(
        shape, LIBXSMM_GEMM_FLAG_BETA_0, LIBXSMM_GEMM_PREFETCH_NONE);
    libxsmm_kernel_info info;
    if (!kernel || libxsmm_get_kernel_info((const void *)kernel, &info) != 0) return 3;
    if (info.is_reference_kernel || !info.code_size || info.code_size % 4) return 4;
    FILE *out = fopen(argv[1], "wb");
    if (!out) return 5;
    if (fwrite((const void *)kernel, 1, info.code_size, out) != info.code_size) return 6;
    if (fclose(out)) return 7;
    printf("{\"target\":\"%s\",\"code_size\":%zu,\"nflops\":%u,"
           "\"parameter_size\":%zu,\"a_offset\":%zu,\"b_offset\":%zu,\"c_offset\":%zu}\n",
           libxsmm_get_target_arch(), info.code_size, info.nflops,
           sizeof(libxsmm_gemm_param), offsetof(libxsmm_gemm_param,a.primary),
           offsetof(libxsmm_gemm_param,b.primary), offsetof(libxsmm_gemm_param,c.primary));
    libxsmm_finalize();
    return 0;
}
