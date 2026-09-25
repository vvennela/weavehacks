/* Compiler probe only: writes one row from each accumulator, not a GEMM. */
#include <arm_sve.h>
#include <arm_sme.h>
__attribute__((target("sme2"))) __arm_new("za") __arm_locally_streaming
void indirect_store_probe(const float *a,const float *b,float *c) {
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
    svst1_f32(all,c+0*svcntsw(),svread_hor_za32_f32_m(svdup_f32(0),all,0,0));
    svst1_f32(all,c+1*svcntsw(),svread_hor_za32_f32_m(svdup_f32(0),all,1,0));
    svst1_f32(all,c+2*svcntsw(),svread_hor_za32_f32_m(svdup_f32(0),all,2,0));
    svst1_f32(all,c+3*svcntsw(),svread_hor_za32_f32_m(svdup_f32(0),all,3,0));
}
