// Original local diagnostic of SME accumulator independence.
// Motivated by https://scalable.uni-jena.de/opt/sme/micro.html
// Not a GEMM implementation or an official hill score.
.text
.arch armv9-a+sme2
.p2align 4
.global _sera_peak_1
_sera_peak_1:
    sub sp, sp, #64
    stp d8, d9, [sp, #0]
    stp d10, d11, [sp, #16]
    stp d12, d13, [sp, #32]
    stp d14, d15, [sp, #48]
    smstart
    ptrue p0.s
    fmov z0.s, #1.0
    fmov z1.s, #1.0
    zero {za}
    cbz x0, Lpeak1_done
.p2align 4
Lpeak1_loop:
    .rept 16
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    .endr
    subs x0, x0, #1
    b.ne Lpeak1_loop
Lpeak1_done:
    mov w12, #0
    st1w {za0h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    cntw x0
    smstop
    ldp d8, d9, [sp, #0]
    ldp d10, d11, [sp, #16]
    ldp d12, d13, [sp, #32]
    ldp d14, d15, [sp, #48]
    add sp, sp, #64
    ret
.p2align 4
.global _sera_peak_2
_sera_peak_2:
    sub sp, sp, #64
    stp d8, d9, [sp, #0]
    stp d10, d11, [sp, #16]
    stp d12, d13, [sp, #32]
    stp d14, d15, [sp, #48]
    smstart
    ptrue p0.s
    fmov z0.s, #1.0
    fmov z1.s, #1.0
    zero {za}
    cbz x0, Lpeak2_done
.p2align 4
Lpeak2_loop:
    .rept 16
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za1.s, p0/m, p0/m, z0.s, z1.s
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za1.s, p0/m, p0/m, z0.s, z1.s
    .endr
    subs x0, x0, #1
    b.ne Lpeak2_loop
Lpeak2_done:
    mov w12, #0
    st1w {za0h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    st1w {za1h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    cntw x0
    smstop
    ldp d8, d9, [sp, #0]
    ldp d10, d11, [sp, #16]
    ldp d12, d13, [sp, #32]
    ldp d14, d15, [sp, #48]
    add sp, sp, #64
    ret
.p2align 4
.global _sera_peak_4
_sera_peak_4:
    sub sp, sp, #64
    stp d8, d9, [sp, #0]
    stp d10, d11, [sp, #16]
    stp d12, d13, [sp, #32]
    stp d14, d15, [sp, #48]
    smstart
    ptrue p0.s
    fmov z0.s, #1.0
    fmov z1.s, #1.0
    zero {za}
    cbz x0, Lpeak4_done
.p2align 4
Lpeak4_loop:
    .rept 16
    fmopa za0.s, p0/m, p0/m, z0.s, z1.s
    fmopa za1.s, p0/m, p0/m, z0.s, z1.s
    fmopa za2.s, p0/m, p0/m, z0.s, z1.s
    fmopa za3.s, p0/m, p0/m, z0.s, z1.s
    .endr
    subs x0, x0, #1
    b.ne Lpeak4_loop
Lpeak4_done:
    mov w12, #0
    st1w {za0h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    st1w {za1h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    st1w {za2h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    st1w {za3h.s[w12, 0]}, p0, [x1]
    addvl x1, x1, #1
    cntw x0
    smstop
    ldp d8, d9, [sp, #0]
    ldp d10, d11, [sp, #16]
    ldp d12, d13, [sp, #32]
    ldp d14, d15, [sp, #48]
    add sp, sp, #64
    ret
