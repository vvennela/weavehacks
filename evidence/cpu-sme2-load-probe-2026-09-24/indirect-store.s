	.build_version macos, 26, 0	sdk_version 26, 5
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_indirect_store_probe           ; -- Begin function indirect_store_probe
	.p2align	2
_indirect_store_probe:                  ; @indirect_store_probe
	.cfi_startproc
; %bb.0:
	stp	d15, d14, [sp, #-80]!           ; 16-byte Folded Spill
	.cfi_def_cfa_offset 80
	stp	d13, d12, [sp, #16]             ; 16-byte Folded Spill
	stp	d11, d10, [sp, #32]             ; 16-byte Folded Spill
	stp	d9, d8, [sp, #48]               ; 16-byte Folded Spill
	stp	x29, x30, [sp, #64]             ; 16-byte Folded Spill
	add	x29, sp, #64
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset b8, -24
	.cfi_offset b9, -32
	.cfi_offset b10, -40
	.cfi_offset b11, -48
	.cfi_offset b12, -56
	.cfi_offset b13, -64
	.cfi_offset b14, -72
	.cfi_offset b15, -80
	smstart	sm
	mrs	x8, TPIDR2_EL0
	cbz	x8, LBB0_2
; %bb.1:
	bl	___arm_tpidr2_save
	msr	TPIDR2_EL0, xzr
LBB0_2:
	smstart	za
	mov	w12, #0                         ; =0x0
	zero	{za}
	ptrue	pn8.s
	ld1w	{ z16.s, z24.s }, pn8/z, [x0]
	ld1w	{ z17.s, z25.s }, pn8/z, [x1]
	zero	{za}
	ptrue	p0.s
	fmopa	za0.s, p0/m, p0/m, z16.s, z17.s
	fmopa	za1.s, p0/m, p0/m, z16.s, z25.s
	fmopa	za2.s, p0/m, p0/m, z24.s, z17.s
	fmopa	za3.s, p0/m, p0/m, z24.s, z25.s
	rdsvl	x8, #1
	lsr	x8, x8, #2
	mov	z0.s, #0                        ; =0x0
	mov	z1.d, z0.d
	mov	z1.s, p0/m, za0h.s[w12, 0]
	str	z1, [x2]
	mov	z1.d, z0.d
	mov	z1.s, p0/m, za1h.s[w12, 0]
	ptrue	p1.s
	st1w	{ z1.s }, p1, [x2, x8, lsl #2]
	lsl	x9, x8, #3
	mov	z1.d, z0.d
	mov	z1.s, p0/m, za2h.s[w12, 0]
	ptrue	p1.b
	st1b	{ z1.b }, p1, [x2, x9]
	mov	w9, #12                         ; =0xc
	mul	x8, x8, x9
	mov	z0.s, p0/m, za3h.s[w12, 0]
	st1b	{ z0.b }, p1, [x2, x8]
	smstop	za
	smstop	sm
	.cfi_def_cfa wsp, 80
	ldp	x29, x30, [sp, #64]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #48]               ; 16-byte Folded Reload
	ldp	d11, d10, [sp, #32]             ; 16-byte Folded Reload
	ldp	d13, d12, [sp, #16]             ; 16-byte Folded Reload
	ldp	d15, d14, [sp], #80             ; 16-byte Folded Reload
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	.cfi_restore b8
	.cfi_restore b9
	.cfi_restore b10
	.cfi_restore b11
	.cfi_restore b12
	.cfi_restore b13
	.cfi_restore b14
	.cfi_restore b15
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
