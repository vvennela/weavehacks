#include <arm_sve.h>
#include <arm_sme.h>
#include <stdio.h>
__attribute__((target("sme"))) __arm_locally_streaming
static unsigned streaming_fp32_lanes(void) { return (unsigned)svcntsw(); }
int main(void) { printf("%u\n", streaming_fp32_lanes()); return 0; }
