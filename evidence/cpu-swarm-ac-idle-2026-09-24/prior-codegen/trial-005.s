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
	add	x15, x21, x16, lsl #3
	umull	x16, w8, w16
	add	x16, x20, x16, lsl #3
LBB0_14:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_15 Depth 2
                                        ;       Child Loop BB0_16 Depth 3
                                        ;       Child Loop BB0_18 Depth 3
	mov	x17, #0                         ; =0x0
	mul	x0, x11, x8
	add	x0, x19, x0, lsl #2
	mov	x1, x16
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
	mov	x3, x10
	mov	x4, x1
	mov	x5, x15
LBB0_18:                                ;   Parent Loop BB0_14 Depth=1
                                        ;     Parent Loop BB0_15 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	s1, [x5], #4
	ldr	s2, [x4]
	fmadd	s0, s2, s1, s0
	add	x4, x4, x13
	subs	x3, x3, #1
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
	add	x15, x15, x13
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
	rdsvl	x12, #1
	lsr	x9, x12, #2
	mov	w10, w0
	sbfiz	x14, x9, #2, #32
	lsl	w15, w9, #1
	sxtw	x11, w15
	sbfx	x4, x12, #2, #32
	mul	x12, x11, x10
	lsl	x13, x12, #2
	sbfiz	x5, x15, #2, #32
	ubfiz	x15, x0, #2, #32
	add	x26, x1, x14
	mul	x12, x4, x10
	lsl	x17, x12, #2
	zero	{za}
	add	x24, x1, x17
	add	x22, x2, x17
	add	x23, x2, x14
	add	x6, x23, x17
	b	LBB1_4
