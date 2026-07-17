_ZN27systems_snackpack_topic_00610scan_count17hcc8a1af892b6d68fE:
.Lfunc_begin0:
	.file	1 "/tmp/systems-snackpack-topic006-b2fb451" "topics/006-ngram-text-indexing/src/lib.rs"
	.loc	1 185 0
	.cfi_startproc
	stp	x29, x30, [sp, #-64]!
	.cfi_def_cfa_offset 64
	str	x23, [sp, #16]
	stp	x22, x21, [sp, #32]
	stp	x20, x19, [sp, #48]
	mov	x29, sp
	.cfi_def_cfa w29, 64
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -48
	.cfi_offset w30, -56
	.cfi_offset w29, -64
	.cfi_remember_state
.Ltmp60:
	.file	2 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/slice/iter" "macros.rs"
	.loc	2 25 86 prologue_end
	cbz	x1, .LBB0_4
.Ltmp61:
	.loc	2 0 86 is_stmt 0
	mov	x19, x3
	mov	x20, x2
	mov	x21, x1
	mov	x22, xzr
.Ltmp62:
	.loc	2 284 24 is_stmt 1
	add	x23, x0, #16
	.loc	2 0 24 is_stmt 0
.Ltmp63:
	.p2align	5, , 16
.LBB0_2:
	.loc	2 279 27 is_stmt 1
	ldp	x0, x1, [x23, #-8]
.Ltmp64:
	.loc	1 188 28
	mov	x2, x20
	mov	x3, x19
	bl	_ZN27systems_snackpack_topic_00614contains_exact17h152785633432bbfaE
.Ltmp65:
	.file	3 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/iter/traits" "accum.rs"
	.loc	3 53 28
	add	x22, x22, w0, uxtw
.Ltmp66:
	.loc	2 284 24
	subs	x21, x21, #1
	add	x23, x23, #24
	b.ne	.LBB0_2
.Ltmp67:
	.loc	1 190 2
	mov	x0, x22
	.cfi_def_cfa wsp, 64
	.loc	1 190 2 epilogue_begin is_stmt 0
	ldp	x20, x19, [sp, #48]
	ldp	x22, x21, [sp, #32]
	ldr	x23, [sp, #16]
	ldp	x29, x30, [sp], #64
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB0_4:
	.cfi_restore_state
	.loc	1 0 2
	mov	x22, xzr
	.loc	1 190 2 is_stmt 1
	mov	x0, x22
	.cfi_def_cfa wsp, 64
	.loc	1 190 2 epilogue_begin is_stmt 0
	ldp	x20, x19, [sp, #48]
	ldp	x22, x21, [sp, #32]
	ldr	x23, [sp, #16]
	ldp	x29, x30, [sp], #64
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w30
	.cfi_restore w29
	ret
.Ltmp68:
.Lfunc_end0:
	.size	_ZN27systems_snackpack_topic_00610scan_count17hcc8a1af892b6d68fE, .Lfunc_end0-_ZN27systems_snackpack_topic_00610scan_count17hcc8a1af892b6d68fE
_ZN27systems_snackpack_topic_00614contains_exact17h152785633432bbfaE:
.Lfunc_begin3:
	.cfi_startproc
	.loc	1 198 8 prologue_end is_stmt 1
	cbz	x3, .LBB3_4
	stp	x29, x30, [sp, #-80]!
	.cfi_def_cfa_offset 80
	str	x25, [sp, #16]
	stp	x24, x23, [sp, #32]
	stp	x22, x21, [sp, #48]
	stp	x20, x19, [sp, #64]
	mov	x29, sp
	.cfi_def_cfa w29, 80
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -40
	.cfi_offset w24, -48
	.cfi_offset w25, -64
	.cfi_offset w30, -72
	.cfi_offset w29, -80
	.cfi_remember_state
	mov	x19, x3
	.loc	1 201 8
	subs	x22, x1, x3
	b.hs	.LBB3_5
	.loc	1 0 8 is_stmt 0
	mov	w0, wzr
.LBB3_3:
	.cfi_def_cfa wsp, 80
	ldp	x20, x19, [sp, #64]
	ldp	x22, x21, [sp, #48]
	ldr	x25, [sp, #16]
	ldp	x24, x23, [sp, #32]
	ldp	x29, x30, [sp], #80
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w25
	.cfi_restore w30
	.cfi_restore w29
	.loc	1 212 2 is_stmt 1
	ret
.LBB3_4:
	.loc	1 0 2 is_stmt 0
	mov	w0, #1
	.loc	1 212 2 is_stmt 1
	ret
.LBB3_5:
	.cfi_restore_state
	.loc	1 205 17
	ldrb	w23, [x2]
	mov	x20, x2
	mov	x21, x0
	mov	x24, xzr
	.loc	1 0 17 is_stmt 0
.Ltmp673:
	.p2align	5, , 16
.LBB3_6:
.Ltmp674:
	.loc	1 207 12 is_stmt 1
	ldrb	w8, [x21, x24]
.Ltmp675:
	.loc	19 1903 50
	cmp	x24, x22
.Ltmp676:
	.loc	26 1162 17
	cinc	x25, x24, lo
.Ltmp677:
	.loc	1 207 12
	cmp	w8, w23
	b.ne	.LBB3_8
	add	x0, x21, x24
.Ltmp678:
	.loc	18 152 13
	mov	x1, x20
	mov	x2, x19
	bl	bcmp
.Ltmp679:
	.loc	1 207 41
	cbz	w0, .LBB3_10
.Ltmp680:
.LBB3_8:
	.loc	1 0 41 is_stmt 0
	mov	w0, wzr
.Ltmp681:
	.loc	27 563 9 is_stmt 1
	cmp	x24, x22
	b.hs	.LBB3_3
	cmp	x25, x22
	mov	x24, x25
	b.ls	.LBB3_6
	b	.LBB3_3
.Ltmp682:
.LBB3_10:
	.loc	27 0 9 is_stmt 0
	mov	w0, #1
	.cfi_def_cfa wsp, 80
	ldp	x20, x19, [sp, #64]
	ldp	x22, x21, [sp, #48]
	ldr	x25, [sp, #16]
	ldp	x24, x23, [sp, #32]
	ldp	x29, x30, [sp], #80
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w25
	.cfi_restore w30
	.cfi_restore w29
	.loc	1 212 2 is_stmt 1
	ret
.Ltmp683:
.Lfunc_end3:
	.size	_ZN27systems_snackpack_topic_00614contains_exact17h152785633432bbfaE, .Lfunc_end3-_ZN27systems_snackpack_topic_00614contains_exact17h152785633432bbfaE
