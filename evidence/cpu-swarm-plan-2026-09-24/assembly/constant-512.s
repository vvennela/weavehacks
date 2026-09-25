	.build_version macos, 26, 0	sdk_version 26, 5
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_gemm                           ; -- Begin function gemm
	.p2align	2
_gemm:                                  ; @gemm
	.cfi_startproc
; %bb.0:
	stp	x24, x23, [sp, #-64]!           ; 16-byte Folded Spill
	stp	x22, x21, [sp, #16]             ; 16-byte Folded Spill
	stp	x20, x19, [sp, #32]             ; 16-byte Folded Spill
	stp	x29, x30, [sp, #48]             ; 16-byte Folded Spill
	add	x29, sp, #48
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	cmp	w0, #1
	b.lt	LBB0_12
; %bb.1:
	mov	x19, x3
	mov	x20, x2
	mov	x21, x1
	mov	x22, x0
	umull	x8, w0, w0
	lsl	x0, x8, #2
	bl	_malloc
	cbz	x0, LBB0_3
; %bb.2:
	mov	x23, x0
	mov	x0, x22
	mov	x1, x21
	mov	x2, x23
	bl	_sme_transpose
	mov	x0, x22
	mov	x1, x23
	mov	x2, x20
	mov	x3, x19
	bl	_sme_gemm
	mov	x0, x23
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	b	_free
LBB0_3:
	cmp	w22, #1
	b.ne	LBB0_5
; %bb.4:
	ldr	s0, [x21]
	ldr	s1, [x20]
	fmul	s0, s1, s0
	str	s0, [x19]
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB0_5:
	mov	w8, w22
	and	x9, x8, #0x7ffffffe
	subs	x10, x8, x9
	b.ne	LBB0_13
; %bb.6:
	lsl	x11, x8, #2
	lsl	x12, x8, #3
	add	x13, x21, #4
LBB0_7:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_8 Depth 2
                                        ;       Child Loop BB0_9 Depth 3
	mov	x14, #0                         ; =0x0
	mul	x15, x10, x8
	add	x15, x19, x15, lsl #2
	mov	x16, x20
LBB0_8:                                 ;   Parent Loop BB0_7 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_9 Depth 3
	movi.2d	v0, #0000000000000000
	mov	x17, x13
	mov	x0, x9
	mov	x1, x16
	movi.2d	v1, #0000000000000000
LBB0_9:                                 ;   Parent Loop BB0_7 Depth=1
                                        ;     Parent Loop BB0_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldp	s2, s3, [x17, #-4]
	ldr	s4, [x1, x11]
	ldr	s5, [x1]
	fmadd	s0, s5, s2, s0
	fmadd	s1, s4, s3, s1
	add	x1, x1, x12
	add	x17, x17, #8
	subs	x0, x0, #2
	b.ne	LBB0_9
; %bb.10:                               ;   in Loop: Header=BB0_8 Depth=2
	fadd	s0, s1, s0
	str	s0, [x15, x14, lsl #2]
	add	x14, x14, #1
	add	x16, x16, #4
	cmp	x14, x8
	b.ne	LBB0_8
; %bb.11:                               ;   in Loop: Header=BB0_7 Depth=1
	add	x10, x10, #1
	add	x13, x13, x11
	cmp	x10, x8
	b.ne	LBB0_7
LBB0_12:
	ldp	x29, x30, [sp, #48]             ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #32]             ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #16]             ; 16-byte Folded Reload
	ldp	x24, x23, [sp], #64             ; 16-byte Folded Reload
	ret
LBB0_13:
	mov	x11, #0                         ; =0x0
	add	x12, x21, #4
	lsl	x13, x8, #2
	lsl	x14, x8, #3
	ubfx	x16, x8, #1, #30
	umull	x15, w8, w16
	add	x15, x20, x15, lsl #3
	add	x16, x21, x16, lsl #3
LBB0_14:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_15 Depth 2
                                        ;       Child Loop BB0_16 Depth 3
                                        ;       Child Loop BB0_18 Depth 3
	mov	x17, #0                         ; =0x0
	mul	x0, x11, x8
	add	x0, x19, x0, lsl #2
	mov	x1, x15
	mov	x2, x20
LBB0_15:                                ;   Parent Loop BB0_14 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_16 Depth 3
                                        ;       Child Loop BB0_18 Depth 3
	movi.2d	v0, #0000000000000000
	mov	x3, x9
	mov	x4, x2
	mov	x5, x12
	movi.2d	v1, #0000000000000000
LBB0_16:                                ;   Parent Loop BB0_14 Depth=1
                                        ;     Parent Loop BB0_15 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldp	s2, s3, [x5, #-4]
	ldr	s4, [x4, x13]
	ldr	s5, [x4]
	fmadd	s0, s5, s2, s0
	fmadd	s1, s4, s3, s1
	add	x5, x5, #8
	add	x4, x4, x14
	subs	x3, x3, #2
	b.ne	LBB0_16
; %bb.17:                               ;   in Loop: Header=BB0_15 Depth=2
	fadd	s0, s1, s0
	mov	x3, x16
	mov	x4, x1
	mov	x5, x10
LBB0_18:                                ;   Parent Loop BB0_14 Depth=1
                                        ;     Parent Loop BB0_15 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	s1, [x3], #4
	ldr	s2, [x4]
	fmadd	s0, s2, s1, s0
	add	x4, x4, x13
	subs	x5, x5, #1
	b.ne	LBB0_18
; %bb.19:                               ;   in Loop: Header=BB0_15 Depth=2
	str	s0, [x0, x17, lsl #2]
	add	x17, x17, #1
	add	x2, x2, #4
	add	x1, x1, #4
	cmp	x17, x8
	b.ne	LBB0_15
; %bb.20:                               ;   in Loop: Header=BB0_14 Depth=1
	add	x11, x11, #1
	add	x12, x12, x13
	add	x16, x16, x13
	cmp	x11, x8
	b.ne	LBB0_14
	b	LBB0_12
	.cfi_endproc
                                        ; -- End function
	.p2align	2                               ; -- Begin function sme_transpose
_sme_transpose:                         ; @sme_transpose
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #208
	.cfi_def_cfa_offset 208
	stp	d15, d14, [sp, #48]             ; 16-byte Folded Spill
	stp	d13, d12, [sp, #64]             ; 16-byte Folded Spill
	stp	d11, d10, [sp, #80]             ; 16-byte Folded Spill
	stp	d9, d8, [sp, #96]               ; 16-byte Folded Spill
	stp	x28, x27, [sp, #112]            ; 16-byte Folded Spill
	stp	x26, x25, [sp, #128]            ; 16-byte Folded Spill
	stp	x24, x23, [sp, #144]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #160]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #176]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #192]            ; 16-byte Folded Spill
	add	x29, sp, #192
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	.cfi_offset b8, -104
	.cfi_offset b9, -112
	.cfi_offset b10, -120
	.cfi_offset b11, -128
	.cfi_offset b12, -136
	.cfi_offset b13, -144
	.cfi_offset b14, -152
	.cfi_offset b15, -160
                                        ; kill: def $w0 killed $w0 def $x0
	smstart	sm
	mrs	x8, TPIDR2_EL0
	cbz	x8, LBB1_2
; %bb.1:
	bl	___arm_tpidr2_save
	msr	TPIDR2_EL0, xzr
LBB1_2:
	smstart	za
	mov	x8, #0                          ; =0x0
	mov	w9, w0
	rdsvl	x10, #1
	lsr	x10, x10, #2
	lsl	x11, x10, #1
	lsl	x12, x10, #2
	add	x27, x1, x12
	mul	x13, x10, x9
	lsl	x16, x13, #3
	lsl	x14, x10, #3
	ubfiz	x15, x0, #2, #32
	add	x17, x15, #4
	mul	x17, x10, x17
	add	x26, x1, x17
	lsl	x13, x13, #2
	add	x25, x1, x13
	zero	{za}
	add	x24, x2, x12
	add	x3, x2, x17
	add	x4, x2, x13
	mov	x5, x9
	b	LBB1_4
LBB1_3:                                 ;   in Loop: Header=BB1_4 Depth=1
	sub	x5, x5, x11
	ldp	x27, x1, [sp, #24]              ; 16-byte Folded Reload
	add	x27, x27, x16
	add	x1, x1, x16
	ldp	x25, x26, [sp, #8]              ; 16-byte Folded Reload
	add	x26, x26, x16
	add	x25, x25, x16
	ldr	x24, [sp]                       ; 8-byte Folded Reload
	add	x24, x24, x14
	ldr	x2, [sp, #40]                   ; 8-byte Folded Reload
	add	x2, x2, x14
	add	x3, x3, x14
	add	x4, x4, x14
	add	x8, x8, x11
	cmp	x8, x9
	b.hs	LBB1_31
LBB1_4:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB1_6 Depth 2
                                        ;       Child Loop BB1_9 Depth 3
                                        ;       Child Loop BB1_14 Depth 3
                                        ;       Child Loop BB1_13 Depth 3
                                        ;       Child Loop BB1_17 Depth 3
                                        ;       Child Loop BB1_21 Depth 3
                                        ;       Child Loop BB1_23 Depth 3
                                        ;       Child Loop BB1_28 Depth 3
                                        ;       Child Loop BB1_30 Depth 3
	mov	x6, #0                          ; =0x0
	sub	x12, x9, x8
	subs	x13, x12, x10
	cmp	x13, x10
	csel	x13, x13, x10, lo
	cmp	x12, x10
	csel	x7, x12, x10, lo
	csel	x19, x13, xzr, hi
	cmp	x10, x5
	csel	x20, x10, x5, lo
	whilelo	p0.s, xzr, x7
	whilelo	p1.s, xzr, x19
	mov	x21, x4
	mov	x22, x3
	stp	x1, x2, [sp, #32]               ; 16-byte Folded Spill
	mov	x23, x2
	stp	x24, x25, [sp]                  ; 16-byte Folded Spill
	stp	x26, x27, [sp, #16]             ; 16-byte Folded Spill
	mov	x17, x1
	mov	x0, x27
	mov	x30, x9
	b	LBB1_6
LBB1_5:                                 ;   in Loop: Header=BB1_6 Depth=2
	sub	x30, x30, x11
	add	x0, x0, x14
	add	x17, x17, x14
	add	x26, x26, x14
	add	x25, x25, x14
	add	x24, x24, x16
	add	x23, x23, x16
	add	x22, x22, x16
	add	x21, x21, x16
	add	x6, x6, x11
	cmp	x6, x9
	b.hs	LBB1_3
LBB1_6:                                 ;   Parent Loop BB1_4 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB1_9 Depth 3
                                        ;       Child Loop BB1_14 Depth 3
                                        ;       Child Loop BB1_13 Depth 3
                                        ;       Child Loop BB1_17 Depth 3
                                        ;       Child Loop BB1_21 Depth 3
                                        ;       Child Loop BB1_23 Depth 3
                                        ;       Child Loop BB1_28 Depth 3
                                        ;       Child Loop BB1_30 Depth 3
	sub	x12, x9, x6
	subs	x13, x12, x10
	cmp	x13, x10
	csel	x13, x13, x10, lo
	cmp	x12, x10
	csel	x1, x12, x10, lo
	csel	x12, x13, xzr, hi
	cmp	x10, x30
	csel	x2, x10, x30, lo
	whilelo	p2.s, xzr, x1
	whilelo	p3.s, xzr, x12
	cbz	x7, LBB1_10
; %bb.7:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x27, x17
	cbz	x12, LBB1_14
; %bb.8:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x28, x0
LBB1_9:                                 ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za0h.s[w13, 0]}, p2/z, [x27]
	ld1w	{za1h.s[w13, 0]}, p3/z, [x28]
	add	x13, x13, #1
	add	x28, x28, x15
	add	x27, x27, x15
	cmp	x20, x13
	b.ne	LBB1_9
LBB1_10:                                ;   in Loop: Header=BB1_6 Depth=2
	cbz	x19, LBB1_18
; %bb.11:                               ;   in Loop: Header=BB1_6 Depth=2
	cbz	x12, LBB1_16
; %bb.12:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x27, x25
	mov	x28, x26
LBB1_13:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za2h.s[w13, 0]}, p2/z, [x27]
	ld1w	{za3h.s[w13, 0]}, p3/z, [x28]
	add	x13, x13, #1
	add	x28, x28, x15
	add	x27, x27, x15
	cmp	x19, x13
	b.ne	LBB1_13
	b	LBB1_18
LBB1_14:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za0h.s[w13, 0]}, p2/z, [x27]
	add	x13, x13, #1
	add	x27, x27, x15
	cmp	x20, x13
	b.ne	LBB1_14
; %bb.15:                               ;   in Loop: Header=BB1_6 Depth=2
	cbz	x19, LBB1_18
LBB1_16:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x27, x25
LBB1_17:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za2h.s[w13, 0]}, p2/z, [x27]
	add	x13, x13, #1
	add	x27, x27, x15
	cmp	x19, x13
	b.ne	LBB1_17
LBB1_18:                                ;   in Loop: Header=BB1_6 Depth=2
	cbz	x1, LBB1_25
; %bb.19:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x1, x23
	cbz	x19, LBB1_23
; %bb.20:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x27, x24
LBB1_21:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0v.s[w13, 0]}, p0, [x1]
	st1w	{za2v.s[w13, 0]}, p1, [x27]
	add	x13, x13, #1
	add	x27, x27, x15
	add	x1, x1, x15
	cmp	x2, x13
	b.ne	LBB1_21
; %bb.22:                               ;   in Loop: Header=BB1_6 Depth=2
	cbnz	x12, LBB1_27
	b	LBB1_5
LBB1_23:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0v.s[w13, 0]}, p0, [x1]
	add	x13, x13, #1
	add	x1, x1, x15
	cmp	x2, x13
	b.ne	LBB1_23
; %bb.24:                               ;   in Loop: Header=BB1_6 Depth=2
	cbnz	x12, LBB1_29
	b	LBB1_5
LBB1_25:                                ;   in Loop: Header=BB1_6 Depth=2
	cbz	x12, LBB1_5
; %bb.26:                               ;   in Loop: Header=BB1_6 Depth=2
	cbz	x19, LBB1_29
LBB1_27:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x1, x21
	mov	x2, x22
LBB1_28:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za1v.s[w13, 0]}, p0, [x1]
	st1w	{za3v.s[w13, 0]}, p1, [x2]
	add	x13, x13, #1
	add	x2, x2, x15
	add	x1, x1, x15
	cmp	x12, x13
	b.ne	LBB1_28
	b	LBB1_5
LBB1_29:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x1, x21
LBB1_30:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za1v.s[w13, 0]}, p0, [x1]
	add	x13, x13, #1
	add	x1, x1, x15
	cmp	x12, x13
	b.ne	LBB1_30
	b	LBB1_5
LBB1_31:
	smstop	za
	smstop	sm
	.cfi_def_cfa wsp, 208
	ldp	x29, x30, [sp, #192]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #176]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #160]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #144]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #128]            ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #112]            ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #96]               ; 16-byte Folded Reload
	ldp	d11, d10, [sp, #80]             ; 16-byte Folded Reload
	ldp	d13, d12, [sp, #64]             ; 16-byte Folded Reload
	ldp	d15, d14, [sp, #48]             ; 16-byte Folded Reload
	add	sp, sp, #208
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w25
	.cfi_restore w26
	.cfi_restore w27
	.cfi_restore w28
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
	.p2align	2                               ; -- Begin function sme_gemm
_sme_gemm:                              ; @sme_gemm
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #176
	.cfi_def_cfa_offset 176
	stp	d15, d14, [sp, #16]             ; 16-byte Folded Spill
	stp	d13, d12, [sp, #32]             ; 16-byte Folded Spill
	stp	d11, d10, [sp, #48]             ; 16-byte Folded Spill
	stp	d9, d8, [sp, #64]               ; 16-byte Folded Spill
	stp	x28, x27, [sp, #80]             ; 16-byte Folded Spill
	stp	x26, x25, [sp, #96]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #112]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #128]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #144]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #160]            ; 16-byte Folded Spill
	add	x29, sp, #160
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	.cfi_offset w19, -24
	.cfi_offset w20, -32
	.cfi_offset w21, -40
	.cfi_offset w22, -48
	.cfi_offset w23, -56
	.cfi_offset w24, -64
	.cfi_offset w25, -72
	.cfi_offset w26, -80
	.cfi_offset w27, -88
	.cfi_offset w28, -96
	.cfi_offset b8, -104
	.cfi_offset b9, -112
	.cfi_offset b10, -120
	.cfi_offset b11, -128
	.cfi_offset b12, -136
	.cfi_offset b13, -144
	.cfi_offset b14, -152
	.cfi_offset b15, -160
	smstart	sm
	mrs	x8, TPIDR2_EL0
	cbz	x8, LBB2_2
; %bb.1:
	bl	___arm_tpidr2_save
	msr	TPIDR2_EL0, xzr
LBB2_2:
	smstart	za
	zero	{za}
	rdsvl	x8, #1
	lsr	x8, x8, #2
	lsl	x9, x8, #1
	cmp	w0, #512
	b.ne	LBB2_4
; %bb.3:
	mov	w10, #512                       ; =0x200
	udiv	x11, x10, x9
	msub	x10, x11, x9, x10
	cbz	x10, LBB2_24
LBB2_4:
	mov	x10, #0                         ; =0x0
	mov	w11, w0
	lsl	x12, x8, #3
	lsl	x13, x11, #2
	add	x14, x3, x8, lsl #2
	mul	x15, x8, x11
	lsl	x16, x15, #3
	str	x16, [sp, #8]                   ; 8-byte Folded Spill
	add	x16, x13, #4
	madd	x16, x8, x16, x3
	add	x17, x3, x15, lsl #2
	mov	x0, x11
	b	LBB2_6
LBB2_5:                                 ;   in Loop: Header=BB2_6 Depth=1
	sub	x0, x0, x9
	add	x1, x1, x12
	ldr	x15, [sp, #8]                   ; 8-byte Folded Reload
	add	x14, x14, x15
	add	x3, x3, x15
	add	x16, x16, x15
	add	x17, x17, x15
	add	x10, x10, x9
	cmp	x10, x11
	b.hs	LBB2_35
LBB2_6:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB2_8 Depth 2
                                        ;       Child Loop BB2_9 Depth 3
                                        ;       Child Loop BB2_13 Depth 3
                                        ;       Child Loop BB2_20 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
                                        ;       Child Loop BB2_23 Depth 3
	mov	x4, #0                          ; =0x0
	sub	x15, x11, x10
	subs	x5, x15, x8
	cmp	x5, x8
	csel	x6, x5, x8, lo
	cmp	x15, x8
	csel	x5, x15, x8, lo
	csel	x6, x6, xzr, hi
	cmp	x8, x0
	csel	x7, x8, x0, lo
	cmp	x6, #0
	csel	x15, xzr, x8, eq
	whilelo	p0.s, xzr, x5
	whilelo	p1.s, xzr, x6
	lsl	x19, x15, #2
	mov	x20, x17
	mov	x21, x16
	mov	x22, x3
	mov	x23, x14
	mov	x24, x2
	b	LBB2_8
LBB2_7:                                 ;   in Loop: Header=BB2_8 Depth=2
	add	x24, x24, x12
	add	x23, x23, x12
	add	x22, x22, x12
	add	x21, x21, x12
	add	x20, x20, x12
	add	x4, x4, x9
	cmp	x4, x11
	b.hs	LBB2_5
LBB2_8:                                 ;   Parent Loop BB2_6 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB2_9 Depth 3
                                        ;       Child Loop BB2_13 Depth 3
                                        ;       Child Loop BB2_20 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
                                        ;       Child Loop BB2_23 Depth 3
	sub	x15, x11, x4
	subs	x25, x15, x8
	cmp	x25, x8
	csel	x25, x25, x8, lo
	cmp	x15, x8
	csel	x15, x15, x8, lo
	csel	x25, x25, xzr, hi
	cmp	x25, #0
	csel	x26, xzr, x8, eq
	whilelo	p2.s, xzr, x15
	whilelo	p3.s, xzr, x25
	zero	{za}
	lsl	x26, x26, #2
	mov	x27, x1
	mov	x28, x24
	mov	x30, x11
LBB2_9:                                 ;   Parent Loop BB2_6 Depth=1
                                        ;     Parent Loop BB2_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{ z0.s }, p0/z, [x27]
	add	x15, x27, x19
	ld1w	{ z1.s }, p1/z, [x15]
	ld1w	{ z2.s }, p2/z, [x28]
	add	x15, x28, x26
	ld1w	{ z3.s }, p3/z, [x15]
	fmopa	za0.s, p0/m, p2/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p3/m, z0.s, z3.s
	fmopa	za2.s, p1/m, p2/m, z1.s, z2.s
	fmopa	za3.s, p1/m, p3/m, z1.s, z3.s
	add	x28, x28, x13
	add	x27, x27, x13
	subs	x30, x30, #1
	b.ne	LBB2_9
; %bb.10:                               ;   in Loop: Header=BB2_8 Depth=2
	cbz	x5, LBB2_15
; %bb.11:                               ;   in Loop: Header=BB2_8 Depth=2
	mov	x15, #0                         ; =0x0
	cbz	x25, LBB2_19
; %bb.12:                               ;   in Loop: Header=BB2_8 Depth=2
	mov	x25, x22
	mov	x26, x23
LBB2_13:                                ;   Parent Loop BB2_6 Depth=1
                                        ;     Parent Loop BB2_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0h.s[w15, 0]}, p2, [x25]
	st1w	{za1h.s[w15, 0]}, p3, [x26]
	add	x15, x15, #1
	add	x26, x26, x13
	add	x25, x25, x13
	cmp	x7, x15
	b.ne	LBB2_13
; %bb.14:                               ;   in Loop: Header=BB2_8 Depth=2
	cbnz	x6, LBB2_17
	b	LBB2_7
LBB2_15:                                ;   in Loop: Header=BB2_8 Depth=2
	cbz	x6, LBB2_7
; %bb.16:                               ;   in Loop: Header=BB2_8 Depth=2
	cbz	x25, LBB2_22
LBB2_17:                                ;   in Loop: Header=BB2_8 Depth=2
	mov	x15, #0                         ; =0x0
	mov	x25, x20
	mov	x26, x21
LBB2_18:                                ;   Parent Loop BB2_6 Depth=1
                                        ;     Parent Loop BB2_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za2h.s[w15, 0]}, p2, [x25]
	st1w	{za3h.s[w15, 0]}, p3, [x26]
	add	x15, x15, #1
	add	x26, x26, x13
	add	x25, x25, x13
	cmp	x6, x15
	b.ne	LBB2_18
	b	LBB2_7
LBB2_19:                                ;   in Loop: Header=BB2_8 Depth=2
	mov	x25, x22
LBB2_20:                                ;   Parent Loop BB2_6 Depth=1
                                        ;     Parent Loop BB2_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0h.s[w15, 0]}, p2, [x25]
	add	x15, x15, #1
	add	x25, x25, x13
	cmp	x7, x15
	b.ne	LBB2_20
; %bb.21:                               ;   in Loop: Header=BB2_8 Depth=2
	cbz	x6, LBB2_7
LBB2_22:                                ;   in Loop: Header=BB2_8 Depth=2
	mov	x15, #0                         ; =0x0
	mov	x25, x20
LBB2_23:                                ;   Parent Loop BB2_6 Depth=1
                                        ;     Parent Loop BB2_8 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za2h.s[w15, 0]}, p2, [x25]
	add	x15, x15, #1
	add	x25, x25, x13
	cmp	x6, x15
	b.ne	LBB2_23
	b	LBB2_7
LBB2_24:
	cbz	x8, LBB2_36
; %bb.25:
	mov	x10, #0                         ; =0x0
	lsl	x11, x8, #3
	add	x12, x3, x8, lsl #2
	lsl	x20, x8, #12
	mov	w13, #2052                      ; =0x804
	madd	x14, x8, x13, x3
	ptrue	p0.s
	add	x15, x3, x8, lsl #11
LBB2_26:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB2_27 Depth 2
                                        ;       Child Loop BB2_28 Depth 3
                                        ;       Child Loop BB2_30 Depth 3
                                        ;       Child Loop BB2_32 Depth 3
	mov	x16, #0                         ; =0x0
	mov	x17, x15
	mov	x0, x14
	mov	x4, x3
	mov	x5, x12
	mov	x6, x2
LBB2_27:                                ;   Parent Loop BB2_26 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB2_28 Depth 3
                                        ;       Child Loop BB2_30 Depth 3
                                        ;       Child Loop BB2_32 Depth 3
	zero	{za}
	mov	x7, x1
	mov	x19, x6
	mov	w13, #512                       ; =0x200
LBB2_28:                                ;   Parent Loop BB2_26 Depth=1
                                        ;     Parent Loop BB2_27 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	z0, [x7]
	ld1w	{ z1.s }, p0/z, [x7, x8, lsl #2]
	ldr	z2, [x19]
	ld1w	{ z3.s }, p0/z, [x19, x8, lsl #2]
	fmopa	za0.s, p0/m, p0/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p0/m, z0.s, z3.s
	fmopa	za2.s, p0/m, p0/m, z1.s, z2.s
	fmopa	za3.s, p0/m, p0/m, z1.s, z3.s
	add	x19, x19, #2048
	add	x7, x7, #2048
	subs	x13, x13, #1
	b.ne	LBB2_28
; %bb.29:                               ;   in Loop: Header=BB2_27 Depth=2
	mov	x7, x4
	mov	x19, x5
LBB2_30:                                ;   Parent Loop BB2_26 Depth=1
                                        ;     Parent Loop BB2_27 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0h.s[w13, 0]}, p0, [x7]
	st1w	{za1h.s[w13, 0]}, p0, [x19]
	add	x13, x13, #1
	add	x19, x19, #2048
	add	x7, x7, #2048
	cmp	x8, x13
	b.ne	LBB2_30
; %bb.31:                               ;   in Loop: Header=BB2_27 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x7, x17
	mov	x19, x0
LBB2_32:                                ;   Parent Loop BB2_26 Depth=1
                                        ;     Parent Loop BB2_27 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za2h.s[w13, 0]}, p0, [x7]
	st1w	{za3h.s[w13, 0]}, p0, [x19]
	add	x13, x13, #1
	add	x19, x19, #2048
	add	x7, x7, #2048
	cmp	x8, x13
	b.ne	LBB2_32
; %bb.33:                               ;   in Loop: Header=BB2_27 Depth=2
	add	x16, x16, x9
	add	x6, x6, x11
	add	x5, x5, x11
	add	x4, x4, x11
	add	x0, x0, x11
	add	x17, x17, x11
	cmp	x16, #512
	b.lo	LBB2_27
; %bb.34:                               ;   in Loop: Header=BB2_26 Depth=1
	add	x10, x10, x9
	add	x1, x1, x11
	add	x12, x12, x20
	add	x3, x3, x20
	add	x14, x14, x20
	add	x15, x15, x20
	cmp	x10, #512
	b.lo	LBB2_26
LBB2_35:
	smstop	za
	smstop	sm
	.cfi_def_cfa wsp, 176
	ldp	x29, x30, [sp, #160]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #144]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #128]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #112]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #96]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #80]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #64]               ; 16-byte Folded Reload
	ldp	d11, d10, [sp, #48]             ; 16-byte Folded Reload
	ldp	d13, d12, [sp, #32]             ; 16-byte Folded Reload
	ldp	d15, d14, [sp, #16]             ; 16-byte Folded Reload
	add	sp, sp, #176
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w25
	.cfi_restore w26
	.cfi_restore w27
	.cfi_restore w28
	.cfi_restore b8
	.cfi_restore b9
	.cfi_restore b10
	.cfi_restore b11
	.cfi_restore b12
	.cfi_restore b13
	.cfi_restore b14
	.cfi_restore b15
	ret
LBB2_36:
	ptrue	p0.s
LBB2_37:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB2_38 Depth 2
	zero	{za}
	mov	x8, x2
	mov	x9, x1
	mov	w10, #512                       ; =0x200
LBB2_38:                                ;   Parent Loop BB2_37 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldr	z0, [x9]
	ldr	z1, [x8]
	fmopa	za0.s, p0/m, p0/m, z0.s, z1.s
	fmopa	za1.s, p0/m, p0/m, z0.s, z1.s
	fmopa	za2.s, p0/m, p0/m, z0.s, z1.s
	fmopa	za3.s, p0/m, p0/m, z0.s, z1.s
	add	x9, x9, #2048
	add	x8, x8, #2048
	subs	x10, x10, #1
	b.ne	LBB2_38
	b	LBB2_37
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
