.text
.arch armv9-a+sme2
.global _sera_peak_abi_check
_sera_peak_abi_check:
    sub sp, sp, #80
    str x30, [sp, #64]
    stp d8, d9, [sp, #0]
    stp d10, d11, [sp, #16]
    stp d12, d13, [sp, #32]
    stp d14, d15, [sp, #48]
    mov x9, #0x1234
    fmov d8, x9
    fmov d9, x9
    fmov d10, x9
    fmov d11, x9
    fmov d12, x9
    fmov d13, x9
    fmov d14, x9
    fmov d15, x9
    blr x2
    mov x9, #0x1234
    mov x0, #0
    fmov x10, d8
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d9
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d10
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d11
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d12
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d13
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d14
    cmp x10, x9
    b.ne Labi_fail
    fmov x10, d15
    cmp x10, x9
    b.ne Labi_fail
    b Labi_restore
Labi_fail:
    mov x0, #1
Labi_restore:
    ldp d8, d9, [sp, #0]
    ldp d10, d11, [sp, #16]
    ldp d12, d13, [sp, #32]
    ldp d14, d15, [sp, #48]
    ldr x30, [sp, #64]
    add sp, sp, #80
    ret