LBB1_3:                                 ;   in Loop: Header=BB1_4 Depth=1
	add	x1, x2, x13
	ldp	x26, x2, [sp, #32]              ; 16-byte Folded Reload
	add	x26, x26, x13
	add	x2, x2, x5
	ldp	x22, x24, [sp, #16]             ; 16-byte Folded Reload
	add	x24, x24, x13
	ldr	x23, [sp, #8]                   ; 8-byte Folded Reload
	add	x23, x23, x5
	add	x22, x22, x5
	add	x6, x6, x5
	add	x8, x8, x11
	cmp	x8, x10
	b.ge	LBB1_29
LBB1_4:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB1_6 Depth 2
                                        ;       Child Loop BB1_11 Depth 3
                                        ;       Child Loop BB1_9 Depth 3
                                        ;       Child Loop BB1_18 Depth 3
                                        ;       Child Loop BB1_20 Depth 3
                                        ;       Child Loop BB1_15 Depth 3
                                        ;       Child Loop BB1_23 Depth 3
                                        ;       Child Loop BB1_27 Depth 3
	mov	x7, #0                          ; =0x0
	sub	w12, w10, w8
	cmp	w12, w9
	csel	w14, w12, w9, lt
	sub	w12, w12, w9
	cmp	w12, w9
	csel	w12, w12, w9, lt
	whilelt	p0.s, w8, w0
	add	w16, w8, w4
	whilelt	p1.s, w16, w0
	sxtw	x19, w14
	sxtw	x20, w12
	mov	x21, x6
	stp	x23, x22, [sp, #8]              ; 16-byte Folded Spill
	stp	x24, x26, [sp, #24]             ; 16-byte Folded Spill
	str	x2, [sp, #40]                   ; 8-byte Folded Spill
	mov	x25, x2
	mov	x2, x1
	mov	x27, x1
	b	LBB1_6
LBB1_5:                                 ;   in Loop: Header=BB1_6 Depth=2
	add	x27, x27, x5
	add	x26, x26, x5
	add	x25, x25, x13
	add	x24, x24, x5
	add	x23, x23, x13
	add	x22, x22, x13
	add	x21, x21, x13
	add	x7, x7, x11
	cmp	x7, x10
	b.ge	LBB1_3
LBB1_6:                                 ;   Parent Loop BB1_4 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB1_11 Depth 3
                                        ;       Child Loop BB1_9 Depth 3
                                        ;       Child Loop BB1_18 Depth 3
                                        ;       Child Loop BB1_20 Depth 3
                                        ;       Child Loop BB1_15 Depth 3
                                        ;       Child Loop BB1_23 Depth 3
                                        ;       Child Loop BB1_27 Depth 3
	sub	x12, x10, x7
	cmp	w12, w9
	csel	w30, w12, w9, lt
	sub	x16, x12, x4
	cmp	w16, w9
	csel	w28, w16, w9, lt
	whilelt	p2.s, w7, w0
	add	w12, w7, w4
	whilelt	p3.s, w12, w0
	cmp	w19, #1
	b.lt	LBB1_12
; %bb.7:                                ;   in Loop: Header=BB1_6 Depth=2
	cmp	x16, #0
	b.le	LBB1_10
; %bb.8:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x14, #0                         ; =0x0
LBB1_9:                                 ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x3, x27, x12
	ld1w	{za0h.s[w14, 0]}, p2/z, [x3]
	add	x3, x26, x12
	ld1w	{za1h.s[w14, 0]}, p3/z, [x3]
	add	x14, x14, #1
	add	x12, x12, x15
	cmp	x14, x19
	b.lt	LBB1_9
	b	LBB1_12
LBB1_10:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x14, x27
LBB1_11:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za0h.s[w12, 0]}, p2/z, [x14]
	add	x12, x12, #1
	add	x14, x14, x15
	cmp	x12, x19
	b.lt	LBB1_11
LBB1_12:                                ;   in Loop: Header=BB1_6 Depth=2
	cmp	w20, #1
	b.lt	LBB1_16
; %bb.13:                               ;   in Loop: Header=BB1_6 Depth=2
	cmp	x16, #0
	b.le	LBB1_19
; %bb.14:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x16, x17
LBB1_15:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x14, x27, x16
	ld1w	{za2h.s[w12, 0]}, p2/z, [x14]
	add	x14, x26, x16
	ld1w	{za3h.s[w12, 0]}, p3/z, [x14]
	add	x12, x12, #1
	add	x16, x16, x15
	cmp	x12, x20
	b.lt	LBB1_15
	b	LBB1_21
LBB1_16:                                ;   in Loop: Header=BB1_6 Depth=2
	cmp	w30, #1
	b.lt	LBB1_24
; %bb.17:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x14, x25
LBB1_18:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za0v.s[w12, 0]}, p0, [x14]
	add	x12, x12, #1
	add	x14, x14, x15
	cmp	x12, x30
	b.lo	LBB1_18
	b	LBB1_24
LBB1_19:                                ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x14, x24
LBB1_20:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ld1w	{za2h.s[w12, 0]}, p2/z, [x14]
	add	x12, x12, #1
	add	x14, x14, x15
	cmp	x12, x20
	b.lt	LBB1_20
LBB1_21:                                ;   in Loop: Header=BB1_6 Depth=2
	cmp	w30, #0
	b.le	LBB1_24
; %bb.22:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x14, #0                         ; =0x0
LBB1_23:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x16, x25, x12
	st1w	{za0v.s[w14, 0]}, p0, [x16]
	add	x16, x23, x12
	st1w	{za2v.s[w14, 0]}, p1, [x16]
	add	x14, x14, #1
	add	x12, x12, x15
	cmp	x14, x30
	b.lo	LBB1_23
LBB1_24:                                ;   in Loop: Header=BB1_6 Depth=2
	cmp	w28, #1
	b.lt	LBB1_5
; %bb.25:                               ;   in Loop: Header=BB1_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x16, x21
	mov	x30, x22
	b	LBB1_27
LBB1_26:                                ;   in Loop: Header=BB1_27 Depth=3
	add	x12, x12, #1
	add	x30, x30, x15
	add	x16, x16, x15
	cmp	x12, x28
	b.hs	LBB1_5
LBB1_27:                                ;   Parent Loop BB1_4 Depth=1
                                        ;     Parent Loop BB1_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	st1w	{za1v.s[w12, 0]}, p0, [x30]
	cmp	w20, #1
	b.lt	LBB1_26
; %bb.28:                               ;   in Loop: Header=BB1_27 Depth=3
	st1w	{za3v.s[w12, 0]}, p1, [x16]
	b	LBB1_26
LBB1_29:
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
	sub	sp, sp, #240
	.cfi_def_cfa_offset 240
	stp	d15, d14, [sp, #80]             ; 16-byte Folded Spill
	stp	d13, d12, [sp, #96]             ; 16-byte Folded Spill
	stp	d11, d10, [sp, #112]            ; 16-byte Folded Spill
	stp	d9, d8, [sp, #128]              ; 16-byte Folded Spill
	stp	x28, x27, [sp, #144]            ; 16-byte Folded Spill
	stp	x26, x25, [sp, #160]            ; 16-byte Folded Spill
	stp	x24, x23, [sp, #176]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #192]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #208]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #224]            ; 16-byte Folded Spill
	add	x29, sp, #224
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
	mov	x6, x2
	str	x1, [sp, #72]                   ; 8-byte Folded Spill
                                        ; kill: def $w0 killed $w0 def $x0
	smstart	sm
	mrs	x8, TPIDR2_EL0
	cbz	x8, LBB2_2
; %bb.1:
	bl	___arm_tpidr2_save
	msr	TPIDR2_EL0, xzr
LBB2_2:
	smstart	za
	mov	x8, #0                          ; =0x0
	rdsvl	x12, #1
	lsr	x9, x12, #2
	sub	w10, w0, #1
	mov	w11, w0
	lsl	x13, x9, #32
	lsl	w16, w9, #1
	sxtw	x25, w16
	sbfx	x21, x12, #2, #32
	ubfx	x14, x12, #2, #31
	ubfiz	x15, x0, #3, #32
	sbfiz	x16, x16, #2, #32
	ubfiz	x17, x0, #2, #32
	add	x12, x6, x17
	str	x12, [sp, #64]                  ; 8-byte Folded Spill
	ldr	x23, [sp, #72]                  ; 8-byte Folded Reload
	add	x22, x23, x17
	mul	x12, x25, x11
	lsl	x12, x12, #2
	stp	x12, x22, [sp, #8]              ; 16-byte Folded Spill
	add	x30, x3, x13, asr #30
	mul	x12, x21, x11
	lsl	x12, x12, #2
	zero	{za}
	str	x12, [sp, #56]                  ; 8-byte Folded Spill
	add	x28, x3, x12
	str	x21, [sp, #24]                  ; 8-byte Folded Spill
	b	LBB2_4
LBB2_3:                                 ;   in Loop: Header=BB2_4 Depth=1
	add	x23, x23, x16
	add	x22, x22, x16
	ldp	x30, x3, [sp, #40]              ; 16-byte Folded Reload
	ldr	x12, [sp, #8]                   ; 8-byte Folded Reload
	add	x3, x3, x12
	add	x30, x30, x12
	ldr	x28, [sp, #32]                  ; 8-byte Folded Reload
	add	x28, x28, x12
	add	x21, x21, x25
	add	x8, x8, x25
	cmp	x8, x11
	b.ge	LBB2_27
LBB2_4:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB2_6 Depth 2
                                        ;       Child Loop BB2_8 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
                                        ;       Child Loop BB2_15 Depth 3
                                        ;       Child Loop BB2_25 Depth 3
                                        ;       Child Loop BB2_22 Depth 3
	mov	x24, #0                         ; =0x0
	whilelt	p0.s, w8, w0
	ldr	x12, [sp, #24]                  ; 8-byte Folded Reload
	add	x12, x8, x12
	whilelt	p1.s, w12, w0
	cmp	x12, x11
	csel	w12, w9, wzr, lt
	add	w12, w8, w12
	sxtw	x1, w12
	sbfiz	x12, x12, #2, #32
	ldp	x4, x13, [sp, #64]              ; 16-byte Folded Reload
	add	x26, x13, x12
	ldr	x13, [sp, #16]                  ; 8-byte Folded Reload
	add	x27, x13, x12
	stp	x28, x30, [sp, #32]             ; 16-byte Folded Spill
	str	x3, [sp, #48]                   ; 8-byte Folded Spill
	mov	x2, x6
	b	LBB2_6
LBB2_5:                                 ;   in Loop: Header=BB2_6 Depth=2
	add	x2, x2, x16
	add	x4, x4, x16
	add	x3, x3, x16
	add	x30, x30, x16
	add	x28, x28, x16
	add	x24, x24, x25
	cmp	x24, x11
	b.ge	LBB2_3
LBB2_6:                                 ;   Parent Loop BB2_4 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB2_8 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
                                        ;       Child Loop BB2_15 Depth 3
                                        ;       Child Loop BB2_25 Depth 3
                                        ;       Child Loop BB2_22 Depth 3
	whilelt	p2.s, w24, w0
	add	x5, x24, x9
	whilelt	p3.s, w5, w0
	zero	{za}
	cmp	w0, #2
	b.lo	LBB2_11
; %bb.7:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	x20, #0                         ; =0x0
	mov	x7, #0                          ; =0x0
	cmp	w0, w5
	csel	x12, x5, x24, gt
	sxtw	x12, w12
	lsl	x12, x12, #2
	add	x19, x6, x12
	ldr	x13, [sp, #64]                  ; 8-byte Folded Reload
	add	x13, x13, x12
LBB2_8:                                 ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x12, x23, x20
	ld1w	{ z0.s }, p0/z, [x12]
	add	x12, x26, x20
	ld1w	{ z1.s }, p1/z, [x12]
	add	x12, x2, x20
	ld1w	{ z2.s }, p2/z, [x12]
	add	x12, x19, x20
	ld1w	{ z3.s }, p3/z, [x12]
	fmopa	za0.s, p0/m, p2/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p3/m, z0.s, z3.s
	fmopa	za2.s, p1/m, p2/m, z1.s, z2.s
	fmopa	za3.s, p1/m, p3/m, z1.s, z3.s
	add	x12, x22, x20
	ld1w	{ z0.s }, p0/z, [x12]
	add	x12, x27, x20
	ld1w	{ z1.s }, p1/z, [x12]
	add	x12, x4, x20
	ld1w	{ z2.s }, p2/z, [x12]
	add	x12, x13, x20
	ld1w	{ z3.s }, p3/z, [x12]
	fmopa	za0.s, p0/m, p2/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p3/m, z0.s, z3.s
	fmopa	za2.s, p1/m, p2/m, z1.s, z2.s
	fmopa	za3.s, p1/m, p3/m, z1.s, z3.s
	add	x7, x7, #2
	add	x20, x20, x15
	cmp	x7, x10
	b.lo	LBB2_8
; %bb.9:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w0, w7
	b.hi	LBB2_12
; %bb.10:                               ;   in Loop: Header=BB2_6 Depth=2
	cmp	w9, #1
	b.ge	LBB2_13
	b	LBB2_5
LBB2_11:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	x7, #0                          ; =0x0
LBB2_12:                                ;   in Loop: Header=BB2_6 Depth=2
	umull	x12, w7, w11
	lsl	x12, x12, #2
	ldr	x13, [sp, #72]                  ; 8-byte Folded Reload
	add	x13, x13, x12
	ld1w	{ z0.s }, p0/z, [x13, x8, lsl #2]
	ld1w	{ z1.s }, p1/z, [x13, x1, lsl #2]
	add	x12, x6, x12
	ld1w	{ z2.s }, p2/z, [x12, x24, lsl #2]
	cmp	w0, w5
	csel	x13, x5, x24, gt
	lsl	x13, x13, #32
	add	x12, x12, x13, asr #30
	ld1w	{ z3.s }, p3/z, [x12]
	fmopa	za0.s, p0/m, p2/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p3/m, z0.s, z3.s
	fmopa	za2.s, p1/m, p2/m, z1.s, z2.s
	fmopa	za3.s, p1/m, p3/m, z1.s, z3.s
	cmp	w9, #1
	b.lt	LBB2_5
LBB2_13:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w0, w5
	b.le	LBB2_17
; %bb.14:                               ;   in Loop: Header=BB2_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x12, #0                         ; =0x0
LBB2_15:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x7, x8, x12
	cmp	x7, x11
	b.ge	LBB2_20
; %bb.16:                               ;   in Loop: Header=BB2_15 Depth=3
	add	x7, x3, x13
	st1w	{za0h.s[w12, 0]}, p2, [x7]
	add	x7, x30, x13
	st1w	{za1h.s[w12, 0]}, p3, [x7]
	add	x12, x12, #1
	add	x13, x13, x17
	cmp	x14, x12
	b.ne	LBB2_15
	b	LBB2_20
LBB2_17:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	x13, #0                         ; =0x0
	mov	x12, x3
LBB2_18:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x7, x8, x13
	cmp	x7, x11
	b.ge	LBB2_20
; %bb.19:                               ;   in Loop: Header=BB2_18 Depth=3
	st1w	{za0h.s[w13, 0]}, p2, [x12]
	add	x13, x13, #1
	add	x12, x12, x17
	cmp	x14, x13
	b.ne	LBB2_18
LBB2_20:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w0, w5
	b.le	LBB2_24
; %bb.21:                               ;   in Loop: Header=BB2_6 Depth=2
	mov	x13, #0                         ; =0x0
	ldr	x5, [sp, #56]                   ; 8-byte Folded Reload
LBB2_22:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x12, x21, x13
	cmp	x12, x11
	b.ge	LBB2_5
; %bb.23:                               ;   in Loop: Header=BB2_22 Depth=3
	add	x12, x3, x5
	st1w	{za2h.s[w13, 0]}, p2, [x12]
	add	x12, x30, x5
	st1w	{za3h.s[w13, 0]}, p3, [x12]
	add	x13, x13, #1
	add	x5, x5, x17
	cmp	x14, x13
	b.ne	LBB2_22
	b	LBB2_5
LBB2_24:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	w13, #0                         ; =0x0
	mov	x5, x14
	mov	x7, x21
	mov	x19, x28
LBB2_25:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	cmp	x7, x11
	b.ge	LBB2_5
; %bb.26:                               ;   in Loop: Header=BB2_25 Depth=3
	st1w	{za2h.s[w13, 0]}, p2, [x19]
	add	w13, w13, #1
	add	x19, x19, x17
	add	x7, x7, #1
	subs	x5, x5, #1
	b.ne	LBB2_25
	b	LBB2_5
LBB2_27:
	smstop	za
	smstop	sm
	.cfi_def_cfa wsp, 240
	ldp	x29, x30, [sp, #224]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #208]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #192]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #176]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #160]            ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #144]            ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #128]              ; 16-byte Folded Reload
	ldp	d11, d10, [sp, #112]            ; 16-byte Folded Reload
	ldp	d13, d12, [sp, #96]             ; 16-byte Folded Reload
	ldp	d15, d14, [sp, #80]             ; 16-byte Folded Reload
	add	sp, sp, #240
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
.subsections_via_symbols
