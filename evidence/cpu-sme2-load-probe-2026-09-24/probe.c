/* Compiler probe only: writes one row from each accumulator, not a GEMM. */
#include <arm_sve.h>
#include <arm_sme.h>
__attribute__((target("sme2"))) __arm_new("za") __arm_locally_streaming
void paired_load_probe(const float *a,const float *b,float *c) {
    svcount_t count = svptrue_c32();
    svbool_t all = svptrue_b32();
    svfloat32x2_t av = svld1_f32_x2(count,a);
    svfloat32x2_t bv = svld1_f32_x2(count,b);
    svfloat32_t a0=svget2_f32(av,0), a1=svget2_f32(av,1);
    svfloat32_t b0=svget2_f32(bv,0), b1=svget2_f32(bv,1);
    svzero_za();
    svmopa_za32_f32_m(0,all,all,a0,b0);
    svmopa_za32_f32_m(1,all,all,a0,b1);
    svmopa_za32_f32_m(2,all,all,a1,b0);
    svmopa_za32_f32_m(3,all,all,a1,b1);
    svst1_hor_za32(0,0,all,c);
    svst1_hor_za32(1,0,all,c+svcntsw());
    svst1_hor_za32(2,0,all,c+2*svcntsw());
    svst1_hor_za32(3,0,all,c+3*svcntsw());
}
