	.build_version macos, 26, 0	sdk_version 26, 5
                                        ; Start of file scope inline assembly
	.section	__TEXT,__text,regular,pure_instructions
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_512:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x7, #512                        ; =0x200
Llibxsmm_64:
	mov	x20, sp
	sub	sp, sp, #32, lsl #12            ; =131072
	mov	x3, sp
	mov	x26, sp
	mov	x11, #32                        ; =0x20
Llibxsmm_78:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #2048
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #2048
	mov	za2h.s[w14, 0:3], { z0.s - z3.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z4.s - z7.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z8.s - z11.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z12.s - z15.s }
	add	w14, w14, #4
	mov	za3h.s[w15, 0:3], { z16.s - z19.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z20.s - z23.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z24.s - z27.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z28.s - z31.s }
	add	w15, w15, #4
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	sub	x1, x1, #32, lsl #12            ; =131072
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	x9, #256                        ; =0x100
	whilelt	pn8.b, xzr, x9, vlx4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	add	x1, x1, #64
	sub	x11, x11, #1
	cbnz	x11, Llibxsmm_78
	sub	x1, x1, #2048
	mov	sp, x20
	mov	x6, #512                        ; =0x200
Llibxsmm_440:
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #2048                       ; =0x800
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Llibxsmm_478:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x0, x0, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Llibxsmm_478
	sub	x0, x0, #256, lsl #12           ; =1048576
	sub	x3, x3, #32, lsl #12            ; =131072
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	add	x2, x2, #16, lsl #12            ; =65536
	add	x3, x3, #128
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #2048                       ; =0x800
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Llibxsmm_70c:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x0, x0, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Llibxsmm_70c
	sub	x0, x0, #256, lsl #12           ; =1048576
	sub	x3, x3, #32, lsl #12            ; =131072
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	sub	x2, x2, #3968
	sub	x2, x2, #15, lsl #12            ; =61440
	add	x3, x26, #0
	add	x0, x0, #128
	sub	x6, x6, #32
	cbnz	x6, Llibxsmm_440
	sub	x0, x0, #2048
	add	x1, x1, #32, lsl #12            ; =131072
	add	x2, x2, #2048
	add	x2, x2, #31, lsl #12            ; =126976
	sub	x7, x7, #64
	cbnz	x7, Llibxsmm_64
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_panel32:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x20, sp
	sub	sp, sp, #16, lsl #12            ; =65536
	mov	x3, sp
	mov	x11, #32                        ; =0x20
Lpanel32_70:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	x9, #64                         ; =0x40
	whilelt	p0.b, xzr, x9
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #2048
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	sub	x1, x1, #16, lsl #12            ; =65536
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z12.s - z15.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	ptrue	p0.b
	mov	x9, #64                         ; =0x40
	whilelt	p1.b, xzr, x9
	st1w	{ z0.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z16.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z1.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z17.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z2.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z18.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z3.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z19.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z4.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z20.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z5.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z21.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z6.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z22.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z7.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z23.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z8.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z24.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z9.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z25.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z10.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z26.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z11.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z27.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z12.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z28.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z13.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z29.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z14.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z30.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z15.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z31.s }, p1, [sp]
	add	sp, sp, #64
	add	x1, x1, #64
	sub	x11, x11, #1
	cbnz	x11, Lpanel32_70
	sub	x1, x1, #2048
	mov	sp, x20
	mov	x6, #512                        ; =0x200
Lpanel32_330:
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #2048                       ; =0x800
	mov	x10, #128                       ; =0x80
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Lpanel32_368:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x0, x0, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Lpanel32_368
	sub	x0, x0, #256, lsl #12           ; =1048576
	sub	x3, x3, #16, lsl #12            ; =65536
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	add	x2, x2, #128
	add	x0, x0, #128
	sub	x6, x6, #32
	cbnz	x6, Lpanel32_330
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_ta:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x7, #512                        ; =0x200
Lta_64:
	mov	x20, sp
	sub	sp, sp, #32, lsl #12            ; =131072
	mov	x3, sp
	mov	x26, sp
	mov	x11, #32                        ; =0x20
Lta_78:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #2048
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #2048
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #2048
	mov	za2h.s[w14, 0:3], { z0.s - z3.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z4.s - z7.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z8.s - z11.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z12.s - z15.s }
	add	w14, w14, #4
	mov	za3h.s[w15, 0:3], { z16.s - z19.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z20.s - z23.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z24.s - z27.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z28.s - z31.s }
	add	w15, w15, #4
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	sub	x1, x1, #32, lsl #12            ; =131072
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	x9, #256                        ; =0x100
	whilelt	pn8.b, xzr, x9, vlx4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	add	x1, x1, #64
	sub	x11, x11, #1
	cbnz	x11, Lta_78
	sub	x1, x1, #2048
	mov	sp, x20
	mov	x6, #512                        ; =0x200
Lta_440:
	mov	x28, sp
	sub	sp, sp, #48, lsl #12            ; =196608
	mov	x27, sp
	mov	x11, #32                        ; =0x20
Lta_450:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	x9, #64                         ; =0x40
	whilelt	p0.b, xzr, x9
	ld1w	{ z0.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z1.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z2.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z3.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z4.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z5.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z6.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z7.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z8.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z9.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z10.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z11.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z12.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z13.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z14.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z15.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z16.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z17.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z18.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z19.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z20.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z21.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z22.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z23.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z24.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z25.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z26.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z27.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z28.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z29.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z30.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z31.s }, p0/z, [x0]
	add	x0, x0, #2048
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	sub	x0, x0, #16, lsl #12            ; =65536
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z12.s - z15.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	ptrue	p0.b
	mov	x9, #64                         ; =0x40
	whilelt	p1.b, xzr, x9
	st1w	{ z0.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z16.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z1.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z17.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z2.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z18.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z3.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z19.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z4.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z20.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z5.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z21.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z6.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z22.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z7.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z23.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z8.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z24.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z9.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z25.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z10.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z26.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z11.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z27.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z12.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z28.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z13.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z29.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z14.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z30.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z15.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z31.s }, p1, [sp]
	add	sp, sp, #64
	add	x0, x0, #64
	sub	x11, x11, #1
	cbnz	x11, Lta_450
	sub	x0, x0, #2048
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #128                        ; =0x80
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Lta_740:
	ld1w	{ z0.s, z1.s }, pn8/z, [x27]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x27, x27, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Lta_740
	sub	x27, x27, #16, lsl #12          ; =65536
	sub	x3, x3, #32, lsl #12            ; =131072
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	add	x2, x2, #16, lsl #12            ; =65536
	add	x3, x3, #128
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #128                        ; =0x80
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Lta_9d4:
	ld1w	{ z0.s, z1.s }, pn8/z, [x27]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x27, x27, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Lta_9d4
	sub	x27, x27, #16, lsl #12          ; =65536
	sub	x3, x3, #32, lsl #12            ; =131072
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	sub	x2, x2, #3968
	sub	x2, x2, #15, lsl #12            ; =61440
	add	x3, x26, #0
	add	x0, x0, #16, lsl #12            ; =65536
	mov	sp, x28
	sub	x6, x6, #32
	cbnz	x6, Lta_440
	sub	x0, x0, #256, lsl #12           ; =1048576
	add	x1, x1, #32, lsl #12            ; =131072
	add	x2, x2, #2048
	add	x2, x2, #31, lsl #12            ; =126976
	sub	x7, x7, #64
	cbnz	x7, Lta_64
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_tb:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x7, #512                        ; =0x200
Ltb_64:
	add	x26, x1, #0
	mov	x6, #512                        ; =0x200
Ltb_6c:
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #2048                       ; =0x800
	mov	x10, #2048                      ; =0x800
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Ltb_a4:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x1]
	add	x0, x0, x9
	add	x1, x1, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Ltb_a4
	sub	x0, x0, #256, lsl #12           ; =1048576
	sub	x1, x1, #256, lsl #12           ; =1048576
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	add	x2, x2, #16, lsl #12            ; =65536
	add	x1, x1, #128
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #2048                       ; =0x800
	mov	x10, #2048                      ; =0x800
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Ltb_338:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x1]
	add	x0, x0, x9
	add	x1, x1, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Ltb_338
	sub	x0, x0, #256, lsl #12           ; =1048576
	sub	x1, x1, #256, lsl #12           ; =1048576
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	sub	x2, x2, #3968
	sub	x2, x2, #15, lsl #12            ; =61440
	add	x1, x26, #0
	add	x0, x0, #128
	sub	x6, x6, #32
	cbnz	x6, Ltb_6c
	sub	x0, x0, #2048
	add	x1, x1, #256
	add	x2, x2, #2048
	add	x2, x2, #31, lsl #12            ; =126976
	sub	x7, x7, #64
	cbnz	x7, Ltb_64
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_tt:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x7, #512                        ; =0x200
Ltt_64:
	add	x26, x1, #0
	mov	x6, #512                        ; =0x200
Ltt_6c:
	mov	x28, sp
	sub	sp, sp, #16, lsl #12            ; =65536
	mov	x27, sp
	mov	x11, #32                        ; =0x20
Ltt_7c:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	x9, #64                         ; =0x40
	whilelt	p0.b, xzr, x9
	ld1w	{ z0.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z1.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z2.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z3.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z4.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z5.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z6.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z7.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z8.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z9.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z10.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z11.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z12.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z13.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z14.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z15.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z16.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z17.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z18.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z19.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z20.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z21.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z22.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z23.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z24.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z25.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z26.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z27.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z28.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z29.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z30.s }, p0/z, [x0]
	add	x0, x0, #2048
	ld1w	{ z31.s }, p0/z, [x0]
	add	x0, x0, #2048
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	sub	x0, x0, #16, lsl #12            ; =65536
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z12.s - z15.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	ptrue	p0.b
	mov	x9, #64                         ; =0x40
	whilelt	p1.b, xzr, x9
	st1w	{ z0.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z16.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z1.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z17.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z2.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z18.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z3.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z19.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z4.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z20.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z5.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z21.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z6.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z22.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z7.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z23.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z8.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z24.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z9.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z25.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z10.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z26.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z11.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z27.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z12.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z28.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z13.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z29.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z14.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z30.s }, p1, [sp]
	add	sp, sp, #64
	st1w	{ z15.s }, p0, [sp]
	add	sp, sp, #64
	st1w	{ z31.s }, p1, [sp]
	add	sp, sp, #64
	add	x0, x0, #64
	sub	x11, x11, #1
	cbnz	x11, Ltt_7c
	sub	x0, x0, #2048
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #128                        ; =0x80
	mov	x10, #2048                      ; =0x800
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Ltt_36c:
	ld1w	{ z0.s, z1.s }, pn8/z, [x27]
	ld1w	{ z2.s, z3.s }, pn9/z, [x1]
	add	x27, x27, x9
	add	x1, x1, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Ltt_36c
	sub	x27, x27, #16, lsl #12          ; =65536
	sub	x1, x1, #256, lsl #12           ; =1048576
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	add	x2, x2, #16, lsl #12            ; =65536
	add	x1, x1, #128
	mov	x17, x2
	add	x9, x2, #8, lsl #12             ; =32768
	zero	{za}
	mov	x9, #128                        ; =0x80
	mov	x10, #2048                      ; =0x800
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #512                        ; =0x200
Ltt_600:
	ld1w	{ z0.s, z1.s }, pn8/z, [x27]
	ld1w	{ z2.s, z3.s }, pn9/z, [x1]
	add	x27, x27, x9
	add	x1, x1, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Ltt_600
	sub	x27, x27, #16, lsl #12          ; =65536
	sub	x1, x1, #256, lsl #12           ; =1048576
	mov	x2, x17
	add	x9, x2, #8, lsl #12             ; =32768
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #2048
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #2048
	mov	x2, x17
	sub	x2, x2, #3968
	sub	x2, x2, #15, lsl #12            ; =61440
	add	x1, x26, #0
	add	x0, x0, #16, lsl #12            ; =65536
	mov	sp, x28
	sub	x6, x6, #32
	cbnz	x6, Ltt_6c
	sub	x0, x0, #256, lsl #12           ; =1048576
	add	x1, x1, #256
	add	x2, x2, #2048
	add	x2, x2, #31, lsl #12            ; =126976
	sub	x7, x7, #64
	cbnz	x7, Ltt_64
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret
	.arch	armv9-a+sme2
	.p2align	12
_sera_libxsmm_256:
	sub	sp, sp, #192
	stp	d8, d9, [sp, #176]
	stp	d10, d11, [sp, #160]
	stp	d12, d13, [sp, #144]
	stp	d14, d15, [sp, #128]
	stp	x20, x21, [sp, #80]
	stp	x22, x23, [sp, #64]
	stp	x26, x27, [sp, #32]
	stp	x28, x29, [sp, #16]
	str	x30, [sp]
	and	x10, x0, x0
	ldr	x0, [x10, #32]
	ldr	x1, [x10, #80]
	ldr	x2, [x10, #128]
	mov	x29, sp
	sub	sp, sp, #192
	mov	x10, #65472                     ; =0xffc0
	movk	x10, #65535, lsl #16
	movk	x10, #65535, lsl #32
	movk	x10, #65535, lsl #48
	mov	x9, sp
	and	x9, x9, x10
	mov	sp, x9
	smstart
	mov	x7, #256                        ; =0x100
Lgemm256_64:
	mov	x20, sp
	sub	sp, sp, #16, lsl #12            ; =65536
	mov	x3, sp
	mov	x26, sp
	mov	x11, #16                        ; =0x10
Lgemm256_78:
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #1024
	mov	za0h.s[w12, 0:3], { z0.s - z3.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z4.s - z7.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z8.s - z11.s }
	add	w12, w12, #4
	mov	za0h.s[w12, 0:3], { z12.s - z15.s }
	add	w12, w12, #4
	mov	za1h.s[w13, 0:3], { z16.s - z19.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z20.s - z23.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z24.s - z27.s }
	add	w13, w13, #4
	mov	za1h.s[w13, 0:3], { z28.s - z31.s }
	add	w13, w13, #4
	ld1w	{ z0.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z1.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z2.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z3.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z4.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z5.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z6.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z7.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z8.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z9.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z10.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z11.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z12.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z13.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z14.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z15.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z16.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z17.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z18.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z19.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z20.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z21.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z22.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z23.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z24.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z25.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z26.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z27.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z28.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z29.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z30.s }, p0/z, [x1]
	add	x1, x1, #1024
	ld1w	{ z31.s }, p0/z, [x1]
	add	x1, x1, #1024
	mov	za2h.s[w14, 0:3], { z0.s - z3.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z4.s - z7.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z8.s - z11.s }
	add	w14, w14, #4
	mov	za2h.s[w14, 0:3], { z12.s - z15.s }
	add	w14, w14, #4
	mov	za3h.s[w15, 0:3], { z16.s - z19.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z20.s - z23.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z24.s - z27.s }
	add	w15, w15, #4
	mov	za3h.s[w15, 0:3], { z28.s - z31.s }
	add	w15, w15, #4
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	sub	x1, x1, #16, lsl #12            ; =65536
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	x9, #256                        ; =0x100
	whilelt	pn8.b, xzr, x9, vlx4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	mov	{ z0.s - z3.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z8.s - z11.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z12.s - z15.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z16.s - z19.s }, za0v.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za1v.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za2v.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z28.s - z31.s }, za3v.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s, z4.s, z8.s, z12.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z1.s, z5.s, z9.s, z13.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z2.s, z6.s, z10.s, z14.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z3.s, z7.s, z11.s, z15.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z16.s, z20.s, z24.s, z28.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z17.s, z21.s, z25.s, z29.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z18.s, z22.s, z26.s, z30.s }, pn8, [sp]
	add	sp, sp, #256
	st1w	{ z19.s, z23.s, z27.s, z31.s }, pn8, [sp]
	add	sp, sp, #256
	add	x1, x1, #64
	sub	x11, x11, #1
	cbnz	x11, Lgemm256_78
	sub	x1, x1, #1024
	mov	sp, x20
	mov	x6, #256                        ; =0x100
Lgemm256_440:
	mov	x17, x2
	add	x9, x2, #4, lsl #12             ; =16384
	zero	{za}
	mov	x9, #1024                       ; =0x400
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #256                        ; =0x100
Lgemm256_478:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x0, x0, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Lgemm256_478
	sub	x0, x0, #64, lsl #12            ; =262144
	sub	x3, x3, #16, lsl #12            ; =65536
	mov	x2, x17
	add	x9, x2, #4, lsl #12             ; =16384
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	mov	x2, x17
	add	x2, x2, #8, lsl #12             ; =32768
	add	x3, x3, #128
	mov	x17, x2
	add	x9, x2, #4, lsl #12             ; =16384
	zero	{za}
	mov	x9, #1024                       ; =0x400
	mov	x10, #256                       ; =0x100
	mov	x11, #128                       ; =0x80
	whilelt	pn8.b, xzr, x11, vlx2
	mov	x11, #128                       ; =0x80
	whilelt	pn9.b, xzr, x11, vlx2
	ptrue	p0.b
	ptrue	p2.b
	ptrue	p1.b
	ptrue	p3.b
	mov	x8, #256                        ; =0x100
Lgemm256_70c:
	ld1w	{ z0.s, z1.s }, pn8/z, [x0]
	ld1w	{ z2.s, z3.s }, pn9/z, [x3]
	add	x0, x0, x9
	add	x3, x3, x10
	fmopa	za0.s, p1/m, p0/m, z2.s, z0.s
	fmopa	za1.s, p1/m, p2/m, z2.s, z1.s
	fmopa	za2.s, p3/m, p0/m, z3.s, z0.s
	fmopa	za3.s, p3/m, p2/m, z3.s, z1.s
	sub	x8, x8, #1
	cbnz	x8, Lgemm256_70c
	sub	x0, x0, #64, lsl #12            ; =262144
	sub	x3, x3, #16, lsl #12            ; =65536
	mov	x2, x17
	add	x9, x2, #4, lsl #12             ; =16384
	mov	w12, #0                         ; =0x0
	mov	w13, #1                         ; =0x1
	mov	w14, #2                         ; =0x2
	mov	w15, #3                         ; =0x3
	ptrue	p0.b
	ptrue	p2.b
	mov	{ z0.s - z3.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z4.s - z7.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z16.s - z19.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z20.s - z23.s }, za0h.s[w12, 0:3]
	add	w12, w12, #4
	mov	{ z8.s - z11.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z12.s - z15.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z24.s - z27.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	mov	{ z28.s - z31.s }, za1h.s[w13, 0:3]
	add	w13, w13, #4
	st1w	{ z0.s }, p0, [x2]
	st1w	{ z8.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z1.s }, p0, [x2]
	st1w	{ z9.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z2.s }, p0, [x2]
	st1w	{ z10.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z3.s }, p0, [x2]
	st1w	{ z11.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z4.s }, p0, [x2]
	st1w	{ z12.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z5.s }, p0, [x2]
	st1w	{ z13.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z6.s }, p0, [x2]
	st1w	{ z14.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z7.s }, p0, [x2]
	st1w	{ z15.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z16.s }, p0, [x2]
	st1w	{ z24.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z17.s }, p0, [x2]
	st1w	{ z25.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z18.s }, p0, [x2]
	st1w	{ z26.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z19.s }, p0, [x2]
	st1w	{ z27.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z20.s }, p0, [x2]
	st1w	{ z28.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z21.s }, p0, [x2]
	st1w	{ z29.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z22.s }, p0, [x2]
	st1w	{ z30.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	st1w	{ z23.s }, p0, [x2]
	st1w	{ z31.s }, p2, [x2, #1, mul vl]
	add	x2, x2, #1024
	mov	{ z0.s - z3.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z4.s - z7.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z16.s - z19.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z20.s - z23.s }, za2h.s[w14, 0:3]
	add	w14, w14, #4
	mov	{ z8.s - z11.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z12.s - z15.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z24.s - z27.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	mov	{ z28.s - z31.s }, za3h.s[w15, 0:3]
	add	w15, w15, #4
	st1w	{ z0.s }, p0, [x9]
	st1w	{ z8.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z1.s }, p0, [x9]
	st1w	{ z9.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z2.s }, p0, [x9]
	st1w	{ z10.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z3.s }, p0, [x9]
	st1w	{ z11.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z4.s }, p0, [x9]
	st1w	{ z12.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z5.s }, p0, [x9]
	st1w	{ z13.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z6.s }, p0, [x9]
	st1w	{ z14.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z7.s }, p0, [x9]
	st1w	{ z15.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z16.s }, p0, [x9]
	st1w	{ z24.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z17.s }, p0, [x9]
	st1w	{ z25.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z18.s }, p0, [x9]
	st1w	{ z26.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z19.s }, p0, [x9]
	st1w	{ z27.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z20.s }, p0, [x9]
	st1w	{ z28.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z21.s }, p0, [x9]
	st1w	{ z29.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z22.s }, p0, [x9]
	st1w	{ z30.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	st1w	{ z23.s }, p0, [x9]
	st1w	{ z31.s }, p2, [x9, #1, mul vl]
	add	x9, x9, #1024
	mov	x2, x17
	sub	x2, x2, #3968
	sub	x2, x2, #7, lsl #12             ; =28672
	add	x3, x26, #0
	add	x0, x0, #128
	sub	x6, x6, #32
	cbnz	x6, Lgemm256_440
	sub	x0, x0, #1024
	add	x1, x1, #16, lsl #12            ; =65536
	add	x2, x2, #3072
	add	x2, x2, #15, lsl #12            ; =61440
	sub	x7, x7, #64
	cbnz	x7, Lgemm256_64
	smstop
	mov	sp, x29
	ldp	d8, d9, [sp, #176]
	ldp	d10, d11, [sp, #160]
	ldp	d12, d13, [sp, #144]
	ldp	d14, d15, [sp, #128]
	ldp	x20, x21, [sp, #80]
	ldp	x22, x23, [sp, #64]
	ldp	x26, x27, [sp, #32]
	ldp	x28, x29, [sp, #16]
	ldr	x30, [sp]
	add	sp, sp, #192
	ret

                                        ; End of file scope inline assembly
	.globl	_gemm                           ; -- Begin function gemm
	.p2align	2
_gemm:                                  ; @gemm
	.cfi_startproc
; %bb.0:
	sub	sp, sp, #352
	stp	x28, x27, [sp, #256]            ; 16-byte Folded Spill
	stp	x26, x25, [sp, #272]            ; 16-byte Folded Spill
	stp	x24, x23, [sp, #288]            ; 16-byte Folded Spill
	stp	x22, x21, [sp, #304]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #320]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #336]            ; 16-byte Folded Spill
	add	x29, sp, #336
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
	mov	x25, x3
	mov	x26, x2
	mov	x24, x1
Lloh0:
	adrp	x8, ___stack_chk_guard@GOTPAGE
Lloh1:
	ldr	x8, [x8, ___stack_chk_guard@GOTPAGEOFF]
Lloh2:
	ldr	x8, [x8]
	stur	x8, [x29, #-96]
	cmp	w0, #512
	b.ne	LBB0_33
; %bb.1:
	mov	w0, #262144                     ; =0x40000
	bl	_malloc
	mov	x23, x0
	mov	w0, #262144                     ; =0x40000
	bl	_malloc
	mov	x22, x0
	mov	w0, #262144                     ; =0x40000
	bl	_malloc
	mov	x21, x0
	cbz	x23, LBB0_36
; %bb.2:
	cbz	x22, LBB0_36
; %bb.3:
	cbz	x21, LBB0_36
; %bb.4:
	add	x8, x25, #128, lsl #12          ; =524288
	str	x8, [sp, #16]                   ; 8-byte Folded Spill
	mov	x0, x25
	mov	w1, #1048576                    ; =0x100000
	bl	_bzero
	mov	x8, #0                          ; =0x0
	add	x9, x24, #128, lsl #12          ; =524288
	add	x27, x9, #1024
	mov	w9, #3072                       ; =0xc00
	movk	w9, #8, lsl #16
	mov	w10, #3136                      ; =0xc40
	movk	w10, #8, lsl #16
	mov	w11, #3200                      ; =0xc80
	movk	w11, #8, lsl #16
	mov	w12, #3264                      ; =0xcc0
	movk	w12, #8, lsl #16
	mov	w13, #3328                      ; =0xd00
	movk	w13, #8, lsl #16
	mov	w14, #3392                      ; =0xd40
	movk	w14, #8, lsl #16
	mov	w15, #3456                      ; =0xd80
	movk	w15, #8, lsl #16
	mov	w16, #3520                      ; =0xdc0
	movk	w16, #8, lsl #16
	mov	w17, #3584                      ; =0xe00
	movk	w17, #8, lsl #16
	mov	w0, #3648                       ; =0xe40
	movk	w0, #8, lsl #16
	mov	w1, #3712                       ; =0xe80
	movk	w1, #8, lsl #16
	mov	w2, #3776                       ; =0xec0
	movk	w2, #8, lsl #16
	mov	w3, #3840                       ; =0xf00
	movk	w3, #8, lsl #16
	mov	w4, #3904                       ; =0xf40
	movk	w4, #8, lsl #16
	mov	w5, #3968                       ; =0xf80
	movk	w5, #8, lsl #16
	mov	w6, #4032                       ; =0xfc0
	movk	w6, #8, lsl #16
LBB0_5:                                 ; =>This Inner Loop Header: Depth=1
	lsl	x7, x8, #11
	add	x19, x24, x7
	add	x7, x27, x7
	prfm	pldl1keep, [x19, #2048]
	ldp	q0, q1, [x19]
	ldp	q2, q3, [x19, #32]
	prfm	pldl1keep, [x19, x9]
	ldp	q4, q5, [x7]
	ldp	q6, q7, [x7, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x20, x23, x8, lsl #10
	stp	q0, q1, [x20]
	stp	q2, q3, [x20, #32]
	prfm	pldl1keep, [x19, #2112]
	ldp	q0, q1, [x19, #64]
	ldp	q2, q3, [x19, #96]
	prfm	pldl1keep, [x19, x10]
	ldp	q4, q5, [x7, #64]
	ldp	q6, q7, [x7, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #64]
	stp	q2, q3, [x20, #96]
	prfm	pldl1keep, [x19, #2176]
	ldp	q0, q1, [x19, #128]
	ldp	q2, q3, [x19, #160]
	prfm	pldl1keep, [x19, x11]
	ldp	q4, q5, [x7, #128]
	ldp	q6, q7, [x7, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #128]
	stp	q2, q3, [x20, #160]
	prfm	pldl1keep, [x19, #2240]
	ldp	q0, q1, [x19, #192]
	ldp	q2, q3, [x19, #224]
	prfm	pldl1keep, [x19, x12]
	ldp	q4, q5, [x7, #192]
	ldp	q6, q7, [x7, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #192]
	stp	q2, q3, [x20, #224]
	prfm	pldl1keep, [x19, #2304]
	ldp	q0, q1, [x19, #256]
	ldp	q2, q3, [x19, #288]
	prfm	pldl1keep, [x19, x13]
	ldp	q4, q5, [x7, #256]
	ldp	q6, q7, [x7, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #256]
	stp	q2, q3, [x20, #288]
	prfm	pldl1keep, [x19, #2368]
	ldp	q0, q1, [x19, #320]
	ldp	q2, q3, [x19, #352]
	prfm	pldl1keep, [x19, x14]
	ldp	q4, q5, [x7, #320]
	ldp	q6, q7, [x7, #352]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #320]
	stp	q2, q3, [x20, #352]
	prfm	pldl1keep, [x19, #2432]
	ldp	q0, q1, [x19, #384]
	ldp	q2, q3, [x19, #416]
	prfm	pldl1keep, [x19, x15]
	ldp	q4, q5, [x7, #384]
	ldp	q6, q7, [x7, #416]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #384]
	stp	q2, q3, [x20, #416]
	prfm	pldl1keep, [x19, #2496]
	ldp	q0, q1, [x19, #448]
	ldp	q2, q3, [x19, #480]
	prfm	pldl1keep, [x19, x16]
	ldp	q4, q5, [x7, #448]
	ldp	q6, q7, [x7, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #448]
	stp	q2, q3, [x20, #480]
	prfm	pldl1keep, [x19, #2560]
	ldp	q0, q1, [x19, #512]
	ldp	q2, q3, [x19, #544]
	prfm	pldl1keep, [x19, x17]
	ldp	q4, q5, [x7, #512]
	ldp	q6, q7, [x7, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #512]
	stp	q2, q3, [x20, #544]
	prfm	pldl1keep, [x19, #2624]
	ldp	q0, q1, [x19, #576]
	ldp	q2, q3, [x19, #608]
	prfm	pldl1keep, [x19, x0]
	ldp	q4, q5, [x7, #576]
	ldp	q6, q7, [x7, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #576]
	stp	q2, q3, [x20, #608]
	prfm	pldl1keep, [x19, #2688]
	ldp	q0, q1, [x19, #640]
	ldp	q2, q3, [x19, #672]
	prfm	pldl1keep, [x19, x1]
	ldp	q4, q5, [x7, #640]
	ldp	q6, q7, [x7, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #640]
	stp	q2, q3, [x20, #672]
	prfm	pldl1keep, [x19, #2752]
	ldp	q0, q1, [x19, #704]
	ldp	q2, q3, [x19, #736]
	prfm	pldl1keep, [x19, x2]
	ldp	q4, q5, [x7, #704]
	ldp	q6, q7, [x7, #736]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #704]
	stp	q2, q3, [x20, #736]
	prfm	pldl1keep, [x19, #2816]
	ldp	q0, q1, [x19, #768]
	ldp	q2, q3, [x19, #800]
	prfm	pldl1keep, [x19, x3]
	ldp	q4, q5, [x7, #768]
	ldp	q6, q7, [x7, #800]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #768]
	stp	q2, q3, [x20, #800]
	prfm	pldl1keep, [x19, #2880]
	ldp	q0, q1, [x19, #832]
	ldp	q2, q3, [x19, #864]
	prfm	pldl1keep, [x19, x4]
	ldp	q4, q5, [x7, #832]
	ldp	q6, q7, [x7, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #832]
	stp	q2, q3, [x20, #864]
	prfm	pldl1keep, [x19, #2944]
	ldp	q0, q1, [x19, #896]
	ldp	q2, q3, [x19, #928]
	prfm	pldl1keep, [x19, x5]
	ldp	q4, q5, [x7, #896]
	ldp	q6, q7, [x7, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #896]
	stp	q2, q3, [x20, #928]
	prfm	pldl1keep, [x19, #3008]
	ldp	q0, q1, [x19, #960]
	ldp	q2, q3, [x19, #992]
	prfm	pldl1keep, [x19, x6]
	ldp	q4, q5, [x7, #960]
	ldp	q6, q7, [x7, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #960]
	stp	q2, q3, [x20, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_5
; %bb.6:
	str	x27, [sp, #24]                  ; 8-byte Folded Spill
	mov	x8, #0                          ; =0x0
	add	x9, x26, #128, lsl #12          ; =524288
	add	x27, x9, #1024
	mov	w9, #3072                       ; =0xc00
	movk	w9, #8, lsl #16
	mov	w10, #3136                      ; =0xc40
	movk	w10, #8, lsl #16
	mov	w11, #3200                      ; =0xc80
	movk	w11, #8, lsl #16
	mov	w12, #3264                      ; =0xcc0
	movk	w12, #8, lsl #16
	mov	w13, #3328                      ; =0xd00
	movk	w13, #8, lsl #16
	mov	w14, #3392                      ; =0xd40
	movk	w14, #8, lsl #16
	mov	w15, #3456                      ; =0xd80
	movk	w15, #8, lsl #16
	mov	w16, #3520                      ; =0xdc0
	movk	w16, #8, lsl #16
	mov	w17, #3584                      ; =0xe00
	movk	w17, #8, lsl #16
	mov	w0, #3648                       ; =0xe40
	movk	w0, #8, lsl #16
	mov	w1, #3712                       ; =0xe80
	movk	w1, #8, lsl #16
	mov	w2, #3776                       ; =0xec0
	movk	w2, #8, lsl #16
	mov	w3, #3840                       ; =0xf00
	movk	w3, #8, lsl #16
	mov	w4, #3904                       ; =0xf40
	movk	w4, #8, lsl #16
	mov	w5, #3968                       ; =0xf80
	movk	w5, #8, lsl #16
	mov	w6, #4032                       ; =0xfc0
	movk	w6, #8, lsl #16
LBB0_7:                                 ; =>This Inner Loop Header: Depth=1
	lsl	x7, x8, #11
	add	x19, x26, x7
	add	x7, x27, x7
	prfm	pldl1keep, [x19, #2048]
	ldp	q0, q1, [x19]
	ldp	q2, q3, [x19, #32]
	prfm	pldl1keep, [x19, x9]
	ldp	q4, q5, [x7]
	ldp	q6, q7, [x7, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x20, x22, x8, lsl #10
	stp	q0, q1, [x20]
	stp	q2, q3, [x20, #32]
	prfm	pldl1keep, [x19, #2112]
	ldp	q0, q1, [x19, #64]
	ldp	q2, q3, [x19, #96]
	prfm	pldl1keep, [x19, x10]
	ldp	q4, q5, [x7, #64]
	ldp	q6, q7, [x7, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #64]
	stp	q2, q3, [x20, #96]
	prfm	pldl1keep, [x19, #2176]
	ldp	q0, q1, [x19, #128]
	ldp	q2, q3, [x19, #160]
	prfm	pldl1keep, [x19, x11]
	ldp	q4, q5, [x7, #128]
	ldp	q6, q7, [x7, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #128]
	stp	q2, q3, [x20, #160]
	prfm	pldl1keep, [x19, #2240]
	ldp	q0, q1, [x19, #192]
	ldp	q2, q3, [x19, #224]
	prfm	pldl1keep, [x19, x12]
	ldp	q4, q5, [x7, #192]
	ldp	q6, q7, [x7, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #192]
	stp	q2, q3, [x20, #224]
	prfm	pldl1keep, [x19, #2304]
	ldp	q0, q1, [x19, #256]
	ldp	q2, q3, [x19, #288]
	prfm	pldl1keep, [x19, x13]
	ldp	q4, q5, [x7, #256]
	ldp	q6, q7, [x7, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #256]
	stp	q2, q3, [x20, #288]
	prfm	pldl1keep, [x19, #2368]
	ldp	q0, q1, [x19, #320]
	ldp	q2, q3, [x19, #352]
	prfm	pldl1keep, [x19, x14]
	ldp	q4, q5, [x7, #320]
	ldp	q6, q7, [x7, #352]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #320]
	stp	q2, q3, [x20, #352]
	prfm	pldl1keep, [x19, #2432]
	ldp	q0, q1, [x19, #384]
	ldp	q2, q3, [x19, #416]
	prfm	pldl1keep, [x19, x15]
	ldp	q4, q5, [x7, #384]
	ldp	q6, q7, [x7, #416]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #384]
	stp	q2, q3, [x20, #416]
	prfm	pldl1keep, [x19, #2496]
	ldp	q0, q1, [x19, #448]
	ldp	q2, q3, [x19, #480]
	prfm	pldl1keep, [x19, x16]
	ldp	q4, q5, [x7, #448]
	ldp	q6, q7, [x7, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #448]
	stp	q2, q3, [x20, #480]
	prfm	pldl1keep, [x19, #2560]
	ldp	q0, q1, [x19, #512]
	ldp	q2, q3, [x19, #544]
	prfm	pldl1keep, [x19, x17]
	ldp	q4, q5, [x7, #512]
	ldp	q6, q7, [x7, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #512]
	stp	q2, q3, [x20, #544]
	prfm	pldl1keep, [x19, #2624]
	ldp	q0, q1, [x19, #576]
	ldp	q2, q3, [x19, #608]
	prfm	pldl1keep, [x19, x0]
	ldp	q4, q5, [x7, #576]
	ldp	q6, q7, [x7, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #576]
	stp	q2, q3, [x20, #608]
	prfm	pldl1keep, [x19, #2688]
	ldp	q0, q1, [x19, #640]
	ldp	q2, q3, [x19, #672]
	prfm	pldl1keep, [x19, x1]
	ldp	q4, q5, [x7, #640]
	ldp	q6, q7, [x7, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #640]
	stp	q2, q3, [x20, #672]
	prfm	pldl1keep, [x19, #2752]
	ldp	q0, q1, [x19, #704]
	ldp	q2, q3, [x19, #736]
	prfm	pldl1keep, [x19, x2]
	ldp	q4, q5, [x7, #704]
	ldp	q6, q7, [x7, #736]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #704]
	stp	q2, q3, [x20, #736]
	prfm	pldl1keep, [x19, #2816]
	ldp	q0, q1, [x19, #768]
	ldp	q2, q3, [x19, #800]
	prfm	pldl1keep, [x19, x3]
	ldp	q4, q5, [x7, #768]
	ldp	q6, q7, [x7, #800]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #768]
	stp	q2, q3, [x20, #800]
	prfm	pldl1keep, [x19, #2880]
	ldp	q0, q1, [x19, #832]
	ldp	q2, q3, [x19, #864]
	prfm	pldl1keep, [x19, x4]
	ldp	q4, q5, [x7, #832]
	ldp	q6, q7, [x7, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #832]
	stp	q2, q3, [x20, #864]
	prfm	pldl1keep, [x19, #2944]
	ldp	q0, q1, [x19, #896]
	ldp	q2, q3, [x19, #928]
	prfm	pldl1keep, [x19, x5]
	ldp	q4, q5, [x7, #896]
	ldp	q6, q7, [x7, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #896]
	stp	q2, q3, [x20, #928]
	prfm	pldl1keep, [x19, #3008]
	ldp	q0, q1, [x19, #960]
	ldp	q2, q3, [x19, #992]
	prfm	pldl1keep, [x19, x6]
	ldp	q4, q5, [x7, #960]
	ldp	q6, q7, [x7, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x20, #960]
	stp	q2, q3, [x20, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_7
; %bb.8:
	str	x27, [sp, #48]                  ; 8-byte Folded Spill
	str	x26, [sp, #32]                  ; 8-byte Folded Spill
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	mov	w19, #1024                      ; =0x400
	movk	w19, #8, lsl #16
	add	x8, x25, x19
	str	x8, [sp, #8]                    ; 8-byte Folded Spill
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	str	x21, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	add	x9, x21, #16
	mov	x10, x25
LBB0_9:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_10 Depth 2
	mov	x11, x10
	mov	x12, x9
	mov	w13, #256                       ; =0x100
LBB0_10:                                ;   Parent Loop BB0_9 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldp	q0, q1, [x12, #-16]
	ldp	q2, q3, [x11]
	fadd.4s	v2, v2, v0
	fadd.4s	v3, v3, v1
	stp	q2, q3, [x11]
	add	x14, x11, x19
	ldp	q2, q3, [x14]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	stp	q0, q1, [x14]
	add	x12, x12, #32
	add	x11, x11, #32
	subs	x13, x13, #8
	b.ne	LBB0_10
; %bb.11:                               ;   in Loop: Header=BB0_9 Depth=1
	add	x8, x8, #1
	add	x9, x9, #1024
	add	x10, x10, #2048
	cmp	x8, #256
	b.ne	LBB0_9
; %bb.12:
	str	x21, [sp, #56]                  ; 8-byte Folded Spill
	str	x25, [sp, #40]                  ; 8-byte Folded Spill
	mov	x8, #0                          ; =0x0
	add	x25, x24, #128, lsl #12         ; =524288
	mov	w5, #2496                       ; =0x9c0
	movk	w5, #8, lsl #16
	mov	w6, #3520                       ; =0xdc0
	movk	w6, #8, lsl #16
	mov	w7, #2560                       ; =0xa00
	movk	w7, #8, lsl #16
	mov	w26, #3584                      ; =0xe00
	movk	w26, #8, lsl #16
	mov	w30, #2624                      ; =0xa40
	movk	w30, #8, lsl #16
	mov	w21, #3648                      ; =0xe40
	movk	w21, #8, lsl #16
	mov	w19, #2688                      ; =0xa80
	movk	w19, #8, lsl #16
	mov	w28, #3712                      ; =0xe80
	movk	w28, #8, lsl #16
	mov	w27, #2752                      ; =0xac0
	movk	w27, #8, lsl #16
	mov	w20, #3776                      ; =0xec0
	movk	w20, #8, lsl #16
	mov	w9, #2816                       ; =0xb00
	movk	w9, #8, lsl #16
	mov	w10, #3840                      ; =0xf00
	movk	w10, #8, lsl #16
	mov	w11, #2880                      ; =0xb40
	movk	w11, #8, lsl #16
	mov	w12, #3904                      ; =0xf40
	movk	w12, #8, lsl #16
	mov	w13, #2944                      ; =0xb80
	movk	w13, #8, lsl #16
	mov	w14, #3968                      ; =0xf80
	movk	w14, #8, lsl #16
	mov	w15, #3008                      ; =0xbc0
	movk	w15, #8, lsl #16
	mov	w16, #4032                      ; =0xfc0
	movk	w16, #8, lsl #16
	ldr	x3, [sp, #24]                   ; 8-byte Folded Reload
LBB0_13:                                ; =>This Inner Loop Header: Depth=1
	lsl	x1, x8, #11
	add	x0, x24, x1
	add	x17, x3, x1
	add	x1, x25, x1
	mov	w2, #2048                       ; =0x800
	movk	w2, #8, lsl #16
	prfm	pldl1keep, [x0, x2]
	ldp	q0, q1, [x1]
	ldp	q2, q3, [x1, #32]
	mov	w2, #3072                       ; =0xc00
	movk	w2, #8, lsl #16
	prfm	pldl1keep, [x0, x2]
	ldp	q4, q5, [x17]
	ldp	q6, q7, [x17, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x2, x23, x8, lsl #10
	stp	q0, q1, [x2]
	stp	q2, q3, [x2, #32]
	mov	w4, #2112                       ; =0x840
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #64]
	ldp	q2, q3, [x1, #96]
	mov	w4, #3136                       ; =0xc40
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #64]
	ldp	q6, q7, [x17, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #64]
	stp	q2, q3, [x2, #96]
	mov	w4, #2176                       ; =0x880
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #128]
	ldp	q2, q3, [x1, #160]
	mov	w4, #3200                       ; =0xc80
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #128]
	ldp	q6, q7, [x17, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #128]
	stp	q2, q3, [x2, #160]
	mov	w4, #2240                       ; =0x8c0
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #192]
	ldp	q2, q3, [x1, #224]
	mov	w4, #3264                       ; =0xcc0
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #192]
	ldp	q6, q7, [x17, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #192]
	stp	q2, q3, [x2, #224]
	mov	w4, #2304                       ; =0x900
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #256]
	ldp	q2, q3, [x1, #288]
	mov	w4, #3328                       ; =0xd00
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #256]
	ldp	q6, q7, [x17, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #256]
	stp	q2, q3, [x2, #288]
	mov	w4, #2368                       ; =0x940
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #320]
	ldp	q2, q3, [x1, #352]
	mov	w4, #3392                       ; =0xd40
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #320]
	ldp	q6, q7, [x17, #352]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #320]
	stp	q2, q3, [x2, #352]
	mov	w4, #2432                       ; =0x980
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q0, q1, [x1, #384]
	ldp	q2, q3, [x1, #416]
	mov	w4, #3456                       ; =0xd80
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x0, x4]
	ldp	q4, q5, [x17, #384]
	ldp	q6, q7, [x17, #416]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #384]
	stp	q2, q3, [x2, #416]
	prfm	pldl1keep, [x0, x5]
	ldp	q0, q1, [x1, #448]
	ldp	q2, q3, [x1, #480]
	prfm	pldl1keep, [x0, x6]
	ldp	q4, q5, [x17, #448]
	ldp	q6, q7, [x17, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #448]
	stp	q2, q3, [x2, #480]
	prfm	pldl1keep, [x0, x7]
	ldp	q0, q1, [x1, #512]
	ldp	q2, q3, [x1, #544]
	prfm	pldl1keep, [x0, x26]
	ldp	q4, q5, [x17, #512]
	ldp	q6, q7, [x17, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #512]
	stp	q2, q3, [x2, #544]
	prfm	pldl1keep, [x0, x30]
	ldp	q0, q1, [x1, #576]
	ldp	q2, q3, [x1, #608]
	prfm	pldl1keep, [x0, x21]
	ldp	q4, q5, [x17, #576]
	ldp	q6, q7, [x17, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #576]
	stp	q2, q3, [x2, #608]
	prfm	pldl1keep, [x0, x19]
	ldp	q0, q1, [x1, #640]
	ldp	q2, q3, [x1, #672]
	prfm	pldl1keep, [x0, x28]
	ldp	q4, q5, [x17, #640]
	ldp	q6, q7, [x17, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #640]
	stp	q2, q3, [x2, #672]
	prfm	pldl1keep, [x0, x27]
	ldp	q0, q1, [x1, #704]
	ldp	q2, q3, [x1, #736]
	prfm	pldl1keep, [x0, x20]
	ldp	q4, q5, [x17, #704]
	ldp	q6, q7, [x17, #736]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #704]
	stp	q2, q3, [x2, #736]
	prfm	pldl1keep, [x0, x9]
	ldp	q0, q1, [x1, #768]
	ldp	q2, q3, [x1, #800]
	prfm	pldl1keep, [x0, x10]
	ldp	q4, q5, [x17, #768]
	ldp	q6, q7, [x17, #800]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #768]
	stp	q2, q3, [x2, #800]
	prfm	pldl1keep, [x0, x11]
	ldp	q0, q1, [x1, #832]
	ldp	q2, q3, [x1, #864]
	prfm	pldl1keep, [x0, x12]
	ldp	q4, q5, [x17, #832]
	ldp	q6, q7, [x17, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #832]
	stp	q2, q3, [x2, #864]
	prfm	pldl1keep, [x0, x13]
	ldp	q0, q1, [x1, #896]
	ldp	q2, q3, [x1, #928]
	prfm	pldl1keep, [x0, x14]
	ldp	q4, q5, [x17, #896]
	ldp	q6, q7, [x17, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #896]
	stp	q2, q3, [x2, #928]
	prfm	pldl1keep, [x0, x15]
	ldp	q0, q1, [x1, #960]
	ldp	q2, q3, [x1, #992]
	prfm	pldl1keep, [x0, x16]
	ldp	q4, q5, [x17, #960]
	ldp	q6, q7, [x17, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x2, #960]
	stp	q2, q3, [x2, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_13
; %bb.14:
	mov	x19, #0                         ; =0x0
	ldr	x28, [sp, #32]                  ; 8-byte Folded Reload
	mov	x26, x28
LBB0_15:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x22, x19
	mov	x1, x26
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x26, x26, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_15
; %bb.16:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	ldr	x19, [sp, #56]                  ; 8-byte Folded Reload
	str	x19, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	add	x9, x19, #16
	ldr	x10, [sp, #16]                  ; 8-byte Folded Reload
	ldr	x27, [sp, #40]                  ; 8-byte Folded Reload
LBB0_17:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_18 Depth 2
	mov	x11, x10
	mov	x12, x9
	mov	w13, #256                       ; =0x100
LBB0_18:                                ;   Parent Loop BB0_17 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldp	q0, q1, [x12, #-16]
	ldp	q2, q3, [x11]
	fadd.4s	v2, v2, v0
	fadd.4s	v3, v3, v1
	stp	q2, q3, [x11]
	ldr	q2, [x11, #1024]
	ldr	q3, [x11, #1040]
	fsub.4s	v0, v2, v0
	fsub.4s	v1, v3, v1
	str	q0, [x11, #1024]
	str	q1, [x11, #1040]
	add	x12, x12, #32
	add	x11, x11, #32
	subs	x13, x13, #8
	b.ne	LBB0_18
; %bb.19:                               ;   in Loop: Header=BB0_17 Depth=1
	add	x8, x8, #1
	add	x9, x9, #1024
	add	x10, x10, #2048
	cmp	x8, #256
	b.ne	LBB0_17
; %bb.20:
	mov	x19, #0                         ; =0x0
	mov	x26, x24
LBB0_21:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x23, x19
	mov	x1, x26
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x26, x26, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_21
; %bb.22:
	mov	x8, #0                          ; =0x0
	add	x9, x28, #1024
	mov	w10, #3072                      ; =0xc00
	movk	w10, #8, lsl #16
	mov	w11, #3136                      ; =0xc40
	movk	w11, #8, lsl #16
	mov	w12, #3200                      ; =0xc80
	movk	w12, #8, lsl #16
	mov	w13, #3264                      ; =0xcc0
	movk	w13, #8, lsl #16
	mov	w14, #3328                      ; =0xd00
	movk	w14, #8, lsl #16
	mov	w15, #3392                      ; =0xd40
	movk	w15, #8, lsl #16
	mov	w16, #3456                      ; =0xd80
	movk	w16, #8, lsl #16
	mov	w17, #3520                      ; =0xdc0
	movk	w17, #8, lsl #16
	mov	w0, #3584                       ; =0xe00
	movk	w0, #8, lsl #16
	mov	w1, #3648                       ; =0xe40
	movk	w1, #8, lsl #16
	mov	w2, #3712                       ; =0xe80
	movk	w2, #8, lsl #16
	mov	w3, #3776                       ; =0xec0
	movk	w3, #8, lsl #16
	mov	w4, #3840                       ; =0xf00
	movk	w4, #8, lsl #16
	mov	w5, #3904                       ; =0xf40
	movk	w5, #8, lsl #16
	mov	w6, #3968                       ; =0xf80
	movk	w6, #8, lsl #16
	mov	w7, #4032                       ; =0xfc0
	movk	w7, #8, lsl #16
	ldr	x30, [sp, #48]                  ; 8-byte Folded Reload
LBB0_23:                                ; =>This Inner Loop Header: Depth=1
	lsl	x21, x8, #11
	add	x20, x28, x21
	add	x19, x30, x21
	add	x21, x9, x21
	prfm	pldl1keep, [x20, #3072]
	ldp	q0, q1, [x21]
	ldp	q2, q3, [x21, #32]
	prfm	pldl1keep, [x20, x10]
	ldp	q4, q5, [x19]
	ldp	q6, q7, [x19, #32]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	add	x26, x22, x8, lsl #10
	stp	q0, q1, [x26]
	stp	q2, q3, [x26, #32]
	prfm	pldl1keep, [x20, #3136]
	ldp	q0, q1, [x21, #64]
	ldp	q2, q3, [x21, #96]
	prfm	pldl1keep, [x20, x11]
	ldp	q4, q5, [x19, #64]
	ldp	q6, q7, [x19, #96]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #64]
	stp	q2, q3, [x26, #96]
	prfm	pldl1keep, [x20, #3200]
	ldp	q0, q1, [x21, #128]
	ldp	q2, q3, [x21, #160]
	prfm	pldl1keep, [x20, x12]
	ldp	q4, q5, [x19, #128]
	ldp	q6, q7, [x19, #160]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #128]
	stp	q2, q3, [x26, #160]
	prfm	pldl1keep, [x20, #3264]
	ldp	q0, q1, [x21, #192]
	ldp	q2, q3, [x21, #224]
	prfm	pldl1keep, [x20, x13]
	ldp	q4, q5, [x19, #192]
	ldp	q6, q7, [x19, #224]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #192]
	stp	q2, q3, [x26, #224]
	prfm	pldl1keep, [x20, #3328]
	ldp	q0, q1, [x21, #256]
	ldp	q2, q3, [x21, #288]
	prfm	pldl1keep, [x20, x14]
	ldp	q4, q5, [x19, #256]
	ldp	q6, q7, [x19, #288]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #256]
	stp	q2, q3, [x26, #288]
	prfm	pldl1keep, [x20, #3392]
	ldp	q0, q1, [x21, #320]
	ldp	q2, q3, [x21, #352]
	prfm	pldl1keep, [x20, x15]
	ldp	q4, q5, [x19, #320]
	ldp	q6, q7, [x19, #352]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #320]
	stp	q2, q3, [x26, #352]
	prfm	pldl1keep, [x20, #3456]
	ldp	q0, q1, [x21, #384]
	ldp	q2, q3, [x21, #416]
	prfm	pldl1keep, [x20, x16]
	ldp	q4, q5, [x19, #384]
	ldp	q6, q7, [x19, #416]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #384]
	stp	q2, q3, [x26, #416]
	prfm	pldl1keep, [x20, #3520]
	ldp	q0, q1, [x21, #448]
	ldp	q2, q3, [x21, #480]
	prfm	pldl1keep, [x20, x17]
	ldp	q4, q5, [x19, #448]
	ldp	q6, q7, [x19, #480]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #448]
	stp	q2, q3, [x26, #480]
	prfm	pldl1keep, [x20, #3584]
	ldp	q0, q1, [x21, #512]
	ldp	q2, q3, [x21, #544]
	prfm	pldl1keep, [x20, x0]
	ldp	q4, q5, [x19, #512]
	ldp	q6, q7, [x19, #544]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #512]
	stp	q2, q3, [x26, #544]
	prfm	pldl1keep, [x20, #3648]
	ldp	q0, q1, [x21, #576]
	ldp	q2, q3, [x21, #608]
	prfm	pldl1keep, [x20, x1]
	ldp	q4, q5, [x19, #576]
	ldp	q6, q7, [x19, #608]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #576]
	stp	q2, q3, [x26, #608]
	prfm	pldl1keep, [x20, #3712]
	ldp	q0, q1, [x21, #640]
	ldp	q2, q3, [x21, #672]
	prfm	pldl1keep, [x20, x2]
	ldp	q4, q5, [x19, #640]
	ldp	q6, q7, [x19, #672]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #640]
	stp	q2, q3, [x26, #672]
	prfm	pldl1keep, [x20, #3776]
	ldp	q0, q1, [x21, #704]
	ldp	q2, q3, [x21, #736]
	prfm	pldl1keep, [x20, x3]
	ldp	q4, q5, [x19, #704]
	ldp	q6, q7, [x19, #736]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #704]
	stp	q2, q3, [x26, #736]
	prfm	pldl1keep, [x20, #3840]
	ldp	q0, q1, [x21, #768]
	ldp	q2, q3, [x21, #800]
	prfm	pldl1keep, [x20, x4]
	ldp	q4, q5, [x19, #768]
	ldp	q6, q7, [x19, #800]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #768]
	stp	q2, q3, [x26, #800]
	prfm	pldl1keep, [x20, #3904]
	ldp	q0, q1, [x21, #832]
	ldp	q2, q3, [x21, #864]
	prfm	pldl1keep, [x20, x5]
	ldp	q4, q5, [x19, #832]
	ldp	q6, q7, [x19, #864]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #832]
	stp	q2, q3, [x26, #864]
	prfm	pldl1keep, [x20, #3968]
	ldp	q0, q1, [x21, #896]
	ldp	q2, q3, [x21, #928]
	prfm	pldl1keep, [x20, x6]
	ldp	q4, q5, [x19, #896]
	ldp	q6, q7, [x19, #928]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #896]
	stp	q2, q3, [x26, #928]
	prfm	pldl1keep, [x20, #4032]
	ldp	q0, q1, [x21, #960]
	ldp	q2, q3, [x21, #992]
	prfm	pldl1keep, [x20, x7]
	ldp	q4, q5, [x19, #960]
	ldp	q6, q7, [x19, #992]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x26, #960]
	stp	q2, q3, [x26, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_23
; %bb.24:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	ldr	x21, [sp, #56]                  ; 8-byte Folded Reload
	str	x21, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	add	x9, x27, #1024
	add	x10, x21, #16
	ldr	x11, [sp, #16]                  ; 8-byte Folded Reload
	add	x11, x11, #1040
	mov	x12, #-524288                   ; =0xfffffffffff80000
LBB0_25:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_26 Depth 2
	mov	x13, x9
	mov	x14, x11
	mov	x15, x10
	mov	w16, #256                       ; =0x100
LBB0_26:                                ;   Parent Loop BB0_25 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldp	q0, q1, [x15, #-16]
	ldr	q2, [x13]
	ldr	q3, [x14, x12]
	fadd.4s	v2, v2, v0
	str	q2, [x13], #32
	fadd.4s	v2, v3, v1
	str	q2, [x14, x12]
	ldp	q2, q3, [x14, #-16]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	stp	q0, q1, [x14, #-16]
	add	x15, x15, #32
	add	x14, x14, #32
	subs	x16, x16, #8
	b.ne	LBB0_26
; %bb.27:                               ;   in Loop: Header=BB0_25 Depth=1
	add	x8, x8, #1
	add	x10, x10, #1024
	add	x11, x11, #2048
	add	x9, x9, #2048
	cmp	x8, #256
	b.ne	LBB0_25
; %bb.28:
	mov	x19, #0                         ; =0x0
	mov	w20, #1024                      ; =0x400
	movk	w20, #8, lsl #16
LBB0_29:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x23, x19
	add	x1, x24, x20
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x20, x20, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_29
; %bb.30:
	add	x26, x28, #128, lsl #12         ; =524288
	str	x26, [sp, #16]                  ; 8-byte Folded Spill
	cbz	x28, LBB0_61
; %bb.31:
	mov	x8, #0                          ; =0x0
	mov	w9, #2048                       ; =0x800
	movk	w9, #8, lsl #16
	mov	w10, #2112                      ; =0x840
	movk	w10, #8, lsl #16
	mov	w11, #2176                      ; =0x880
	movk	w11, #8, lsl #16
	mov	w12, #2240                      ; =0x8c0
	movk	w12, #8, lsl #16
	mov	w13, #2304                      ; =0x900
	movk	w13, #8, lsl #16
	mov	w14, #2368                      ; =0x940
	movk	w14, #8, lsl #16
	mov	w15, #2432                      ; =0x980
	movk	w15, #8, lsl #16
	mov	w16, #2496                      ; =0x9c0
	movk	w16, #8, lsl #16
	mov	w17, #2560                      ; =0xa00
	movk	w17, #8, lsl #16
	mov	w0, #2624                       ; =0xa40
	movk	w0, #8, lsl #16
	mov	w1, #2688                       ; =0xa80
	movk	w1, #8, lsl #16
	mov	w2, #2752                       ; =0xac0
	movk	w2, #8, lsl #16
	mov	w3, #2816                       ; =0xb00
	movk	w3, #8, lsl #16
	mov	w4, #2880                       ; =0xb40
	movk	w4, #8, lsl #16
	mov	w5, #2944                       ; =0xb80
	movk	w5, #8, lsl #16
	mov	w6, #3008                       ; =0xbc0
	movk	w6, #8, lsl #16
LBB0_32:                                ; =>This Inner Loop Header: Depth=1
	lsl	x19, x8, #11
	add	x7, x28, x19
	add	x19, x26, x19
	prfm	pldl1keep, [x7, x9]
	ldp	q0, q1, [x19]
	ldp	q2, q3, [x19, #32]
	prfm	pldl1keep, [x7, #2048]
	ldp	q4, q5, [x7]
	ldp	q6, q7, [x7, #32]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	add	x20, x22, x8, lsl #10
	stp	q0, q1, [x20]
	stp	q2, q3, [x20, #32]
	prfm	pldl1keep, [x7, x10]
	ldp	q0, q1, [x19, #64]
	ldp	q2, q3, [x19, #96]
	prfm	pldl1keep, [x7, #2112]
	ldp	q4, q5, [x7, #64]
	ldp	q6, q7, [x7, #96]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #64]
	stp	q2, q3, [x20, #96]
	prfm	pldl1keep, [x7, x11]
	ldp	q0, q1, [x19, #128]
	ldp	q2, q3, [x19, #160]
	prfm	pldl1keep, [x7, #2176]
	ldp	q4, q5, [x7, #128]
	ldp	q6, q7, [x7, #160]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #128]
	stp	q2, q3, [x20, #160]
	prfm	pldl1keep, [x7, x12]
	ldp	q0, q1, [x19, #192]
	ldp	q2, q3, [x19, #224]
	prfm	pldl1keep, [x7, #2240]
	ldp	q4, q5, [x7, #192]
	ldp	q6, q7, [x7, #224]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #192]
	stp	q2, q3, [x20, #224]
	prfm	pldl1keep, [x7, x13]
	ldp	q0, q1, [x19, #256]
	ldp	q2, q3, [x19, #288]
	prfm	pldl1keep, [x7, #2304]
	ldp	q4, q5, [x7, #256]
	ldp	q6, q7, [x7, #288]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #256]
	stp	q2, q3, [x20, #288]
	prfm	pldl1keep, [x7, x14]
	ldp	q0, q1, [x19, #320]
	ldp	q2, q3, [x19, #352]
	prfm	pldl1keep, [x7, #2368]
	ldp	q4, q5, [x7, #320]
	ldp	q6, q7, [x7, #352]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #320]
	stp	q2, q3, [x20, #352]
	prfm	pldl1keep, [x7, x15]
	ldp	q0, q1, [x19, #384]
	ldp	q2, q3, [x19, #416]
	prfm	pldl1keep, [x7, #2432]
	ldp	q4, q5, [x7, #384]
	ldp	q6, q7, [x7, #416]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #384]
	stp	q2, q3, [x20, #416]
	prfm	pldl1keep, [x7, x16]
	ldp	q0, q1, [x19, #448]
	ldp	q2, q3, [x19, #480]
	prfm	pldl1keep, [x7, #2496]
	ldp	q4, q5, [x7, #448]
	ldp	q6, q7, [x7, #480]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #448]
	stp	q2, q3, [x20, #480]
	prfm	pldl1keep, [x7, x17]
	ldp	q0, q1, [x19, #512]
	ldp	q2, q3, [x19, #544]
	prfm	pldl1keep, [x7, #2560]
	ldp	q4, q5, [x7, #512]
	ldp	q6, q7, [x7, #544]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #512]
	stp	q2, q3, [x20, #544]
	prfm	pldl1keep, [x7, x0]
	ldp	q0, q1, [x19, #576]
	ldp	q2, q3, [x19, #608]
	prfm	pldl1keep, [x7, #2624]
	ldp	q4, q5, [x7, #576]
	ldp	q6, q7, [x7, #608]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #576]
	stp	q2, q3, [x20, #608]
	prfm	pldl1keep, [x7, x1]
	ldp	q0, q1, [x19, #640]
	ldp	q2, q3, [x19, #672]
	prfm	pldl1keep, [x7, #2688]
	ldp	q4, q5, [x7, #640]
	ldp	q6, q7, [x7, #672]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #640]
	stp	q2, q3, [x20, #672]
	prfm	pldl1keep, [x7, x2]
	ldp	q0, q1, [x19, #704]
	ldp	q2, q3, [x19, #736]
	prfm	pldl1keep, [x7, #2752]
	ldp	q4, q5, [x7, #704]
	ldp	q6, q7, [x7, #736]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #704]
	stp	q2, q3, [x20, #736]
	prfm	pldl1keep, [x7, x3]
	ldp	q0, q1, [x19, #768]
	ldp	q2, q3, [x19, #800]
	prfm	pldl1keep, [x7, #2816]
	ldp	q4, q5, [x7, #768]
	ldp	q6, q7, [x7, #800]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #768]
	stp	q2, q3, [x20, #800]
	prfm	pldl1keep, [x7, x4]
	ldp	q0, q1, [x19, #832]
	ldp	q2, q3, [x19, #864]
	prfm	pldl1keep, [x7, #2880]
	ldp	q4, q5, [x7, #832]
	ldp	q6, q7, [x7, #864]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #832]
	stp	q2, q3, [x20, #864]
	prfm	pldl1keep, [x7, x5]
	ldp	q0, q1, [x19, #896]
	ldp	q2, q3, [x19, #928]
	prfm	pldl1keep, [x7, #2944]
	ldp	q4, q5, [x7, #896]
	ldp	q6, q7, [x7, #928]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #896]
	stp	q2, q3, [x20, #928]
	prfm	pldl1keep, [x7, x6]
	ldp	q0, q1, [x19, #960]
	ldp	q2, q3, [x19, #992]
	prfm	pldl1keep, [x7, #3008]
	ldp	q4, q5, [x7, #960]
	ldp	q6, q7, [x7, #992]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #960]
	stp	q2, q3, [x20, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_32
	b	LBB0_63
LBB0_33:
	cmp	w0, #1
	b.lt	LBB0_91
; %bb.34:
	mov	x22, x0
	umull	x8, w0, w0
	lsl	x0, x8, #2
	bl	_malloc
	cbz	x0, LBB0_40
; %bb.35:
	mov	x21, x0
	mov	x0, x22
	mov	x1, x24
	mov	x2, x21
	bl	_sme_transpose
	mov	x0, x22
	b	LBB0_38
LBB0_36:
	mov	x0, x23
	bl	_free
	mov	x0, x22
	bl	_free
	mov	x0, x21
	bl	_free
	mov	w0, #1048576                    ; =0x100000
	bl	_malloc
	cbz	x0, LBB0_55
; %bb.37:
	mov	x21, x0
	mov	w0, #512                        ; =0x200
	mov	x1, x24
	mov	x2, x21
	bl	_sme_transpose
	mov	w0, #512                        ; =0x200
LBB0_38:
	mov	x1, x21
	mov	x2, x26
	mov	x3, x25
	bl	_sme_gemm
	ldur	x8, [x29, #-96]
Lloh3:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh4:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh5:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB0_93
; %bb.39:
	mov	x0, x21
	ldp	x29, x30, [sp, #336]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #320]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #304]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #288]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #272]            ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #256]            ; 16-byte Folded Reload
	add	sp, sp, #352
	b	_free
LBB0_40:
	mov	x8, #0                          ; =0x0
	mov	w10, w22
	and	x11, x10, #0x7ffffffe
	add	x12, x24, #4
	lsl	x13, x10, #2
	lsl	x14, x10, #3
	and	x15, x10, #0xffffffff80000001
	ubfx	x17, x10, #1, #30
	umull	x16, w10, w17
	add	x16, x26, x16, lsl #3
	add	x17, x24, x17, lsl #3
	b	LBB0_43
LBB0_41:                                ;   in Loop: Header=BB0_43 Depth=1
	ldr	s0, [x24, x1, lsl #2]
	ldr	s1, [x26]
	fmul	s0, s1, s0
	str	s0, [x0]
LBB0_42:                                ;   in Loop: Header=BB0_43 Depth=1
	add	x8, x8, #1
	add	x12, x12, x13
	add	x17, x17, x13
	cmp	x8, x10
	b.eq	LBB0_91
LBB0_43:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_50 Depth 2
                                        ;       Child Loop BB0_51 Depth 3
                                        ;       Child Loop BB0_53 Depth 3
                                        ;     Child Loop BB0_46 Depth 2
                                        ;       Child Loop BB0_47 Depth 3
	mul	x1, x8, x10
	add	x0, x25, x1, lsl #2
	cmp	w22, #1
	b.eq	LBB0_41
; %bb.44:                               ;   in Loop: Header=BB0_43 Depth=1
	cmp	x10, x11
	b.ne	LBB0_49
; %bb.45:                               ;   in Loop: Header=BB0_43 Depth=1
	mov	x1, #0                          ; =0x0
	mov	x2, x26
LBB0_46:                                ;   Parent Loop BB0_43 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_47 Depth 3
	movi.2d	v0, #0000000000000000
	mov	x3, x12
	mov	x4, x11
	mov	x5, x2
	movi.2d	v1, #0000000000000000
LBB0_47:                                ;   Parent Loop BB0_43 Depth=1
                                        ;     Parent Loop BB0_46 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldp	s2, s3, [x3, #-4]
	ldr	s4, [x5, x13]
	ldr	s5, [x5]
	fmadd	s0, s5, s2, s0
	fmadd	s1, s4, s3, s1
	add	x5, x5, x14
	add	x3, x3, #8
	subs	x4, x4, #2
	b.ne	LBB0_47
; %bb.48:                               ;   in Loop: Header=BB0_46 Depth=2
	fadd	s0, s1, s0
	str	s0, [x0, x1, lsl #2]
	add	x1, x1, #1
	add	x2, x2, #4
	cmp	x1, x10
	b.ne	LBB0_46
	b	LBB0_42
LBB0_49:                                ;   in Loop: Header=BB0_43 Depth=1
	mov	x1, #0                          ; =0x0
	mov	x2, x16
	mov	x3, x26
LBB0_50:                                ;   Parent Loop BB0_43 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_51 Depth 3
                                        ;       Child Loop BB0_53 Depth 3
	movi.2d	v0, #0000000000000000
	mov	x4, x11
	mov	x5, x3
	mov	x6, x12
	movi.2d	v1, #0000000000000000
LBB0_51:                                ;   Parent Loop BB0_43 Depth=1
                                        ;     Parent Loop BB0_50 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldp	s2, s3, [x6, #-4]
	ldr	s4, [x5, x13]
	ldr	s5, [x5]
	fmadd	s0, s5, s2, s0
	fmadd	s1, s4, s3, s1
	add	x6, x6, #8
	add	x5, x5, x14
	subs	x4, x4, #2
	b.ne	LBB0_51
; %bb.52:                               ;   in Loop: Header=BB0_50 Depth=2
	fadd	s0, s1, s0
	mov	x4, x17
	mov	x5, x2
	mov	x6, x15
LBB0_53:                                ;   Parent Loop BB0_43 Depth=1
                                        ;     Parent Loop BB0_50 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldr	s1, [x4], #4
	ldr	s2, [x5]
	fmadd	s0, s2, s1, s0
	add	x5, x5, x13
	subs	x6, x6, #1
	b.ne	LBB0_53
; %bb.54:                               ;   in Loop: Header=BB0_50 Depth=2
	str	s0, [x0, x1, lsl #2]
	add	x1, x1, #1
	add	x3, x3, #4
	add	x2, x2, #4
	cmp	x1, x10
	b.ne	LBB0_50
	b	LBB0_42
LBB0_55:
	mov	x8, #0                          ; =0x0
	add	x9, x24, #4
LBB0_56:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_57 Depth 2
                                        ;       Child Loop BB0_58 Depth 3
	mov	x10, #0                         ; =0x0
	add	x11, x25, x8, lsl #11
	mov	x12, x26
LBB0_57:                                ;   Parent Loop BB0_56 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB0_58 Depth 3
	movi.2d	v0, #0000000000000000
	mov	w13, #512                       ; =0x200
	mov	x14, x12
	mov	x15, x9
	movi.2d	v1, #0000000000000000
LBB0_58:                                ;   Parent Loop BB0_56 Depth=1
                                        ;     Parent Loop BB0_57 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	ldp	s2, s3, [x15, #-4]
	ldr	s4, [x14]
	ldr	s5, [x14, #2048]
	fmadd	s0, s4, s2, s0
	fmadd	s1, s5, s3, s1
	add	x15, x15, #8
	add	x14, x14, #1, lsl #12           ; =4096
	subs	x13, x13, #2
	b.ne	LBB0_58
; %bb.59:                               ;   in Loop: Header=BB0_57 Depth=2
	fadd	s0, s1, s0
	str	s0, [x11, x10, lsl #2]
	add	x10, x10, #1
	add	x12, x12, #4
	cmp	x10, #512
	b.ne	LBB0_57
; %bb.60:                               ;   in Loop: Header=BB0_56 Depth=1
	add	x8, x8, #1
	add	x9, x9, #2048
	cmp	x8, #512
	b.ne	LBB0_56
	b	LBB0_91
LBB0_61:
	mov	x19, #0                         ; =0x0
LBB0_62:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x22, x19
	mov	x1, x26
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x26, x26, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_62
LBB0_63:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	str	x21, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	add	x9, x21, #16
	mov	x10, x27
	ldr	x26, [sp, #48]                  ; 8-byte Folded Reload
LBB0_64:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_65 Depth 2
	mov	x11, x10
	mov	x12, x9
	mov	w13, #256                       ; =0x100
LBB0_65:                                ;   Parent Loop BB0_64 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	add	x14, x11, #128, lsl #12         ; =524288
	ldp	q0, q1, [x12, #-16]
	ldp	q2, q3, [x11]
	fadd.4s	v2, v2, v0
	fadd.4s	v3, v3, v1
	stp	q2, q3, [x11], #32
	ldp	q2, q3, [x14]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	stp	q0, q1, [x14]
	add	x12, x12, #32
	subs	x13, x13, #8
	b.ne	LBB0_65
; %bb.66:                               ;   in Loop: Header=BB0_64 Depth=1
	add	x8, x8, #1
	add	x9, x9, #1024
	add	x10, x10, #2048
	cmp	x8, #256
	b.ne	LBB0_64
; %bb.67:
	mov	x8, #0                          ; =0x0
LBB0_68:                                ; =>This Inner Loop Header: Depth=1
	add	x9, x24, x8, lsl #11
	prfm	pldl1keep, [x9, #2048]
	ldp	q0, q1, [x9]
	ldp	q2, q3, [x9, #32]
	prfm	pldl1keep, [x9, #3072]
	ldr	q4, [x9, #1024]
	ldr	q5, [x9, #1040]
	ldr	q6, [x9, #1056]
	ldr	q7, [x9, #1072]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x10, x23, x8, lsl #10
	stp	q0, q1, [x10]
	stp	q2, q3, [x10, #32]
	prfm	pldl1keep, [x9, #2112]
	ldp	q0, q1, [x9, #64]
	ldp	q2, q3, [x9, #96]
	prfm	pldl1keep, [x9, #3136]
	ldr	q4, [x9, #1088]
	ldr	q5, [x9, #1104]
	ldr	q6, [x9, #1120]
	ldr	q7, [x9, #1136]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #64]
	stp	q2, q3, [x10, #96]
	prfm	pldl1keep, [x9, #2176]
	ldp	q0, q1, [x9, #128]
	ldp	q2, q3, [x9, #160]
	prfm	pldl1keep, [x9, #3200]
	ldr	q4, [x9, #1152]
	ldr	q5, [x9, #1168]
	ldr	q6, [x9, #1184]
	ldr	q7, [x9, #1200]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #128]
	stp	q2, q3, [x10, #160]
	prfm	pldl1keep, [x9, #2240]
	ldp	q0, q1, [x9, #192]
	ldp	q2, q3, [x9, #224]
	prfm	pldl1keep, [x9, #3264]
	ldr	q4, [x9, #1216]
	ldr	q5, [x9, #1232]
	ldr	q6, [x9, #1248]
	ldr	q7, [x9, #1264]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #192]
	stp	q2, q3, [x10, #224]
	prfm	pldl1keep, [x9, #2304]
	ldp	q0, q1, [x9, #256]
	ldp	q2, q3, [x9, #288]
	prfm	pldl1keep, [x9, #3328]
	ldr	q4, [x9, #1280]
	ldr	q5, [x9, #1296]
	ldr	q6, [x9, #1312]
	ldr	q7, [x9, #1328]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #256]
	stp	q2, q3, [x10, #288]
	prfm	pldl1keep, [x9, #2368]
	ldp	q0, q1, [x9, #320]
	ldp	q2, q3, [x9, #352]
	prfm	pldl1keep, [x9, #3392]
	ldr	q4, [x9, #1344]
	ldr	q5, [x9, #1360]
	ldr	q6, [x9, #1376]
	ldr	q7, [x9, #1392]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #320]
	stp	q2, q3, [x10, #352]
	prfm	pldl1keep, [x9, #2432]
	ldp	q0, q1, [x9, #384]
	ldp	q2, q3, [x9, #416]
	prfm	pldl1keep, [x9, #3456]
	ldr	q4, [x9, #1408]
	ldr	q5, [x9, #1424]
	ldr	q6, [x9, #1440]
	ldr	q7, [x9, #1456]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #384]
	stp	q2, q3, [x10, #416]
	prfm	pldl1keep, [x9, #2496]
	ldp	q0, q1, [x9, #448]
	ldp	q2, q3, [x9, #480]
	prfm	pldl1keep, [x9, #3520]
	ldr	q4, [x9, #1472]
	ldr	q5, [x9, #1488]
	ldr	q6, [x9, #1504]
	ldr	q7, [x9, #1520]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #448]
	stp	q2, q3, [x10, #480]
	prfm	pldl1keep, [x9, #2560]
	ldp	q0, q1, [x9, #512]
	ldp	q2, q3, [x9, #544]
	prfm	pldl1keep, [x9, #3584]
	ldr	q4, [x9, #1536]
	ldr	q5, [x9, #1552]
	ldr	q6, [x9, #1568]
	ldr	q7, [x9, #1584]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #512]
	stp	q2, q3, [x10, #544]
	prfm	pldl1keep, [x9, #2624]
	ldp	q0, q1, [x9, #576]
	ldp	q2, q3, [x9, #608]
	prfm	pldl1keep, [x9, #3648]
	ldr	q4, [x9, #1600]
	ldr	q5, [x9, #1616]
	ldr	q6, [x9, #1632]
	ldr	q7, [x9, #1648]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #576]
	stp	q2, q3, [x10, #608]
	prfm	pldl1keep, [x9, #2688]
	ldp	q0, q1, [x9, #640]
	ldp	q2, q3, [x9, #672]
	prfm	pldl1keep, [x9, #3712]
	ldr	q4, [x9, #1664]
	ldr	q5, [x9, #1680]
	ldr	q6, [x9, #1696]
	ldr	q7, [x9, #1712]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #640]
	stp	q2, q3, [x10, #672]
	prfm	pldl1keep, [x9, #2752]
	ldp	q0, q1, [x9, #704]
	ldp	q2, q3, [x9, #736]
	prfm	pldl1keep, [x9, #3776]
	ldr	q4, [x9, #1728]
	ldr	q5, [x9, #1744]
	ldr	q6, [x9, #1760]
	ldr	q7, [x9, #1776]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #704]
	stp	q2, q3, [x10, #736]
	prfm	pldl1keep, [x9, #2816]
	ldp	q0, q1, [x9, #768]
	ldp	q2, q3, [x9, #800]
	prfm	pldl1keep, [x9, #3840]
	ldr	q4, [x9, #1792]
	ldr	q5, [x9, #1808]
	ldr	q6, [x9, #1824]
	ldr	q7, [x9, #1840]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #768]
	stp	q2, q3, [x10, #800]
	prfm	pldl1keep, [x9, #2880]
	ldp	q0, q1, [x9, #832]
	ldp	q2, q3, [x9, #864]
	prfm	pldl1keep, [x9, #3904]
	ldr	q4, [x9, #1856]
	ldr	q5, [x9, #1872]
	ldr	q6, [x9, #1888]
	ldr	q7, [x9, #1904]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #832]
	stp	q2, q3, [x10, #864]
	prfm	pldl1keep, [x9, #2944]
	ldp	q0, q1, [x9, #896]
	ldp	q2, q3, [x9, #928]
	prfm	pldl1keep, [x9, #3968]
	ldr	q4, [x9, #1920]
	ldr	q5, [x9, #1936]
	ldr	q6, [x9, #1952]
	ldr	q7, [x9, #1968]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #896]
	stp	q2, q3, [x10, #928]
	prfm	pldl1keep, [x9, #3008]
	ldp	q0, q1, [x9, #960]
	ldp	q2, q3, [x9, #992]
	prfm	pldl1keep, [x9, #4032]
	ldr	q4, [x9, #1984]
	ldr	q5, [x9, #2000]
	ldr	q6, [x9, #2016]
	ldr	q7, [x9, #2032]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #960]
	stp	q2, q3, [x10, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_68
; %bb.69:
	mov	x19, #0                         ; =0x0
LBB0_70:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x22, x19
	mov	x1, x26
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x26, x26, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_70
; %bb.71:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	str	x21, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	add	x9, x21, #16
	mov	x10, x27
LBB0_72:                                ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB0_73 Depth 2
	mov	x11, x10
	mov	x12, x9
	mov	w13, #256                       ; =0x100
LBB0_73:                                ;   Parent Loop BB0_72 Depth=1
                                        ; =>  This Inner Loop Header: Depth=2
	ldp	q0, q1, [x12, #-16]
	ldp	q2, q3, [x11]
	fsub.4s	v2, v2, v0
	fsub.4s	v3, v3, v1
	stp	q2, q3, [x11]
	ldr	q2, [x11, #1024]
	ldr	q3, [x11, #1040]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	str	q0, [x11, #1024]
	str	q1, [x11, #1040]
	add	x12, x12, #32
	add	x11, x11, #32
	subs	x13, x13, #8
	b.ne	LBB0_73
; %bb.74:                               ;   in Loop: Header=BB0_72 Depth=1
	add	x8, x8, #1
	add	x9, x9, #1024
	add	x10, x10, #2048
	cmp	x8, #256
	b.ne	LBB0_72
; %bb.75:
	cbz	x24, LBB0_78
; %bb.76:
	mov	x8, #0                          ; =0x0
	mov	w9, #2048                       ; =0x800
	movk	w9, #8, lsl #16
	mov	w10, #2112                      ; =0x840
	movk	w10, #8, lsl #16
	mov	w11, #2176                      ; =0x880
	movk	w11, #8, lsl #16
	mov	w12, #2240                      ; =0x8c0
	movk	w12, #8, lsl #16
	mov	w13, #2304                      ; =0x900
	movk	w13, #8, lsl #16
	mov	w14, #2368                      ; =0x940
	movk	w14, #8, lsl #16
	mov	w15, #2432                      ; =0x980
	movk	w15, #8, lsl #16
	mov	w16, #2496                      ; =0x9c0
	movk	w16, #8, lsl #16
	mov	w17, #2560                      ; =0xa00
	movk	w17, #8, lsl #16
	mov	w0, #2624                       ; =0xa40
	movk	w0, #8, lsl #16
	mov	w1, #2688                       ; =0xa80
	movk	w1, #8, lsl #16
	mov	w2, #2752                       ; =0xac0
	movk	w2, #8, lsl #16
	mov	w3, #2816                       ; =0xb00
	movk	w3, #8, lsl #16
	mov	w4, #2880                       ; =0xb40
	movk	w4, #8, lsl #16
	mov	w5, #2944                       ; =0xb80
	movk	w5, #8, lsl #16
	mov	w6, #3008                       ; =0xbc0
	movk	w6, #8, lsl #16
LBB0_77:                                ; =>This Inner Loop Header: Depth=1
	lsl	x19, x8, #11
	add	x7, x24, x19
	add	x19, x25, x19
	prfm	pldl1keep, [x7, x9]
	ldp	q0, q1, [x19]
	ldp	q2, q3, [x19, #32]
	prfm	pldl1keep, [x7, #2048]
	ldp	q4, q5, [x7]
	ldp	q6, q7, [x7, #32]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	add	x20, x23, x8, lsl #10
	stp	q0, q1, [x20]
	stp	q2, q3, [x20, #32]
	prfm	pldl1keep, [x7, x10]
	ldp	q0, q1, [x19, #64]
	ldp	q2, q3, [x19, #96]
	prfm	pldl1keep, [x7, #2112]
	ldp	q4, q5, [x7, #64]
	ldp	q6, q7, [x7, #96]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #64]
	stp	q2, q3, [x20, #96]
	prfm	pldl1keep, [x7, x11]
	ldp	q0, q1, [x19, #128]
	ldp	q2, q3, [x19, #160]
	prfm	pldl1keep, [x7, #2176]
	ldp	q4, q5, [x7, #128]
	ldp	q6, q7, [x7, #160]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #128]
	stp	q2, q3, [x20, #160]
	prfm	pldl1keep, [x7, x12]
	ldp	q0, q1, [x19, #192]
	ldp	q2, q3, [x19, #224]
	prfm	pldl1keep, [x7, #2240]
	ldp	q4, q5, [x7, #192]
	ldp	q6, q7, [x7, #224]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #192]
	stp	q2, q3, [x20, #224]
	prfm	pldl1keep, [x7, x13]
	ldp	q0, q1, [x19, #256]
	ldp	q2, q3, [x19, #288]
	prfm	pldl1keep, [x7, #2304]
	ldp	q4, q5, [x7, #256]
	ldp	q6, q7, [x7, #288]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #256]
	stp	q2, q3, [x20, #288]
	prfm	pldl1keep, [x7, x14]
	ldp	q0, q1, [x19, #320]
	ldp	q2, q3, [x19, #352]
	prfm	pldl1keep, [x7, #2368]
	ldp	q4, q5, [x7, #320]
	ldp	q6, q7, [x7, #352]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #320]
	stp	q2, q3, [x20, #352]
	prfm	pldl1keep, [x7, x15]
	ldp	q0, q1, [x19, #384]
	ldp	q2, q3, [x19, #416]
	prfm	pldl1keep, [x7, #2432]
	ldp	q4, q5, [x7, #384]
	ldp	q6, q7, [x7, #416]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #384]
	stp	q2, q3, [x20, #416]
	prfm	pldl1keep, [x7, x16]
	ldp	q0, q1, [x19, #448]
	ldp	q2, q3, [x19, #480]
	prfm	pldl1keep, [x7, #2496]
	ldp	q4, q5, [x7, #448]
	ldp	q6, q7, [x7, #480]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #448]
	stp	q2, q3, [x20, #480]
	prfm	pldl1keep, [x7, x17]
	ldp	q0, q1, [x19, #512]
	ldp	q2, q3, [x19, #544]
	prfm	pldl1keep, [x7, #2560]
	ldp	q4, q5, [x7, #512]
	ldp	q6, q7, [x7, #544]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #512]
	stp	q2, q3, [x20, #544]
	prfm	pldl1keep, [x7, x0]
	ldp	q0, q1, [x19, #576]
	ldp	q2, q3, [x19, #608]
	prfm	pldl1keep, [x7, #2624]
	ldp	q4, q5, [x7, #576]
	ldp	q6, q7, [x7, #608]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #576]
	stp	q2, q3, [x20, #608]
	prfm	pldl1keep, [x7, x1]
	ldp	q0, q1, [x19, #640]
	ldp	q2, q3, [x19, #672]
	prfm	pldl1keep, [x7, #2688]
	ldp	q4, q5, [x7, #640]
	ldp	q6, q7, [x7, #672]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #640]
	stp	q2, q3, [x20, #672]
	prfm	pldl1keep, [x7, x2]
	ldp	q0, q1, [x19, #704]
	ldp	q2, q3, [x19, #736]
	prfm	pldl1keep, [x7, #2752]
	ldp	q4, q5, [x7, #704]
	ldp	q6, q7, [x7, #736]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #704]
	stp	q2, q3, [x20, #736]
	prfm	pldl1keep, [x7, x3]
	ldp	q0, q1, [x19, #768]
	ldp	q2, q3, [x19, #800]
	prfm	pldl1keep, [x7, #2816]
	ldp	q4, q5, [x7, #768]
	ldp	q6, q7, [x7, #800]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #768]
	stp	q2, q3, [x20, #800]
	prfm	pldl1keep, [x7, x4]
	ldp	q0, q1, [x19, #832]
	ldp	q2, q3, [x19, #864]
	prfm	pldl1keep, [x7, #2880]
	ldp	q4, q5, [x7, #832]
	ldp	q6, q7, [x7, #864]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #832]
	stp	q2, q3, [x20, #864]
	prfm	pldl1keep, [x7, x5]
	ldp	q0, q1, [x19, #896]
	ldp	q2, q3, [x19, #928]
	prfm	pldl1keep, [x7, #2944]
	ldp	q4, q5, [x7, #896]
	ldp	q6, q7, [x7, #928]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #896]
	stp	q2, q3, [x20, #928]
	prfm	pldl1keep, [x7, x6]
	ldp	q0, q1, [x19, #960]
	ldp	q2, q3, [x19, #992]
	prfm	pldl1keep, [x7, #3008]
	ldp	q4, q5, [x7, #960]
	ldp	q6, q7, [x7, #992]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x20, #960]
	stp	q2, q3, [x20, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_77
	b	LBB0_80
LBB0_78:
	mov	x19, #0                         ; =0x0
LBB0_79:                                ; =>This Inner Loop Header: Depth=1
	add	x0, x23, x19
	mov	x1, x25
	mov	w2, #1024                       ; =0x400
	bl	_memcpy
	add	x19, x19, #1024
	add	x25, x25, #2048
	cmp	x19, #64, lsl #12               ; =262144
	b.ne	LBB0_79
LBB0_80:
	mov	x8, #0                          ; =0x0
LBB0_81:                                ; =>This Inner Loop Header: Depth=1
	add	x9, x28, x8, lsl #11
	prfm	pldl1keep, [x9, #2048]
	ldp	q0, q1, [x9]
	ldp	q2, q3, [x9, #32]
	prfm	pldl1keep, [x9, #3072]
	ldr	q4, [x9, #1024]
	ldr	q5, [x9, #1040]
	ldr	q6, [x9, #1056]
	ldr	q7, [x9, #1072]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x10, x22, x8, lsl #10
	stp	q0, q1, [x10]
	stp	q2, q3, [x10, #32]
	prfm	pldl1keep, [x9, #2112]
	ldp	q0, q1, [x9, #64]
	ldp	q2, q3, [x9, #96]
	prfm	pldl1keep, [x9, #3136]
	ldr	q4, [x9, #1088]
	ldr	q5, [x9, #1104]
	ldr	q6, [x9, #1120]
	ldr	q7, [x9, #1136]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #64]
	stp	q2, q3, [x10, #96]
	prfm	pldl1keep, [x9, #2176]
	ldp	q0, q1, [x9, #128]
	ldp	q2, q3, [x9, #160]
	prfm	pldl1keep, [x9, #3200]
	ldr	q4, [x9, #1152]
	ldr	q5, [x9, #1168]
	ldr	q6, [x9, #1184]
	ldr	q7, [x9, #1200]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #128]
	stp	q2, q3, [x10, #160]
	prfm	pldl1keep, [x9, #2240]
	ldp	q0, q1, [x9, #192]
	ldp	q2, q3, [x9, #224]
	prfm	pldl1keep, [x9, #3264]
	ldr	q4, [x9, #1216]
	ldr	q5, [x9, #1232]
	ldr	q6, [x9, #1248]
	ldr	q7, [x9, #1264]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #192]
	stp	q2, q3, [x10, #224]
	prfm	pldl1keep, [x9, #2304]
	ldp	q0, q1, [x9, #256]
	ldp	q2, q3, [x9, #288]
	prfm	pldl1keep, [x9, #3328]
	ldr	q4, [x9, #1280]
	ldr	q5, [x9, #1296]
	ldr	q6, [x9, #1312]
	ldr	q7, [x9, #1328]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #256]
	stp	q2, q3, [x10, #288]
	prfm	pldl1keep, [x9, #2368]
	ldp	q0, q1, [x9, #320]
	ldp	q2, q3, [x9, #352]
	prfm	pldl1keep, [x9, #3392]
	ldr	q4, [x9, #1344]
	ldr	q5, [x9, #1360]
	ldr	q6, [x9, #1376]
	ldr	q7, [x9, #1392]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #320]
	stp	q2, q3, [x10, #352]
	prfm	pldl1keep, [x9, #2432]
	ldp	q0, q1, [x9, #384]
	ldp	q2, q3, [x9, #416]
	prfm	pldl1keep, [x9, #3456]
	ldr	q4, [x9, #1408]
	ldr	q5, [x9, #1424]
	ldr	q6, [x9, #1440]
	ldr	q7, [x9, #1456]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #384]
	stp	q2, q3, [x10, #416]
	prfm	pldl1keep, [x9, #2496]
	ldp	q0, q1, [x9, #448]
	ldp	q2, q3, [x9, #480]
	prfm	pldl1keep, [x9, #3520]
	ldr	q4, [x9, #1472]
	ldr	q5, [x9, #1488]
	ldr	q6, [x9, #1504]
	ldr	q7, [x9, #1520]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #448]
	stp	q2, q3, [x10, #480]
	prfm	pldl1keep, [x9, #2560]
	ldp	q0, q1, [x9, #512]
	ldp	q2, q3, [x9, #544]
	prfm	pldl1keep, [x9, #3584]
	ldr	q4, [x9, #1536]
	ldr	q5, [x9, #1552]
	ldr	q6, [x9, #1568]
	ldr	q7, [x9, #1584]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #512]
	stp	q2, q3, [x10, #544]
	prfm	pldl1keep, [x9, #2624]
	ldp	q0, q1, [x9, #576]
	ldp	q2, q3, [x9, #608]
	prfm	pldl1keep, [x9, #3648]
	ldr	q4, [x9, #1600]
	ldr	q5, [x9, #1616]
	ldr	q6, [x9, #1632]
	ldr	q7, [x9, #1648]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #576]
	stp	q2, q3, [x10, #608]
	prfm	pldl1keep, [x9, #2688]
	ldp	q0, q1, [x9, #640]
	ldp	q2, q3, [x9, #672]
	prfm	pldl1keep, [x9, #3712]
	ldr	q4, [x9, #1664]
	ldr	q5, [x9, #1680]
	ldr	q6, [x9, #1696]
	ldr	q7, [x9, #1712]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #640]
	stp	q2, q3, [x10, #672]
	prfm	pldl1keep, [x9, #2752]
	ldp	q0, q1, [x9, #704]
	ldp	q2, q3, [x9, #736]
	prfm	pldl1keep, [x9, #3776]
	ldr	q4, [x9, #1728]
	ldr	q5, [x9, #1744]
	ldr	q6, [x9, #1760]
	ldr	q7, [x9, #1776]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #704]
	stp	q2, q3, [x10, #736]
	prfm	pldl1keep, [x9, #2816]
	ldp	q0, q1, [x9, #768]
	ldp	q2, q3, [x9, #800]
	prfm	pldl1keep, [x9, #3840]
	ldr	q4, [x9, #1792]
	ldr	q5, [x9, #1808]
	ldr	q6, [x9, #1824]
	ldr	q7, [x9, #1840]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #768]
	stp	q2, q3, [x10, #800]
	prfm	pldl1keep, [x9, #2880]
	ldp	q0, q1, [x9, #832]
	ldp	q2, q3, [x9, #864]
	prfm	pldl1keep, [x9, #3904]
	ldr	q4, [x9, #1856]
	ldr	q5, [x9, #1872]
	ldr	q6, [x9, #1888]
	ldr	q7, [x9, #1904]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #832]
	stp	q2, q3, [x10, #864]
	prfm	pldl1keep, [x9, #2944]
	ldp	q0, q1, [x9, #896]
	ldp	q2, q3, [x9, #928]
	prfm	pldl1keep, [x9, #3968]
	ldr	q4, [x9, #1920]
	ldr	q5, [x9, #1936]
	ldr	q6, [x9, #1952]
	ldr	q7, [x9, #1968]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #896]
	stp	q2, q3, [x10, #928]
	prfm	pldl1keep, [x9, #3008]
	ldp	q0, q1, [x9, #960]
	ldp	q2, q3, [x9, #992]
	prfm	pldl1keep, [x9, #4032]
	ldr	q4, [x9, #1984]
	ldr	q5, [x9, #2000]
	ldr	q6, [x9, #2016]
	ldr	q7, [x9, #2032]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x10, #960]
	stp	q2, q3, [x10, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_81
; %bb.82:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	str	x21, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	mov	w9, #3072                       ; =0xc00
	movk	w9, #8, lsl #16
	mov	w10, #3136                      ; =0xc40
	movk	w10, #8, lsl #16
	mov	w11, #3200                      ; =0xc80
	movk	w11, #8, lsl #16
	mov	w12, #3264                      ; =0xcc0
	movk	w12, #8, lsl #16
	mov	w13, #3328                      ; =0xd00
	movk	w13, #8, lsl #16
	mov	w14, #3392                      ; =0xd40
	movk	w14, #8, lsl #16
	mov	w15, #3456                      ; =0xd80
	movk	w15, #8, lsl #16
	mov	w16, #3520                      ; =0xdc0
	movk	w16, #8, lsl #16
	mov	w17, #3584                      ; =0xe00
	movk	w17, #8, lsl #16
	mov	w0, #3648                       ; =0xe40
	movk	w0, #8, lsl #16
	mov	w1, #3712                       ; =0xe80
	movk	w1, #8, lsl #16
	mov	w2, #3776                       ; =0xec0
	movk	w2, #8, lsl #16
	mov	w3, #3840                       ; =0xf00
	movk	w3, #8, lsl #16
	mov	w4, #3904                       ; =0xf40
	movk	w4, #8, lsl #16
	mov	w5, #3968                       ; =0xf80
	movk	w5, #8, lsl #16
	mov	w6, #4032                       ; =0xfc0
	movk	w6, #8, lsl #16
	ldr	x25, [sp, #8]                   ; 8-byte Folded Reload
LBB0_83:                                ; =>This Inner Loop Header: Depth=1
	lsl	x7, x8, #11
	add	x19, x27, x7
	add	x7, x25, x7
	add	x20, x21, x8, lsl #10
	ldp	q0, q1, [x20]
	ldp	q2, q3, [x20, #32]
	prfm	pldl1keep, [x19, x9]
	ldp	q4, q5, [x7]
	ldp	q6, q7, [x7, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7]
	stp	q2, q3, [x7, #32]
	ldp	q0, q1, [x20, #64]
	ldp	q2, q3, [x20, #96]
	prfm	pldl1keep, [x19, x10]
	ldp	q4, q5, [x7, #64]
	ldp	q6, q7, [x7, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #64]
	stp	q2, q3, [x7, #96]
	ldp	q0, q1, [x20, #128]
	ldp	q2, q3, [x20, #160]
	prfm	pldl1keep, [x19, x11]
	ldp	q4, q5, [x7, #128]
	ldp	q6, q7, [x7, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #128]
	ldp	q0, q1, [x20, #192]
	stp	q2, q3, [x7, #160]
	ldp	q2, q3, [x20, #224]
	prfm	pldl1keep, [x19, x12]
	ldp	q4, q5, [x7, #192]
	ldp	q6, q7, [x7, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #192]
	ldp	q0, q1, [x20, #256]
	stp	q2, q3, [x7, #224]
	ldp	q2, q3, [x20, #288]
	prfm	pldl1keep, [x19, x13]
	ldp	q4, q5, [x7, #256]
	ldp	q6, q7, [x7, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #256]
	ldp	q0, q1, [x20, #320]
	stp	q2, q3, [x7, #288]
	ldp	q4, q2, [x20, #352]
	prfm	pldl1keep, [x19, x14]
	ldp	q3, q5, [x7, #320]
	ldp	q6, q7, [x7, #352]
	fadd.4s	v0, v3, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v3, v6, v4
	fadd.4s	v2, v7, v2
	stp	q0, q1, [x7, #320]
	ldp	q0, q1, [x20, #384]
	ldp	q4, q5, [x20, #416]
	stp	q3, q2, [x7, #352]
	prfm	pldl1keep, [x19, x15]
	ldp	q2, q3, [x7, #384]
	ldp	q6, q7, [x7, #416]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	fadd.4s	v2, v6, v4
	fadd.4s	v3, v7, v5
	stp	q0, q1, [x7, #384]
	stp	q2, q3, [x7, #416]
	ldp	q0, q1, [x20, #448]
	ldp	q2, q3, [x20, #480]
	prfm	pldl1keep, [x19, x16]
	ldp	q4, q5, [x7, #448]
	ldp	q6, q7, [x7, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #448]
	stp	q2, q3, [x7, #480]
	ldp	q0, q1, [x20, #512]
	ldp	q2, q3, [x20, #544]
	prfm	pldl1keep, [x19, x17]
	ldp	q4, q5, [x7, #512]
	ldp	q6, q7, [x7, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #512]
	ldp	q0, q1, [x20, #576]
	stp	q2, q3, [x7, #544]
	ldp	q2, q3, [x20, #608]
	prfm	pldl1keep, [x19, x0]
	ldp	q4, q5, [x7, #576]
	ldp	q6, q7, [x7, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #576]
	ldp	q0, q1, [x20, #640]
	stp	q2, q3, [x7, #608]
	ldp	q2, q3, [x20, #672]
	prfm	pldl1keep, [x19, x1]
	ldp	q4, q5, [x7, #640]
	ldp	q6, q7, [x7, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #640]
	ldp	q0, q1, [x20, #704]
	stp	q2, q3, [x7, #672]
	ldp	q4, q2, [x20, #736]
	prfm	pldl1keep, [x19, x2]
	ldp	q3, q5, [x7, #704]
	ldp	q6, q7, [x7, #736]
	fadd.4s	v0, v3, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v3, v6, v4
	fadd.4s	v2, v7, v2
	stp	q0, q1, [x7, #704]
	ldp	q0, q1, [x20, #768]
	ldp	q4, q5, [x20, #800]
	stp	q3, q2, [x7, #736]
	prfm	pldl1keep, [x19, x3]
	ldp	q2, q3, [x7, #768]
	ldp	q6, q7, [x7, #800]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	fadd.4s	v2, v6, v4
	fadd.4s	v3, v7, v5
	stp	q0, q1, [x7, #768]
	stp	q2, q3, [x7, #800]
	ldp	q0, q1, [x20, #832]
	ldp	q2, q3, [x20, #864]
	prfm	pldl1keep, [x19, x4]
	ldp	q4, q5, [x7, #832]
	ldp	q6, q7, [x7, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #832]
	stp	q2, q3, [x7, #864]
	ldp	q0, q1, [x20, #896]
	ldp	q2, q3, [x20, #928]
	prfm	pldl1keep, [x19, x5]
	ldp	q4, q5, [x7, #896]
	ldp	q6, q7, [x7, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #896]
	ldp	q0, q1, [x20, #960]
	stp	q2, q3, [x7, #928]
	ldp	q2, q3, [x20, #992]
	prfm	pldl1keep, [x19, x6]
	ldp	q4, q5, [x7, #960]
	ldp	q6, q7, [x7, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x7, #960]
	stp	q2, q3, [x7, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_83
; %bb.84:
	mov	x8, #0                          ; =0x0
	add	x9, x24, #1024
	mov	w10, #3072                      ; =0xc00
	movk	w10, #8, lsl #16
	mov	w11, #3136                      ; =0xc40
	movk	w11, #8, lsl #16
	mov	w12, #3200                      ; =0xc80
	movk	w12, #8, lsl #16
	mov	w13, #3264                      ; =0xcc0
	movk	w13, #8, lsl #16
	mov	w14, #3328                      ; =0xd00
	movk	w14, #8, lsl #16
	mov	w15, #3392                      ; =0xd40
	movk	w15, #8, lsl #16
	mov	w16, #3456                      ; =0xd80
	movk	w16, #8, lsl #16
	mov	w17, #3520                      ; =0xdc0
	movk	w17, #8, lsl #16
	mov	w0, #3584                       ; =0xe00
	movk	w0, #8, lsl #16
	mov	w1, #3648                       ; =0xe40
	movk	w1, #8, lsl #16
	mov	w2, #3712                       ; =0xe80
	movk	w2, #8, lsl #16
	mov	w3, #3776                       ; =0xec0
	movk	w3, #8, lsl #16
	mov	w4, #3840                       ; =0xf00
	movk	w4, #8, lsl #16
	mov	w5, #3904                       ; =0xf40
	movk	w5, #8, lsl #16
	mov	w6, #3968                       ; =0xf80
	movk	w6, #8, lsl #16
	mov	w7, #4032                       ; =0xfc0
	movk	w7, #8, lsl #16
	ldr	x26, [sp, #24]                  ; 8-byte Folded Reload
LBB0_85:                                ; =>This Inner Loop Header: Depth=1
	lsl	x21, x8, #11
	add	x20, x24, x21
	add	x19, x26, x21
	add	x21, x9, x21
	prfm	pldl1keep, [x20, #3072]
	ldp	q0, q1, [x21]
	ldp	q2, q3, [x21, #32]
	prfm	pldl1keep, [x20, x10]
	ldp	q4, q5, [x19]
	ldp	q6, q7, [x19, #32]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	add	x25, x23, x8, lsl #10
	stp	q0, q1, [x25]
	stp	q2, q3, [x25, #32]
	prfm	pldl1keep, [x20, #3136]
	ldp	q0, q1, [x21, #64]
	ldp	q2, q3, [x21, #96]
	prfm	pldl1keep, [x20, x11]
	ldp	q4, q5, [x19, #64]
	ldp	q6, q7, [x19, #96]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #64]
	stp	q2, q3, [x25, #96]
	prfm	pldl1keep, [x20, #3200]
	ldp	q0, q1, [x21, #128]
	ldp	q2, q3, [x21, #160]
	prfm	pldl1keep, [x20, x12]
	ldp	q4, q5, [x19, #128]
	ldp	q6, q7, [x19, #160]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #128]
	stp	q2, q3, [x25, #160]
	prfm	pldl1keep, [x20, #3264]
	ldp	q0, q1, [x21, #192]
	ldp	q2, q3, [x21, #224]
	prfm	pldl1keep, [x20, x13]
	ldp	q4, q5, [x19, #192]
	ldp	q6, q7, [x19, #224]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #192]
	stp	q2, q3, [x25, #224]
	prfm	pldl1keep, [x20, #3328]
	ldp	q0, q1, [x21, #256]
	ldp	q2, q3, [x21, #288]
	prfm	pldl1keep, [x20, x14]
	ldp	q4, q5, [x19, #256]
	ldp	q6, q7, [x19, #288]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #256]
	stp	q2, q3, [x25, #288]
	prfm	pldl1keep, [x20, #3392]
	ldp	q0, q1, [x21, #320]
	ldp	q2, q3, [x21, #352]
	prfm	pldl1keep, [x20, x15]
	ldp	q4, q5, [x19, #320]
	ldp	q6, q7, [x19, #352]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #320]
	stp	q2, q3, [x25, #352]
	prfm	pldl1keep, [x20, #3456]
	ldp	q0, q1, [x21, #384]
	ldp	q2, q3, [x21, #416]
	prfm	pldl1keep, [x20, x16]
	ldp	q4, q5, [x19, #384]
	ldp	q6, q7, [x19, #416]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #384]
	stp	q2, q3, [x25, #416]
	prfm	pldl1keep, [x20, #3520]
	ldp	q0, q1, [x21, #448]
	ldp	q2, q3, [x21, #480]
	prfm	pldl1keep, [x20, x17]
	ldp	q4, q5, [x19, #448]
	ldp	q6, q7, [x19, #480]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #448]
	stp	q2, q3, [x25, #480]
	prfm	pldl1keep, [x20, #3584]
	ldp	q0, q1, [x21, #512]
	ldp	q2, q3, [x21, #544]
	prfm	pldl1keep, [x20, x0]
	ldp	q4, q5, [x19, #512]
	ldp	q6, q7, [x19, #544]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #512]
	stp	q2, q3, [x25, #544]
	prfm	pldl1keep, [x20, #3648]
	ldp	q0, q1, [x21, #576]
	ldp	q2, q3, [x21, #608]
	prfm	pldl1keep, [x20, x1]
	ldp	q4, q5, [x19, #576]
	ldp	q6, q7, [x19, #608]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #576]
	stp	q2, q3, [x25, #608]
	prfm	pldl1keep, [x20, #3712]
	ldp	q0, q1, [x21, #640]
	ldp	q2, q3, [x21, #672]
	prfm	pldl1keep, [x20, x2]
	ldp	q4, q5, [x19, #640]
	ldp	q6, q7, [x19, #672]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #640]
	stp	q2, q3, [x25, #672]
	prfm	pldl1keep, [x20, #3776]
	ldp	q0, q1, [x21, #704]
	ldp	q2, q3, [x21, #736]
	prfm	pldl1keep, [x20, x3]
	ldp	q4, q5, [x19, #704]
	ldp	q6, q7, [x19, #736]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #704]
	stp	q2, q3, [x25, #736]
	prfm	pldl1keep, [x20, #3840]
	ldp	q0, q1, [x21, #768]
	ldp	q2, q3, [x21, #800]
	prfm	pldl1keep, [x20, x4]
	ldp	q4, q5, [x19, #768]
	ldp	q6, q7, [x19, #800]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #768]
	stp	q2, q3, [x25, #800]
	prfm	pldl1keep, [x20, #3904]
	ldp	q0, q1, [x21, #832]
	ldp	q2, q3, [x21, #864]
	prfm	pldl1keep, [x20, x5]
	ldp	q4, q5, [x19, #832]
	ldp	q6, q7, [x19, #864]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #832]
	stp	q2, q3, [x25, #864]
	prfm	pldl1keep, [x20, #3968]
	ldp	q0, q1, [x21, #896]
	ldp	q2, q3, [x21, #928]
	prfm	pldl1keep, [x20, x6]
	ldp	q4, q5, [x19, #896]
	ldp	q6, q7, [x19, #928]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #896]
	stp	q2, q3, [x25, #928]
	prfm	pldl1keep, [x20, #4032]
	ldp	q0, q1, [x21, #960]
	ldp	q2, q3, [x21, #992]
	prfm	pldl1keep, [x20, x7]
	ldp	q4, q5, [x19, #960]
	ldp	q6, q7, [x19, #992]
	fsub.4s	v0, v0, v4
	fsub.4s	v1, v1, v5
	fsub.4s	v2, v2, v6
	fsub.4s	v3, v3, v7
	stp	q0, q1, [x25, #960]
	stp	q2, q3, [x25, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_85
; %bb.86:
	mov	x8, #0                          ; =0x0
	mov	w5, #2496                       ; =0x9c0
	movk	w5, #8, lsl #16
	mov	w6, #3520                       ; =0xdc0
	movk	w6, #8, lsl #16
	mov	w7, #2560                       ; =0xa00
	movk	w7, #8, lsl #16
	mov	w24, #3584                      ; =0xe00
	movk	w24, #8, lsl #16
	mov	w25, #2624                      ; =0xa40
	movk	w25, #8, lsl #16
	mov	w26, #3648                      ; =0xe40
	movk	w26, #8, lsl #16
	mov	w19, #2688                      ; =0xa80
	movk	w19, #8, lsl #16
	mov	w28, #3712                      ; =0xe80
	movk	w28, #8, lsl #16
	mov	w27, #2752                      ; =0xac0
	movk	w27, #8, lsl #16
	mov	w20, #3776                      ; =0xec0
	movk	w20, #8, lsl #16
	mov	w30, #2816                      ; =0xb00
	movk	w30, #8, lsl #16
	mov	w21, #3840                      ; =0xf00
	movk	w21, #8, lsl #16
	mov	w9, #2880                       ; =0xb40
	movk	w9, #8, lsl #16
	mov	w10, #3904                      ; =0xf40
	movk	w10, #8, lsl #16
	mov	w11, #2944                      ; =0xb80
	movk	w11, #8, lsl #16
	mov	w12, #3968                      ; =0xf80
	movk	w12, #8, lsl #16
	mov	w13, #3008                      ; =0xbc0
	movk	w13, #8, lsl #16
	mov	w14, #4032                      ; =0xfc0
	movk	w14, #8, lsl #16
	ldr	x1, [sp, #32]                   ; 8-byte Folded Reload
	ldr	x2, [sp, #48]                   ; 8-byte Folded Reload
	ldr	x3, [sp, #16]                   ; 8-byte Folded Reload
LBB0_87:                                ; =>This Inner Loop Header: Depth=1
	lsl	x17, x8, #11
	add	x16, x1, x17
	add	x15, x2, x17
	add	x17, x3, x17
	mov	w0, #2048                       ; =0x800
	movk	w0, #8, lsl #16
	prfm	pldl1keep, [x16, x0]
	ldp	q0, q1, [x17]
	ldp	q2, q3, [x17, #32]
	mov	w0, #3072                       ; =0xc00
	movk	w0, #8, lsl #16
	prfm	pldl1keep, [x16, x0]
	ldp	q4, q5, [x15]
	ldp	q6, q7, [x15, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	add	x0, x22, x8, lsl #10
	stp	q0, q1, [x0]
	stp	q2, q3, [x0, #32]
	mov	w4, #2112                       ; =0x840
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #64]
	ldp	q2, q3, [x17, #96]
	mov	w4, #3136                       ; =0xc40
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #64]
	ldp	q6, q7, [x15, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #64]
	stp	q2, q3, [x0, #96]
	mov	w4, #2176                       ; =0x880
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #128]
	ldp	q2, q3, [x17, #160]
	mov	w4, #3200                       ; =0xc80
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #128]
	ldp	q6, q7, [x15, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #128]
	stp	q2, q3, [x0, #160]
	mov	w4, #2240                       ; =0x8c0
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #192]
	ldp	q2, q3, [x17, #224]
	mov	w4, #3264                       ; =0xcc0
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #192]
	ldp	q6, q7, [x15, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #192]
	stp	q2, q3, [x0, #224]
	mov	w4, #2304                       ; =0x900
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #256]
	ldp	q2, q3, [x17, #288]
	mov	w4, #3328                       ; =0xd00
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #256]
	ldp	q6, q7, [x15, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #256]
	stp	q2, q3, [x0, #288]
	mov	w4, #2368                       ; =0x940
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #320]
	ldp	q2, q3, [x17, #352]
	mov	w4, #3392                       ; =0xd40
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #320]
	ldp	q6, q7, [x15, #352]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #320]
	stp	q2, q3, [x0, #352]
	mov	w4, #2432                       ; =0x980
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q0, q1, [x17, #384]
	ldp	q2, q3, [x17, #416]
	mov	w4, #3456                       ; =0xd80
	movk	w4, #8, lsl #16
	prfm	pldl1keep, [x16, x4]
	ldp	q4, q5, [x15, #384]
	ldp	q6, q7, [x15, #416]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #384]
	stp	q2, q3, [x0, #416]
	prfm	pldl1keep, [x16, x5]
	ldp	q0, q1, [x17, #448]
	ldp	q2, q3, [x17, #480]
	prfm	pldl1keep, [x16, x6]
	ldp	q4, q5, [x15, #448]
	ldp	q6, q7, [x15, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #448]
	stp	q2, q3, [x0, #480]
	prfm	pldl1keep, [x16, x7]
	ldp	q0, q1, [x17, #512]
	ldp	q2, q3, [x17, #544]
	prfm	pldl1keep, [x16, x24]
	ldp	q4, q5, [x15, #512]
	ldp	q6, q7, [x15, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #512]
	stp	q2, q3, [x0, #544]
	prfm	pldl1keep, [x16, x25]
	ldp	q0, q1, [x17, #576]
	ldp	q2, q3, [x17, #608]
	prfm	pldl1keep, [x16, x26]
	ldp	q4, q5, [x15, #576]
	ldp	q6, q7, [x15, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #576]
	stp	q2, q3, [x0, #608]
	prfm	pldl1keep, [x16, x19]
	ldp	q0, q1, [x17, #640]
	ldp	q2, q3, [x17, #672]
	prfm	pldl1keep, [x16, x28]
	ldp	q4, q5, [x15, #640]
	ldp	q6, q7, [x15, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #640]
	stp	q2, q3, [x0, #672]
	prfm	pldl1keep, [x16, x27]
	ldp	q0, q1, [x17, #704]
	ldp	q2, q3, [x17, #736]
	prfm	pldl1keep, [x16, x20]
	ldp	q4, q5, [x15, #704]
	ldp	q6, q7, [x15, #736]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #704]
	stp	q2, q3, [x0, #736]
	prfm	pldl1keep, [x16, x30]
	ldp	q0, q1, [x17, #768]
	ldp	q2, q3, [x17, #800]
	prfm	pldl1keep, [x16, x21]
	ldp	q4, q5, [x15, #768]
	ldp	q6, q7, [x15, #800]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #768]
	stp	q2, q3, [x0, #800]
	prfm	pldl1keep, [x16, x9]
	ldp	q0, q1, [x17, #832]
	ldp	q2, q3, [x17, #864]
	prfm	pldl1keep, [x16, x10]
	ldp	q4, q5, [x15, #832]
	ldp	q6, q7, [x15, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #832]
	stp	q2, q3, [x0, #864]
	prfm	pldl1keep, [x16, x11]
	ldp	q0, q1, [x17, #896]
	ldp	q2, q3, [x17, #928]
	prfm	pldl1keep, [x16, x12]
	ldp	q4, q5, [x15, #896]
	ldp	q6, q7, [x15, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #896]
	stp	q2, q3, [x0, #928]
	prfm	pldl1keep, [x16, x13]
	ldp	q0, q1, [x17, #960]
	ldp	q2, q3, [x17, #992]
	prfm	pldl1keep, [x16, x14]
	ldp	q4, q5, [x15, #960]
	ldp	q6, q7, [x15, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x0, #960]
	stp	q2, q3, [x0, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_87
; %bb.88:
	movi.2d	v0, #0000000000000000
	stp	q0, q0, [sp, #208]
	stp	q0, q0, [sp, #176]
	stp	q0, q0, [sp, #144]
	stp	q0, q0, [sp, #112]
	stp	q0, q0, [sp, #80]
	str	q0, [sp, #64]
	str	x22, [sp, #96]
	str	x23, [sp, #144]
	ldr	x19, [sp, #56]                  ; 8-byte Folded Reload
	str	x19, [sp, #192]
	add	x0, sp, #64
	bl	_sera_libxsmm_256
	mov	x8, #0                          ; =0x0
	ldr	x11, [sp, #40]                  ; 8-byte Folded Reload
LBB0_89:                                ; =>This Inner Loop Header: Depth=1
	add	x9, x11, x8, lsl #11
	add	x10, x19, x8, lsl #10
	ldp	q0, q1, [x10]
	ldp	q2, q3, [x10, #32]
	prfm	pldl1keep, [x9, #2048]
	ldp	q4, q5, [x9]
	ldp	q6, q7, [x9, #32]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9]
	stp	q2, q3, [x9, #32]
	ldp	q0, q1, [x10, #64]
	ldp	q2, q3, [x10, #96]
	prfm	pldl1keep, [x9, #2112]
	ldp	q4, q5, [x9, #64]
	ldp	q6, q7, [x9, #96]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #64]
	stp	q2, q3, [x9, #96]
	ldp	q0, q1, [x10, #128]
	ldp	q2, q3, [x10, #160]
	prfm	pldl1keep, [x9, #2176]
	ldp	q4, q5, [x9, #128]
	ldp	q6, q7, [x9, #160]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #128]
	ldp	q0, q1, [x10, #192]
	stp	q2, q3, [x9, #160]
	ldp	q2, q3, [x10, #224]
	prfm	pldl1keep, [x9, #2240]
	ldp	q4, q5, [x9, #192]
	ldp	q6, q7, [x9, #224]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #192]
	ldp	q0, q1, [x10, #256]
	stp	q2, q3, [x9, #224]
	ldp	q2, q3, [x10, #288]
	prfm	pldl1keep, [x9, #2304]
	ldp	q4, q5, [x9, #256]
	ldp	q6, q7, [x9, #288]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #256]
	ldp	q0, q1, [x10, #320]
	stp	q2, q3, [x9, #288]
	ldp	q4, q2, [x10, #352]
	prfm	pldl1keep, [x9, #2368]
	ldp	q3, q5, [x9, #320]
	ldp	q6, q7, [x9, #352]
	fadd.4s	v0, v3, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v3, v6, v4
	fadd.4s	v2, v7, v2
	stp	q0, q1, [x9, #320]
	ldp	q0, q1, [x10, #384]
	ldp	q4, q5, [x10, #416]
	stp	q3, q2, [x9, #352]
	prfm	pldl1keep, [x9, #2432]
	ldp	q2, q3, [x9, #384]
	ldp	q6, q7, [x9, #416]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	fadd.4s	v2, v6, v4
	fadd.4s	v3, v7, v5
	stp	q0, q1, [x9, #384]
	stp	q2, q3, [x9, #416]
	ldp	q0, q1, [x10, #448]
	ldp	q2, q3, [x10, #480]
	prfm	pldl1keep, [x9, #2496]
	ldp	q4, q5, [x9, #448]
	ldp	q6, q7, [x9, #480]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #448]
	stp	q2, q3, [x9, #480]
	ldp	q0, q1, [x10, #512]
	ldp	q2, q3, [x10, #544]
	prfm	pldl1keep, [x9, #2560]
	ldp	q4, q5, [x9, #512]
	ldp	q6, q7, [x9, #544]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #512]
	ldp	q0, q1, [x10, #576]
	stp	q2, q3, [x9, #544]
	ldp	q2, q3, [x10, #608]
	prfm	pldl1keep, [x9, #2624]
	ldp	q4, q5, [x9, #576]
	ldp	q6, q7, [x9, #608]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #576]
	ldp	q0, q1, [x10, #640]
	stp	q2, q3, [x9, #608]
	ldp	q2, q3, [x10, #672]
	prfm	pldl1keep, [x9, #2688]
	ldp	q4, q5, [x9, #640]
	ldp	q6, q7, [x9, #672]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #640]
	ldp	q0, q1, [x10, #704]
	stp	q2, q3, [x9, #672]
	ldp	q4, q2, [x10, #736]
	prfm	pldl1keep, [x9, #2752]
	ldp	q3, q5, [x9, #704]
	ldp	q6, q7, [x9, #736]
	fadd.4s	v0, v3, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v3, v6, v4
	fadd.4s	v2, v7, v2
	stp	q0, q1, [x9, #704]
	ldp	q0, q1, [x10, #768]
	ldp	q4, q5, [x10, #800]
	stp	q3, q2, [x9, #736]
	prfm	pldl1keep, [x9, #2816]
	ldp	q2, q3, [x9, #768]
	ldp	q6, q7, [x9, #800]
	fadd.4s	v0, v2, v0
	fadd.4s	v1, v3, v1
	fadd.4s	v2, v6, v4
	fadd.4s	v3, v7, v5
	stp	q0, q1, [x9, #768]
	stp	q2, q3, [x9, #800]
	ldp	q0, q1, [x10, #832]
	ldp	q2, q3, [x10, #864]
	prfm	pldl1keep, [x9, #2880]
	ldp	q4, q5, [x9, #832]
	ldp	q6, q7, [x9, #864]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #832]
	stp	q2, q3, [x9, #864]
	ldp	q0, q1, [x10, #896]
	ldp	q2, q3, [x10, #928]
	prfm	pldl1keep, [x9, #2944]
	ldp	q4, q5, [x9, #896]
	ldp	q6, q7, [x9, #928]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #896]
	ldp	q0, q1, [x10, #960]
	stp	q2, q3, [x9, #928]
	ldp	q2, q3, [x10, #992]
	prfm	pldl1keep, [x9, #3008]
	ldp	q4, q5, [x9, #960]
	ldp	q6, q7, [x9, #992]
	fadd.4s	v0, v4, v0
	fadd.4s	v1, v5, v1
	fadd.4s	v2, v6, v2
	fadd.4s	v3, v7, v3
	stp	q0, q1, [x9, #960]
	stp	q2, q3, [x9, #992]
	add	x8, x8, #1
	cmp	x8, #256
	b.ne	LBB0_89
; %bb.90:
	mov	x0, x23
	bl	_free
	mov	x0, x22
	bl	_free
	mov	x0, x19
	bl	_free
LBB0_91:
	ldur	x8, [x29, #-96]
Lloh6:
	adrp	x9, ___stack_chk_guard@GOTPAGE
Lloh7:
	ldr	x9, [x9, ___stack_chk_guard@GOTPAGEOFF]
Lloh8:
	ldr	x9, [x9]
	cmp	x9, x8
	b.ne	LBB0_93
; %bb.92:
	ldp	x29, x30, [sp, #336]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #320]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #304]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #288]            ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #272]            ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #256]            ; 16-byte Folded Reload
	add	sp, sp, #352
	ret
LBB0_93:
	bl	___stack_chk_fail
	.loh AdrpLdrGotLdr	Lloh0, Lloh1, Lloh2
	.loh AdrpLdrGotLdr	Lloh3, Lloh4, Lloh5
	.loh AdrpLdrGotLdr	Lloh6, Lloh7, Lloh8
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
	stp	d15, d14, [sp, #-160]!          ; 16-byte Folded Spill
	.cfi_def_cfa_offset 160
	stp	d13, d12, [sp, #16]             ; 16-byte Folded Spill
	stp	d11, d10, [sp, #32]             ; 16-byte Folded Spill
	stp	d9, d8, [sp, #48]               ; 16-byte Folded Spill
	stp	x28, x27, [sp, #64]             ; 16-byte Folded Spill
	stp	x26, x25, [sp, #80]             ; 16-byte Folded Spill
	stp	x24, x23, [sp, #96]             ; 16-byte Folded Spill
	stp	x22, x21, [sp, #112]            ; 16-byte Folded Spill
	stp	x20, x19, [sp, #128]            ; 16-byte Folded Spill
	stp	x29, x30, [sp, #144]            ; 16-byte Folded Spill
	add	x29, sp, #144
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
	cbz	x8, LBB2_2
; %bb.1:
	bl	___arm_tpidr2_save
	msr	TPIDR2_EL0, xzr
LBB2_2:
	smstart	za
	mov	x8, #0                          ; =0x0
	zero	{za}
	rdsvl	x12, #1
	lsr	x9, x12, #2
	mov	w10, w0
	lsl	x15, x9, #32
	lsl	w16, w9, #1
	sxtw	x11, w16
	sbfx	x27, x12, #2, #32
	ubfx	x13, x12, #2, #31
	ubfiz	x14, x0, #2, #32
	sbfiz	x30, x16, #2, #32
	mul	x12, x11, x10
	lsl	x16, x12, #2
	add	x17, x3, x15, asr #30
	mul	x12, x27, x10
	lsl	x4, x12, #2
	add	x5, x3, x4
	mov	x6, x27
	mov	x7, x1
	b	LBB2_4
LBB2_3:                                 ;   in Loop: Header=BB2_4 Depth=1
	add	x7, x7, x30
	add	x3, x3, x16
	add	x17, x17, x16
	add	x5, x5, x16
	add	x6, x6, x11
	add	x8, x8, x11
	cmp	x8, x10
	b.ge	LBB2_23
LBB2_4:                                 ; =>This Loop Header: Depth=1
                                        ;     Child Loop BB2_6 Depth 2
                                        ;       Child Loop BB2_7 Depth 3
                                        ;       Child Loop BB2_14 Depth 3
                                        ;       Child Loop BB2_11 Depth 3
                                        ;       Child Loop BB2_21 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
	mov	x19, #0                         ; =0x0
	whilelt	p0.s, w8, w0
	add	x12, x8, x27
	whilelt	p1.s, w12, w0
	cmp	x12, x10
	csel	w12, w9, wzr, lt
	add	w12, w8, w12
	lsl	x12, x12, #32
	add	x20, x1, x12, asr #30
	mov	x21, x5
	mov	x22, x17
	mov	x23, x3
	mov	x24, x2
	b	LBB2_6
LBB2_5:                                 ;   in Loop: Header=BB2_6 Depth=2
	add	x24, x24, x30
	add	x23, x23, x30
	add	x22, x22, x30
	add	x21, x21, x30
	add	x19, x19, x11
	cmp	x19, x10
	b.ge	LBB2_3
LBB2_6:                                 ;   Parent Loop BB2_4 Depth=1
                                        ; =>  This Loop Header: Depth=2
                                        ;       Child Loop BB2_7 Depth 3
                                        ;       Child Loop BB2_14 Depth 3
                                        ;       Child Loop BB2_11 Depth 3
                                        ;       Child Loop BB2_21 Depth 3
                                        ;       Child Loop BB2_18 Depth 3
	mov	x26, #0                         ; =0x0
	whilelt	p2.s, w19, w0
	add	x25, x19, x9
	whilelt	p3.s, w25, w0
	zero	{za}
	cmp	w0, w25
	csel	x12, x25, x19, gt
	lsl	x12, x12, #32
	add	x12, x2, x12, asr #30
	mov	x28, x10
LBB2_7:                                 ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x15, x7, x26
	ld1w	{ z0.s }, p0/z, [x15]
	add	x15, x20, x26
	ld1w	{ z1.s }, p1/z, [x15]
	add	x15, x24, x26
	ld1w	{ z2.s }, p2/z, [x15]
	add	x15, x12, x26
	ld1w	{ z3.s }, p3/z, [x15]
	fmopa	za0.s, p0/m, p2/m, z0.s, z2.s
	fmopa	za1.s, p0/m, p3/m, z0.s, z3.s
	fmopa	za2.s, p1/m, p2/m, z1.s, z2.s
	fmopa	za3.s, p1/m, p3/m, z1.s, z3.s
	add	x26, x26, x14
	subs	x28, x28, #1
	b.ne	LBB2_7
; %bb.8:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w9, #1
	b.lt	LBB2_5
; %bb.9:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w0, w25
	b.le	LBB2_13
; %bb.10:                               ;   in Loop: Header=BB2_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x15, #0                         ; =0x0
LBB2_11:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x26, x8, x15
	cmp	x26, x10
	b.ge	LBB2_16
; %bb.12:                               ;   in Loop: Header=BB2_11 Depth=3
	add	x26, x23, x12
	st1w	{za0h.s[w15, 0]}, p2, [x26]
	add	x26, x22, x12
	st1w	{za1h.s[w15, 0]}, p3, [x26]
	add	x15, x15, #1
	add	x12, x12, x14
	cmp	x13, x15
	b.ne	LBB2_11
	b	LBB2_16
LBB2_13:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x15, x23
LBB2_14:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x26, x8, x12
	cmp	x26, x10
	b.ge	LBB2_16
; %bb.15:                               ;   in Loop: Header=BB2_14 Depth=3
	st1w	{za0h.s[w12, 0]}, p2, [x15]
	add	x12, x12, #1
	add	x15, x15, x14
	cmp	x13, x12
	b.ne	LBB2_14
LBB2_16:                                ;   in Loop: Header=BB2_6 Depth=2
	cmp	w0, w25
	b.le	LBB2_20
; %bb.17:                               ;   in Loop: Header=BB2_6 Depth=2
	mov	x12, #0                         ; =0x0
	mov	x25, x4
LBB2_18:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	add	x15, x6, x12
	cmp	x15, x10
	b.ge	LBB2_5
; %bb.19:                               ;   in Loop: Header=BB2_18 Depth=3
	add	x15, x23, x25
	st1w	{za2h.s[w12, 0]}, p2, [x15]
	add	x15, x22, x25
	st1w	{za3h.s[w12, 0]}, p3, [x15]
	add	x12, x12, #1
	add	x25, x25, x14
	cmp	x13, x12
	b.ne	LBB2_18
	b	LBB2_5
LBB2_20:                                ;   in Loop: Header=BB2_6 Depth=2
	mov	w12, #0                         ; =0x0
	mov	x25, x13
	mov	x26, x6
	mov	x28, x21
LBB2_21:                                ;   Parent Loop BB2_4 Depth=1
                                        ;     Parent Loop BB2_6 Depth=2
                                        ; =>    This Inner Loop Header: Depth=3
	cmp	x26, x10
	b.ge	LBB2_5
; %bb.22:                               ;   in Loop: Header=BB2_21 Depth=3
	st1w	{za2h.s[w12, 0]}, p2, [x28]
	add	w12, w12, #1
	add	x28, x28, x14
	add	x26, x26, #1
	subs	x25, x25, #1
	b.ne	LBB2_21
	b	LBB2_5
LBB2_23:
	smstop	za
	smstop	sm
	.cfi_def_cfa wsp, 160
	ldp	x29, x30, [sp, #144]            ; 16-byte Folded Reload
	ldp	x20, x19, [sp, #128]            ; 16-byte Folded Reload
	ldp	x22, x21, [sp, #112]            ; 16-byte Folded Reload
	ldp	x24, x23, [sp, #96]             ; 16-byte Folded Reload
	ldp	x26, x25, [sp, #80]             ; 16-byte Folded Reload
	ldp	x28, x27, [sp, #64]             ; 16-byte Folded Reload
	ldp	d9, d8, [sp, #48]               ; 16-byte Folded Reload
	ldp	d11, d10, [sp, #32]             ; 16-byte Folded Reload
	ldp	d13, d12, [sp, #16]             ; 16-byte Folded Reload
	ldp	d15, d14, [sp], #160            ; 16-byte Folded Reload
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
