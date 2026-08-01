	.file	"lib.c6f551dc431569fb-cgu.0"
	.section	.text._ZN3lib21publication_roundtrip17hbeb873775708e670E,"ax",@progbits
	.globl	_ZN3lib21publication_roundtrip17hbeb873775708e670E
	.p2align	2
	.type	_ZN3lib21publication_roundtrip17hbeb873775708e670E,@function
_ZN3lib21publication_roundtrip17hbeb873775708e670E:
.Lfunc_begin0:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception0
	sub	sp, sp, #368
	.cfi_def_cfa_offset 368
	stp	x29, x30, [sp, #288]
	str	x28, [sp, #304]
	stp	x24, x23, [sp, #320]
	stp	x22, x21, [sp, #336]
	stp	x20, x19, [sp, #352]
	add	x29, sp, #288
	.cfi_def_cfa w29, 80
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -40
	.cfi_offset w24, -48
	.cfi_offset w28, -64
	.cfi_offset w30, -72
	.cfi_offset w29, -80
	.cfi_remember_state
	str	x0, [sp, #8]
	cbz	x0, .LBB0_64
	stp	xzr, xzr, [sp, #16]
	add	x23, sp, #128
	str	xzr, [sp, #32]
	bl	_RNvNtNtCshxTglP3SOjd_3std6thread7current18current_or_unnamed
	mov	w8, #1
	mov	x21, x0
	stp	x0, xzr, [x29, #-64]
	dup	v0.2d, x8
	sturb	wzr, [x29, #-48]
	str	q0, [x23, #80]
	bl	_RNvCsfLfy6EI15iL_7___rustc35___rust_no_alloc_shim_is_unstable_v2
	mov	w0, #40
	mov	w1, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc12___rust_alloc
	cbz	x0, .LBB0_65
	ldp	q0, q1, [x23, #80]
	mov	x19, x0
	ldur	x8, [x29, #-48]
	mov	x1, x19
	str	x8, [x0, #32]
	mov	x8, #-9223372036854775808
	stp	q0, q1, [x0]
	stp	x0, x8, [sp, #40]
	mov	w0, #1
	bl	__aarch64_ldadd8_relax
	tbnz	x0, #63, .LBB0_76
	adrp	x24, :got:_RNvNCNvNtNtCshxTglP3SOjd_3std6thread9lifecycle15spawn_unchecked03MIN
	ldr	x24, [x24, :got_lo12:_RNvNCNvNtNtCshxTglP3SOjd_3std6thread9lifecycle15spawn_unchecked03MIN]
	str	x19, [sp, #72]
	ldr	x8, [x24]
	cbz	x8, .LBB0_5
	sub	x20, x8, #1
	b	.LBB0_30
.LBB0_5:
.Ltmp0:
	adrp	x0, .Lanon.8237690aa1ed0b145f80bff47c997adc.14
	add	x0, x0, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.14
	add	x8, sp, #128
	mov	w1, #14
	bl	_RNvNtCshxTglP3SOjd_3std3env7__var_os
.Ltmp1:
	ldr	x21, [sp, #128]
	mov	x8, #-9223372036854775808
	cmp	x21, x8
	b.ne	.LBB0_8
	mov	w20, #2097152
	b	.LBB0_29
.LBB0_8:
	ldp	x22, x1, [sp, #136]
.Ltmp2:
	sub	x8, x29, #80
	mov	x0, x22
	bl	_RNvNtNtCs6Hz1PecaLG4_4core3str8converts9from_utf8
.Ltmp3:
	ldur	x8, [x29, #-80]
	cmp	x8, #1
	b.eq	.LBB0_14
	ldur	x8, [x29, #-64]
	cbz	x8, .LBB0_14
	ldur	x9, [x29, #-72]
	cmp	x8, #1
	b.ne	.LBB0_15
	ldrb	w10, [x9]
	mov	w20, #2097152
	cmp	w10, #43
	b.eq	.LBB0_27
	cmp	w10, #45
	b.eq	.LBB0_27
	b	.LBB0_16
.LBB0_14:
	mov	w20, #2097152
	cbnz	x21, .LBB0_28
	b	.LBB0_29
.LBB0_15:
	ldrb	w10, [x9]
.LBB0_16:
	cmp	w10, #43
	cset	w10, eq
	cinc	x9, x9, eq
	sub	x8, x8, x10
	cmp	x8, #17
	b.hs	.LBB0_21
	mov	x20, xzr
	cbz	x8, .LBB0_27
	mov	w10, #10
.LBB0_19:
	ldrb	w11, [x9], #1
	sub	w11, w11, #48
	cmp	w11, #9
	b.hi	.LBB0_26
	mul	x12, x20, x10
	subs	x8, x8, #1
	add	x20, x12, w11, uxtw
	b.ne	.LBB0_19
	b	.LBB0_27
.LBB0_21:
	mov	x11, xzr
	mov	w10, #10
	mov	w20, #2097152
.LBB0_22:
	cbz	x8, .LBB0_63
	umulh	x12, x11, x10
	cmp	xzr, x12
	b.ne	.LBB0_27
	add	x11, x11, x11, lsl #2
	ldrb	w12, [x9], #1
	lsl	x11, x11, #1
	sub	w13, w12, #48
	adds	x11, x11, x13
	cset	w12, hs
	cmp	w13, #9
	b.hi	.LBB0_27
	sub	x8, x8, #1
	tbz	w12, #0, .LBB0_22
	b	.LBB0_27
.LBB0_26:
	mov	w20, #2097152
.LBB0_27:
	cbz	x21, .LBB0_29
.LBB0_28:
	mov	x0, x22
	mov	x1, x21
	mov	w2, #1
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB0_29:
	add	x8, x20, #1
	str	x8, [x24]
.LBB0_30:
.Ltmp5:
	bl	_RNvMNtNtCshxTglP3SOjd_3std6thread2idNtB2_8ThreadId3new
.Ltmp6:
.Ltmp7:
	add	x1, sp, #48
	bl	_RNvMs_NtNtCshxTglP3SOjd_3std6thread6threadNtB4_6Thread3new
.Ltmp8:
	str	x0, [sp, #80]
.Ltmp10:
	add	x8, sp, #88
	add	x0, sp, #80
	bl	_RNvNtNtCshxTglP3SOjd_3std6thread9spawnhook15run_spawn_hooks
.Ltmp11:
	mov	w8, #1
	stp	x19, xzr, [x29, #-64]
	dup	v0.2d, x8
	str	q0, [x23, #80]
	bl	_RNvCsfLfy6EI15iL_7___rustc35___rust_no_alloc_shim_is_unstable_v2
	mov	w0, #48
	mov	w1, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc12___rust_alloc
	cbz	x0, .LBB0_66
	ldp	q0, q1, [x23, #80]
	mov	x21, x0
	ldr	q2, [x23, #112]
	str	x0, [sp, #120]
	mov	x1, x21
	stp	q0, q1, [x0]
	str	q2, [x0, #32]
	mov	w0, #1
	bl	__aarch64_ldadd8_relax
	tbnz	x0, #63, .LBB0_76
	add	x8, sp, #32
	add	x9, sp, #16
	ldur	q0, [sp, #88]
	stp	x8, x9, [sp, #176]
	add	x8, sp, #24
	ldur	q1, [sp, #104]
	str	x8, [sp, #192]
	ldr	x8, [x21, #16]
	add	x9, sp, #8
	str	q0, [sp, #128]
	str	q1, [x23, #16]
	stp	x21, x9, [sp, #160]
	cbz	x8, .LBB0_37
.Ltmp13:
	add	x0, x8, #16
	bl	_RNvMNtNtCshxTglP3SOjd_3std6thread6scopedNtB2_9ScopeData29increment_num_running_threads
.Ltmp14:
.LBB0_37:
	ldp	q0, q1, [x23, #32]
	ldr	x8, [sp, #192]
	stur	x8, [x29, #-16]
	stp	q0, q1, [x23, #112]
	ldr	q0, [x23, #16]
	ldr	q1, [sp, #128]
	stp	q1, q0, [x23, #80]
	bl	_RNvCsfLfy6EI15iL_7___rustc35___rust_no_alloc_shim_is_unstable_v2
	mov	w0, #72
	mov	w1, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc12___rust_alloc
	cbz	x0, .LBB0_68
	ldp	q0, q1, [x23, #32]
	mov	x22, x0
	ldr	x8, [sp, #192]
	ldr	x1, [sp, #80]
	stp	q0, q1, [x0, #32]
	ldr	q0, [x23, #16]
	ldr	q1, [sp, #128]
	str	x8, [x0, #64]
	stp	q1, q0, [x0]
	mov	w0, #1
	bl	__aarch64_ldadd8_relax
	tbnz	x0, #63, .LBB0_76
	ldr	x8, [sp, #80]
	stp	x8, x22, [x29, #-80]
	adrp	x8, .Lanon.8237690aa1ed0b145f80bff47c997adc.13
	add	x8, x8, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.13
	stur	x8, [x29, #-64]
	bl	_RNvCsfLfy6EI15iL_7___rustc35___rust_no_alloc_shim_is_unstable_v2
	mov	w0, #24
	mov	w1, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc12___rust_alloc
	cbz	x0, .LBB0_69
	ldr	q0, [x23, #80]
	ldur	x8, [x29, #-64]
	mov	x1, x0
	str	q0, [x0]
	str	x8, [x0, #16]
.Ltmp18:
	mov	x0, x20
	bl	_RNvMs0_NtNtNtCshxTglP3SOjd_3std3sys6thread4unixNtB5_6Thread3new
.Ltmp19:
	cmp	x0, #1
	b.eq	.LBB0_71
	ldr	x8, [sp, #80]
	stur	x1, [x29, #-64]
	stp	x8, x21, [x29, #-80]
	sub	x21, x29, #80
.Ltmp21:
	add	x0, x21, #16
	bl	_RNvXs1_NtNtNtCshxTglP3SOjd_3std3sys6thread4unixNtB5_6ThreadNtNtNtCs6Hz1PecaLG4_4core3ops4drop4Drop4drop
.Ltmp22:
	ldur	x1, [x29, #-80]
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_45
	dmb	ishld
.Ltmp26:
	sub	x0, x29, #80
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp27:
.LBB0_45:
	ldur	x1, [x29, #-72]
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_47
	dmb	ishld
.Ltmp32:
	add	x0, x21, #8
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp33:
.LBB0_47:
	ldr	x8, [sp, #8]
	cbz	x8, .LBB0_54
	mov	w11, #1
	add	x9, sp, #24
	add	x10, sp, #32
.LBB0_49:
	str	x11, [sp, #128]
	cmp	x11, x8
	ldar	x13, [x9]
	cinc	x12, x11, lo
	cmp	x13, x11
	b.eq	.LBB0_51
.LBB0_50:
	isb
	ldar	x13, [x9]
	cmp	x13, x11
	b.ne	.LBB0_50
.LBB0_51:
	ldr	x13, [sp, #16]
	cmp	x13, x11
	stur	x13, [x29, #-80]
	b.ne	.LBB0_62
	cmp	x11, x8
	stlr	x11, [x10]
	b.hs	.LBB0_54
	cmp	x12, x8
	mov	x11, x12
	b.ls	.LBB0_49
.LBB0_54:
	mov	x21, xzr
.LBB0_55:
	add	x8, x19, #24
	ldar	x8, [x8]
	cbz	x8, .LBB0_57
.Ltmp78:
	add	x0, x19, #16
	bl	_RNvMs_NtNtCshxTglP3SOjd_3std6thread6threadNtB4_6Thread4park
.Ltmp79:
	b	.LBB0_55
.LBB0_57:
	cbnz	x21, .LBB0_70
	ldrb	w8, [x19, #32]
	cbnz	w8, .LBB0_67
	mov	x0, #-1
	mov	x1, x19
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_61
	add	x0, sp, #40
	dmb	ishld
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
.LBB0_61:
	ldr	x0, [sp, #16]
	.cfi_def_cfa wsp, 368
	ldp	x20, x19, [sp, #352]
	ldr	x28, [sp, #304]
	ldp	x22, x21, [sp, #336]
	ldp	x24, x23, [sp, #320]
	ldp	x29, x30, [sp, #288]
	add	sp, sp, #368
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w28
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB0_62:
	.cfi_restore_state
.Ltmp34:
	adrp	x5, .Lanon.8237690aa1ed0b145f80bff47c997adc.7
	add	x5, x5, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.7
	sub	x1, x29, #80
	add	x2, sp, #128
	mov	w0, wzr
	mov	x3, xzr
	bl	_RINvNtCs6Hz1PecaLG4_4core9panicking13assert_failedyyEB4_
.Ltmp35:
	b	.LBB0_76
.LBB0_63:
	mov	x20, x11
	cbnz	x21, .LBB0_28
	b	.LBB0_29
.LBB0_64:
	adrp	x0, .Lanon.8237690aa1ed0b145f80bff47c997adc.0
	add	x0, x0, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.0
	adrp	x2, .Lanon.8237690aa1ed0b145f80bff47c997adc.2
	add	x2, x2, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.2
	mov	w1, #45
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking9panic_fmt
.LBB0_65:
.Ltmp91:
	mov	w0, #8
	mov	w1, #40
	sub	x19, x29, #80
	bl	_RNvNtCs3U9RWQJh2dM_5alloc5alloc18handle_alloc_error
.Ltmp92:
	b	.LBB0_76
.LBB0_66:
.Ltmp62:
	mov	w0, #8
	mov	w1, #48
	sub	x21, x29, #80
	bl	_RNvNtCs3U9RWQJh2dM_5alloc5alloc18handle_alloc_error
.Ltmp63:
	b	.LBB0_76
.LBB0_67:
.Ltmp85:
	adrp	x0, .Lanon.8237690aa1ed0b145f80bff47c997adc.12
	add	x0, x0, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.12
	adrp	x2, .Lanon.8237690aa1ed0b145f80bff47c997adc.3
	add	x2, x2, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.3
	mov	w1, #49
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking9panic_fmt
.Ltmp86:
	b	.LBB0_76
.LBB0_68:
.Ltmp54:
	mov	w0, #8
	mov	w1, #72
	bl	_RNvNtCs3U9RWQJh2dM_5alloc5alloc18handle_alloc_error
.Ltmp55:
	b	.LBB0_76
.LBB0_69:
.Ltmp48:
	mov	w0, #8
	mov	w1, #24
	bl	_RNvNtCs3U9RWQJh2dM_5alloc5alloc18handle_alloc_error
.Ltmp49:
	b	.LBB0_76
.LBB0_70:
.Ltmp83:
	mov	x0, x21
	mov	x1, x22
	bl	_RNvNtCshxTglP3SOjd_3std5panic13resume_unwind
.Ltmp84:
	b	.LBB0_76
.LBB0_71:
	mov	x20, x1
	mov	x0, #-1
	mov	x1, x21
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_73
	dmb	ishld
.Ltmp36:
	add	x0, sp, #120
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp37:
.LBB0_73:
	ldr	x1, [sp, #80]
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_75
	dmb	ishld
.Ltmp39:
	add	x0, sp, #80
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp40:
.LBB0_75:
	stur	x20, [x29, #-80]
.Ltmp42:
	adrp	x0, .Lanon.8237690aa1ed0b145f80bff47c997adc.4
	add	x0, x0, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.4
	adrp	x3, .Lanon.8237690aa1ed0b145f80bff47c997adc.15
	add	x3, x3, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.15
	adrp	x4, .Lanon.8237690aa1ed0b145f80bff47c997adc.6
	add	x4, x4, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.6
	sub	x2, x29, #80
	mov	w1, #22
	bl	_RNvNtCs6Hz1PecaLG4_4core6result13unwrap_failed
.Ltmp43:
.LBB0_76:
	brk	#0x1
.LBB0_77:
.Ltmp4:
	mov	x20, x0
	cbz	x21, .LBB0_106
	mov	x0, x22
	mov	x1, x21
	mov	w2, #1
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
	b	.LBB0_106
.LBB0_79:
.Ltmp38:
	mov	x20, x0
	b	.LBB0_102
.LBB0_80:
.Ltmp28:
	mov	x20, x0
	b	.LBB0_86
.LBB0_81:
.Ltmp44:
	mov	x20, x0
.Ltmp45:
	sub	x0, x29, #80
	bl	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E
.Ltmp46:
	b	.LBB0_119
.LBB0_82:
.Ltmp47:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_83:
.Ltmp15:
	mov	x20, x0
.Ltmp16:
	add	x0, sp, #128
	bl	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E
.Ltmp17:
	b	.LBB0_97
.LBB0_84:
.Ltmp23:
	ldur	x1, [x29, #-80]
	mov	x20, x0
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_86
	dmb	ishld
.Ltmp24:
	sub	x0, x29, #80
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp25:
.LBB0_86:
	ldur	x1, [x29, #-72]
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_119
	dmb	ishld
.Ltmp29:
	add	x0, x21, #8
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp30:
	b	.LBB0_119
.LBB0_88:
.Ltmp31:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_89:
.Ltmp20:
	mov	x20, x0
	b	.LBB0_97
.LBB0_90:
.Ltmp12:
	mov	x20, x0
	mov	w21, #1
	b	.LBB0_103
.LBB0_91:
.Ltmp9:
	mov	x20, x0
	b	.LBB0_106
.LBB0_92:
.Ltmp80:
	mov	x20, x0
	cbz	x21, .LBB0_114
.Ltmp81:
	mov	x0, x21
	mov	x1, x22
	bl	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E
.Ltmp82:
	b	.LBB0_114
.LBB0_94:
.Ltmp50:
	mov	x20, x0
.Ltmp51:
	sub	x0, x29, #80
	bl	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E
.Ltmp52:
	b	.LBB0_97
.LBB0_95:
.Ltmp53:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_96:
.Ltmp56:
	mov	x20, x0
.Ltmp57:
	sub	x0, x29, #80
	bl	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E
.Ltmp58:
.LBB0_97:
	mov	x0, #-1
	mov	x1, x21
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_102
	dmb	ishld
.Ltmp60:
	add	x0, sp, #120
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp61:
	b	.LBB0_102
.LBB0_99:
.Ltmp59:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_100:
.Ltmp64:
	mov	x20, x0
.Ltmp65:
	add	x0, x21, #16
	bl	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE
.Ltmp66:
.Ltmp68:
	add	x0, sp, #88
	bl	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E
.Ltmp69:
.LBB0_102:
	mov	w21, wzr
.LBB0_103:
	ldr	x1, [sp, #80]
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_105
	dmb	ishld
.Ltmp70:
	add	x0, sp, #80
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp71:
.LBB0_105:
	cbz	w21, .LBB0_119
.LBB0_106:
	mov	x0, #-1
	mov	x1, x19
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_119
	dmb	ishld
.Ltmp72:
	add	x0, sp, #72
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
.Ltmp73:
	b	.LBB0_119
.LBB0_108:
.Ltmp67:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_109:
.Ltmp74:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_110:
.Ltmp93:
	mov	x20, x0
	mov	x0, #-1
	mov	x1, x21
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_116
	dmb	ishld
.Ltmp94:
	add	x0, x19, #16
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp95:
	b	.LBB0_116
.LBB0_112:
.Ltmp96:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_113:
.Ltmp87:
	mov	x20, x0
.LBB0_114:
	mov	x0, #-1
	mov	x1, x19
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB0_116
	dmb	ishld
.Ltmp88:
	add	x0, sp, #40
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
.Ltmp89:
.LBB0_116:
	mov	x0, x20
	bl	_Unwind_Resume
.LBB0_117:
.Ltmp90:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB0_118:
.Ltmp41:
	mov	x20, x0
.LBB0_119:
.Ltmp75:
	mov	x0, x20
	bl	_RNvNvNtCshxTglP3SOjd_3std9panicking12catch_unwind7cleanup
.Ltmp76:
	mov	x21, x0
	mov	x22, x1
	b	.LBB0_55
.LBB0_121:
.Ltmp77:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking19panic_cannot_unwind
.Lfunc_end0:
	.size	_ZN3lib21publication_roundtrip17hbeb873775708e670E, .Lfunc_end0-_ZN3lib21publication_roundtrip17hbeb873775708e670E
	.cfi_endproc
	.section	.gcc_except_table._ZN3lib21publication_roundtrip17hbeb873775708e670E,"a",@progbits
	.p2align	2, 0x0
GCC_except_table0:
.Lexception0:
	.byte	255
	.byte	156
	.uleb128 .Lttbase0-.Lttbaseref0
.Lttbaseref0:
	.byte	1
	.uleb128 .Lcst_end0-.Lcst_begin0
.Lcst_begin0:
	.uleb128 .Lfunc_begin0-.Lfunc_begin0
	.uleb128 .Ltmp0-.Lfunc_begin0
	.byte	0
	.byte	0
	.uleb128 .Ltmp0-.Lfunc_begin0
	.uleb128 .Ltmp1-.Ltmp0
	.uleb128 .Ltmp9-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp2-.Lfunc_begin0
	.uleb128 .Ltmp3-.Ltmp2
	.uleb128 .Ltmp4-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp5-.Lfunc_begin0
	.uleb128 .Ltmp8-.Ltmp5
	.uleb128 .Ltmp9-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp10-.Lfunc_begin0
	.uleb128 .Ltmp11-.Ltmp10
	.uleb128 .Ltmp12-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp11-.Lfunc_begin0
	.uleb128 .Ltmp13-.Ltmp11
	.byte	0
	.byte	0
	.uleb128 .Ltmp13-.Lfunc_begin0
	.uleb128 .Ltmp14-.Ltmp13
	.uleb128 .Ltmp15-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp14-.Lfunc_begin0
	.uleb128 .Ltmp18-.Ltmp14
	.byte	0
	.byte	0
	.uleb128 .Ltmp18-.Lfunc_begin0
	.uleb128 .Ltmp19-.Ltmp18
	.uleb128 .Ltmp20-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp21-.Lfunc_begin0
	.uleb128 .Ltmp22-.Ltmp21
	.uleb128 .Ltmp23-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp22-.Lfunc_begin0
	.uleb128 .Ltmp26-.Ltmp22
	.byte	0
	.byte	0
	.uleb128 .Ltmp26-.Lfunc_begin0
	.uleb128 .Ltmp27-.Ltmp26
	.uleb128 .Ltmp28-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp27-.Lfunc_begin0
	.uleb128 .Ltmp32-.Ltmp27
	.byte	0
	.byte	0
	.uleb128 .Ltmp32-.Lfunc_begin0
	.uleb128 .Ltmp33-.Ltmp32
	.uleb128 .Ltmp41-.Lfunc_begin0
	.byte	7
	.uleb128 .Ltmp78-.Lfunc_begin0
	.uleb128 .Ltmp79-.Ltmp78
	.uleb128 .Ltmp80-.Lfunc_begin0
	.byte	0
	.uleb128 .Ltmp79-.Lfunc_begin0
	.uleb128 .Ltmp34-.Ltmp79
	.byte	0
	.byte	0
	.uleb128 .Ltmp34-.Lfunc_begin0
	.uleb128 .Ltmp35-.Ltmp34
	.uleb128 .Ltmp41-.Lfunc_begin0
	.byte	7
	.uleb128 .Ltmp35-.Lfunc_begin0
	.uleb128 .Ltmp91-.Ltmp35
	.byte	0
	.byte	0
	.uleb128 .Ltmp91-.Lfunc_begin0
	.uleb128 .Ltmp92-.Ltmp91
	.uleb128 .Ltmp93-.Lfunc_begin0
	.byte	0
	.uleb128 .Ltmp62-.Lfunc_begin0
	.uleb128 .Ltmp63-.Ltmp62
	.uleb128 .Ltmp64-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp85-.Lfunc_begin0
	.uleb128 .Ltmp86-.Ltmp85
	.uleb128 .Ltmp87-.Lfunc_begin0
	.byte	0
	.uleb128 .Ltmp54-.Lfunc_begin0
	.uleb128 .Ltmp55-.Ltmp54
	.uleb128 .Ltmp56-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp48-.Lfunc_begin0
	.uleb128 .Ltmp49-.Ltmp48
	.uleb128 .Ltmp50-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp83-.Lfunc_begin0
	.uleb128 .Ltmp84-.Ltmp83
	.uleb128 .Ltmp87-.Lfunc_begin0
	.byte	0
	.uleb128 .Ltmp84-.Lfunc_begin0
	.uleb128 .Ltmp36-.Ltmp84
	.byte	0
	.byte	0
	.uleb128 .Ltmp36-.Lfunc_begin0
	.uleb128 .Ltmp37-.Ltmp36
	.uleb128 .Ltmp38-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp37-.Lfunc_begin0
	.uleb128 .Ltmp39-.Ltmp37
	.byte	0
	.byte	0
	.uleb128 .Ltmp39-.Lfunc_begin0
	.uleb128 .Ltmp40-.Ltmp39
	.uleb128 .Ltmp41-.Lfunc_begin0
	.byte	7
	.uleb128 .Ltmp42-.Lfunc_begin0
	.uleb128 .Ltmp43-.Ltmp42
	.uleb128 .Ltmp44-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp45-.Lfunc_begin0
	.uleb128 .Ltmp46-.Ltmp45
	.uleb128 .Ltmp47-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp16-.Lfunc_begin0
	.uleb128 .Ltmp17-.Ltmp16
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp17-.Lfunc_begin0
	.uleb128 .Ltmp24-.Ltmp17
	.byte	0
	.byte	0
	.uleb128 .Ltmp24-.Lfunc_begin0
	.uleb128 .Ltmp25-.Ltmp24
	.uleb128 .Ltmp31-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp25-.Lfunc_begin0
	.uleb128 .Ltmp29-.Ltmp25
	.byte	0
	.byte	0
	.uleb128 .Ltmp29-.Lfunc_begin0
	.uleb128 .Ltmp30-.Ltmp29
	.uleb128 .Ltmp31-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp81-.Lfunc_begin0
	.uleb128 .Ltmp82-.Ltmp81
	.uleb128 .Ltmp90-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp51-.Lfunc_begin0
	.uleb128 .Ltmp52-.Ltmp51
	.uleb128 .Ltmp53-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp57-.Lfunc_begin0
	.uleb128 .Ltmp58-.Ltmp57
	.uleb128 .Ltmp59-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp58-.Lfunc_begin0
	.uleb128 .Ltmp60-.Ltmp58
	.byte	0
	.byte	0
	.uleb128 .Ltmp60-.Lfunc_begin0
	.uleb128 .Ltmp61-.Ltmp60
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp65-.Lfunc_begin0
	.uleb128 .Ltmp66-.Ltmp65
	.uleb128 .Ltmp67-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp68-.Lfunc_begin0
	.uleb128 .Ltmp69-.Ltmp68
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp69-.Lfunc_begin0
	.uleb128 .Ltmp70-.Ltmp69
	.byte	0
	.byte	0
	.uleb128 .Ltmp70-.Lfunc_begin0
	.uleb128 .Ltmp71-.Ltmp70
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp71-.Lfunc_begin0
	.uleb128 .Ltmp72-.Ltmp71
	.byte	0
	.byte	0
	.uleb128 .Ltmp72-.Lfunc_begin0
	.uleb128 .Ltmp73-.Ltmp72
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp73-.Lfunc_begin0
	.uleb128 .Ltmp94-.Ltmp73
	.byte	0
	.byte	0
	.uleb128 .Ltmp94-.Lfunc_begin0
	.uleb128 .Ltmp95-.Ltmp94
	.uleb128 .Ltmp96-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp95-.Lfunc_begin0
	.uleb128 .Ltmp88-.Ltmp95
	.byte	0
	.byte	0
	.uleb128 .Ltmp88-.Lfunc_begin0
	.uleb128 .Ltmp89-.Ltmp88
	.uleb128 .Ltmp90-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp89-.Lfunc_begin0
	.uleb128 .Ltmp75-.Ltmp89
	.byte	0
	.byte	0
	.uleb128 .Ltmp75-.Lfunc_begin0
	.uleb128 .Ltmp76-.Ltmp75
	.uleb128 .Ltmp77-.Lfunc_begin0
	.byte	1
.Lcst_end0:
	.byte	127
	.byte	0
	.byte	0
	.byte	0
	.byte	1
	.byte	125
	.byte	1
	.byte	0
	.p2align	2, 0x0
	.xword	0
.Lttbase0:
	.byte	0
	.p2align	2, 0x0

	.section	.text._ZN3std2io5Write9write_all17h9313e362643cf870E,"ax",@progbits
	.p2align	2
	.type	_ZN3std2io5Write9write_all17h9313e362643cf870E,@function
_ZN3std2io5Write9write_all17h9313e362643cf870E:
	.cfi_startproc
	sub	sp, sp, #80
	.cfi_def_cfa_offset 80
	stp	x29, x30, [sp, #16]
	str	x23, [sp, #32]
	stp	x22, x21, [sp, #48]
	stp	x20, x19, [sp, #64]
	add	x29, sp, #16
	.cfi_def_cfa w29, 64
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -48
	.cfi_offset w30, -56
	.cfi_offset w29, -64
	.cfi_remember_state
	cbz	x2, .LBB1_14
	mov	x19, x2
	mov	x20, x1
	mov	x21, x0
	mov	x23, sp
	adrp	x22, .Lanon.8237690aa1ed0b145f80bff47c997adc.10
	add	x22, x22, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.10
	b	.LBB1_4
.LBB1_2:
	cmp	x8, #35
	b.ne	.LBB1_15
.LBB1_3:
	add	x0, x23, #8
	bl	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E
	cbz	x19, .LBB1_14
.LBB1_4:
	mov	x0, x21
	mov	x1, x20
	mov	x2, x19
	bl	_RNvXs3_NtNtNtCshxTglP3SOjd_3std3sys5stdio4unixNtB5_6StderrNtNtBb_2io5Write5write
	stp	x0, x1, [sp]
	tbz	w0, #0, .LBB1_8
	and	x8, x1, #0x3
	cmp	x8, #1
	b.gt	.LBB1_11
	cbnz	x8, .LBB1_13
	ldrb	w8, [x1, #16]
	cmp	w8, #35
	b.eq	.LBB1_3
	b	.LBB1_15
.LBB1_8:
	cbz	x1, .LBB1_16
	subs	x8, x19, x1
	b.lo	.LBB1_17
	add	x20, x20, x1
	mov	x19, x8
	cbnz	x8, .LBB1_4
	b	.LBB1_14
.LBB1_11:
	cmp	x8, #2
	lsr	x8, x1, #32
	b.ne	.LBB1_2
	cmp	x8, #4
	b.eq	.LBB1_3
	b	.LBB1_15
.LBB1_13:
	ldrb	w8, [x1, #15]
	cmp	w8, #35
	b.eq	.LBB1_3
	b	.LBB1_15
.LBB1_14:
	mov	x1, xzr
.LBB1_15:
	mov	x0, x1
	.cfi_def_cfa wsp, 80
	ldp	x20, x19, [sp, #64]
	ldr	x23, [sp, #32]
	ldp	x22, x21, [sp, #48]
	ldp	x29, x30, [sp, #16]
	add	sp, sp, #80
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB1_16:
	.cfi_restore_state
	mov	x1, x22
	b	.LBB1_15
.LBB1_17:
	adrp	x3, .Lanon.8237690aa1ed0b145f80bff47c997adc.11
	add	x3, x3, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.11
	mov	x0, x1
	mov	x1, x19
	mov	x2, x19
	bl	_RNvNtNtCs6Hz1PecaLG4_4core5slice5index16slice_index_fail
.Lfunc_end1:
	.size	_ZN3std2io5Write9write_all17h9313e362643cf870E, .Lfunc_end1-_ZN3std2io5Write9write_all17h9313e362643cf870E
	.cfi_endproc

	.section	.text._ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE,"ax",@progbits
	.globl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE
	.p2align	2
	.type	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE,@function
_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE:
	.cfi_startproc
	sub	sp, sp, #48
	.cfi_def_cfa_offset 48
	stp	x29, x30, [sp, #32]
	add	x29, sp, #32
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	ldp	q0, q1, [x0]
	mov	x0, sp
	stp	q0, q1, [sp]
	bl	_RNvMs_NtNtCshxTglP3SOjd_3std6thread9spawnhookNtB4_15ChildSpawnHooks3run
	//APP
	//NO_APP
	.cfi_def_cfa wsp, 48
	ldp	x29, x30, [sp, #32]
	add	sp, sp, #48
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end2:
	.size	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE, .Lfunc_end2-_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE
	.cfi_endproc

	.section	.text._ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE,"ax",@progbits
	.globl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE
	.p2align	2
	.type	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE,@function
_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE:
	.cfi_startproc
	ldr	x8, [x0]
	ldr	x8, [x8]
	cbz	x8, .LBB3_6
	ldp	x9, x10, [x0, #8]
	mov	w12, #1
	ldr	x11, [x0, #24]
.LBB3_2:
	ldar	x15, [x9]
	cmp	x12, x8
	sub	x14, x12, #1
	cinc	x13, x12, lo
	cmp	x15, x14
	b.eq	.LBB3_4
.LBB3_3:
	isb
	ldar	x15, [x9]
	cmp	x15, x14
	b.ne	.LBB3_3
.LBB3_4:
	cmp	x12, x8
	str	x12, [x10]
	stlr	x12, [x11]
	b.hs	.LBB3_6
	cmp	x13, x8
	mov	x12, x13
	b.ls	.LBB3_2
.LBB3_6:
	//APP
	//NO_APP
	ret
.Lfunc_end3:
	.size	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE, .Lfunc_end3-_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE
	.cfi_endproc

	.section	".text._ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE","ax",@progbits
	.p2align	2
	.type	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE,@function
_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE:
.Lfunc_begin1:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception1
	sub	sp, sp, #192
	.cfi_def_cfa_offset 192
	stp	x29, x30, [sp, #128]
	stp	x24, x23, [sp, #144]
	stp	x22, x21, [sp, #160]
	stp	x20, x19, [sp, #176]
	add	x29, sp, #128
	.cfi_def_cfa w29, 64
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -40
	.cfi_offset w24, -48
	.cfi_offset w30, -56
	.cfi_offset w29, -64
	.cfi_remember_state
	ldp	q3, q2, [x0]
	mov	x19, x0
	ldur	q0, [x0, #56]
	ldur	q1, [x0, #40]
	stp	q1, q0, [sp, #16]
	str	q2, [sp]
	stp	q3, q2, [sp, #64]
	stp	q1, q0, [sp, #96]
.Ltmp97:
	add	x0, sp, #64
	add	x20, sp, #64
	bl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17he408abf18feb6c2bE
.Ltmp98:
	add	x0, x20, #32
	bl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hf3df56bdfa989afdE
	mov	x20, xzr
	ldr	x22, [x19, #32]!
	ldr	x8, [x22, #24]
	cbz	x8, .LBB4_7
.LBB4_2:
	ldr	x24, [x22, #32]
	cbz	x24, .LBB4_7
	ldr	x23, [x22, #40]
	ldr	x8, [x23]
	cbz	x8, .LBB4_5
.Ltmp103:
	mov	x0, x24
	blr	x8
.Ltmp104:
.LBB4_5:
	ldr	x1, [x23, #8]
	cbz	x1, .LBB4_7
	ldr	x2, [x23, #16]
	mov	x0, x24
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB4_7:
	mov	w8, #1
	mov	x0, #-1
	mov	x1, x22
	stp	x8, x20, [x22, #24]
	str	x21, [x22, #40]
	str	x22, [sp, #56]
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB4_9
	add	x0, sp, #56
	dmb	ishld
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.LBB4_9:
	.cfi_def_cfa wsp, 192
	ldp	x20, x19, [sp, #176]
	ldp	x22, x21, [sp, #160]
	ldp	x24, x23, [sp, #144]
	ldp	x29, x30, [sp, #128]
	add	sp, sp, #192
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB4_10:
	.cfi_restore_state
.Ltmp105:
	ldr	x1, [x23, #8]
	mov	x8, x23
	mov	x23, x0
	cbz	x1, .LBB4_12
	ldr	x2, [x8, #16]
	mov	x0, x24
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB4_12:
	mov	w8, #1
	mov	x0, #-1
	mov	x1, x22
	stp	x8, x20, [x22, #24]
	str	x21, [x22, #40]
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB4_14
	dmb	ishld
.Ltmp106:
	mov	x0, x19
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp107:
.LBB4_14:
	mov	x0, x23
	bl	_Unwind_Resume
.LBB4_15:
.Ltmp108:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB4_16:
.Ltmp99:
.Ltmp100:
	bl	_RNvNvNtCshxTglP3SOjd_3std9panicking12catch_unwind7cleanup
.Ltmp101:
	mov	x20, x0
	mov	x21, x1
	ldr	x22, [x19, #32]!
	ldr	x8, [x22, #24]
	cbnz	x8, .LBB4_2
	b	.LBB4_7
.LBB4_18:
.Ltmp102:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking19panic_cannot_unwind
.Lfunc_end4:
	.size	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE, .Lfunc_end4-_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE","a",@progbits
	.p2align	2, 0x0
GCC_except_table4:
.Lexception1:
	.byte	255
	.byte	156
	.uleb128 .Lttbase1-.Lttbaseref1
.Lttbaseref1:
	.byte	1
	.uleb128 .Lcst_end1-.Lcst_begin1
.Lcst_begin1:
	.uleb128 .Ltmp97-.Lfunc_begin1
	.uleb128 .Ltmp98-.Ltmp97
	.uleb128 .Ltmp99-.Lfunc_begin1
	.byte	3
	.uleb128 .Ltmp103-.Lfunc_begin1
	.uleb128 .Ltmp104-.Ltmp103
	.uleb128 .Ltmp105-.Lfunc_begin1
	.byte	0
	.uleb128 .Ltmp104-.Lfunc_begin1
	.uleb128 .Ltmp106-.Ltmp104
	.byte	0
	.byte	0
	.uleb128 .Ltmp106-.Lfunc_begin1
	.uleb128 .Ltmp107-.Ltmp106
	.uleb128 .Ltmp108-.Lfunc_begin1
	.byte	1
	.uleb128 .Ltmp107-.Lfunc_begin1
	.uleb128 .Ltmp100-.Ltmp107
	.byte	0
	.byte	0
	.uleb128 .Ltmp100-.Lfunc_begin1
	.uleb128 .Ltmp101-.Ltmp100
	.uleb128 .Ltmp102-.Lfunc_begin1
	.byte	1
.Lcst_end1:
	.byte	127
	.byte	0
	.byte	1
	.byte	0
	.p2align	2, 0x0
	.xword	0
.Lttbase1:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E,@function
_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E:
.Lfunc_begin2:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception2
	stp	x29, x30, [sp, #-48]!
	.cfi_def_cfa_offset 48
	str	x21, [sp, #16]
	stp	x20, x19, [sp, #32]
	mov	x29, sp
	.cfi_def_cfa w29, 48
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -32
	.cfi_offset w30, -40
	.cfi_offset w29, -48
	.cfi_remember_state
	cbz	x0, .LBB5_5
	ldr	x8, [x1]
	mov	x19, x0
	mov	x20, x1
	cbz	x8, .LBB5_3
.Ltmp109:
	mov	x0, x19
	blr	x8
.Ltmp110:
.LBB5_3:
	ldr	x1, [x20, #8]
	cbz	x1, .LBB5_5
	ldr	x2, [x20, #16]
	mov	x0, x19
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB5_5:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB5_6:
	.cfi_restore_state
.Ltmp111:
	ldr	x1, [x20, #8]
	mov	x21, x0
	cbz	x1, .LBB5_8
	ldr	x2, [x20, #16]
	mov	x0, x19
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB5_8:
	mov	x0, x21
	bl	_Unwind_Resume
.Lfunc_end5:
	.size	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E, .Lfunc_end5-_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E","a",@progbits
	.p2align	2, 0x0
GCC_except_table5:
.Lexception2:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end2-.Lcst_begin2
.Lcst_begin2:
	.uleb128 .Ltmp109-.Lfunc_begin2
	.uleb128 .Ltmp110-.Ltmp109
	.uleb128 .Ltmp111-.Lfunc_begin2
	.byte	0
	.uleb128 .Ltmp110-.Lfunc_begin2
	.uleb128 .Lfunc_end5-.Ltmp110
	.byte	0
	.byte	0
.Lcst_end2:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E,@function
_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E:
.Lfunc_begin3:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception3
	stp	x29, x30, [sp, #-48]!
	.cfi_def_cfa_offset 48
	str	x21, [sp, #16]
	stp	x20, x19, [sp, #32]
	mov	x29, sp
	.cfi_def_cfa w29, 48
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -32
	.cfi_offset w30, -40
	.cfi_offset w29, -48
	.cfi_remember_state
	ldr	x8, [x1]
	mov	x20, x1
	mov	x19, x0
	cbz	x8, .LBB6_2
.Ltmp112:
	mov	x0, x19
	blr	x8
.Ltmp113:
.LBB6_2:
	ldr	x1, [x20, #8]
	cbz	x1, .LBB6_4
	ldr	x2, [x20, #16]
	mov	x0, x19
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB6_4:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB6_5:
	.cfi_restore_state
.Ltmp114:
	ldr	x1, [x20, #8]
	mov	x21, x0
	cbz	x1, .LBB6_7
	ldr	x2, [x20, #16]
	mov	x0, x19
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB6_7:
	mov	x0, x21
	bl	_Unwind_Resume
.Lfunc_end6:
	.size	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E, .Lfunc_end6-_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E","a",@progbits
	.p2align	2, 0x0
GCC_except_table6:
.Lexception3:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end3-.Lcst_begin3
.Lcst_begin3:
	.uleb128 .Ltmp112-.Lfunc_begin3
	.uleb128 .Ltmp113-.Ltmp112
	.uleb128 .Ltmp114-.Lfunc_begin3
	.byte	0
	.uleb128 .Ltmp113-.Lfunc_begin3
	.uleb128 .Lfunc_end6-.Ltmp113
	.byte	0
	.byte	0
.Lcst_end3:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE,@function
_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE:
.Lfunc_begin4:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception4
	stp	x29, x30, [sp, #-64]!
	.cfi_def_cfa_offset 64
	stp	x24, x23, [sp, #16]
	stp	x22, x21, [sp, #32]
	stp	x20, x19, [sp, #48]
	mov	x29, sp
	.cfi_def_cfa w29, 64
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -24
	.cfi_offset w22, -32
	.cfi_offset w23, -40
	.cfi_offset w24, -48
	.cfi_offset w30, -56
	.cfi_offset w29, -64
	.cfi_remember_state
	ldp	x19, x23, [x0, #8]
	mov	x20, x0
	cbz	x23, .LBB7_7
	add	x24, x19, #24
	b	.LBB7_3
.LBB7_2:
	subs	x23, x23, #1
	add	x24, x24, #16
	b.eq	.LBB7_7
.LBB7_3:
	ldp	x22, x21, [x24, #-24]
	ldr	x8, [x21]
	cbz	x8, .LBB7_5
.Ltmp115:
	mov	x0, x22
	blr	x8
.Ltmp116:
.LBB7_5:
	ldr	x1, [x21, #8]
	cbz	x1, .LBB7_2
	ldr	x2, [x21, #16]
	mov	x0, x22
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
	b	.LBB7_2
.LBB7_7:
	ldr	x8, [x20]
	cbz	x8, .LBB7_9
	lsl	x1, x8, #4
	mov	x0, x19
	mov	w2, #8
	.cfi_def_cfa wsp, 64
	ldp	x20, x19, [sp, #48]
	ldp	x22, x21, [sp, #32]
	ldp	x24, x23, [sp, #16]
	ldp	x29, x30, [sp], #64
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB7_9:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 64
	ldp	x20, x19, [sp, #48]
	ldp	x22, x21, [sp, #32]
	ldp	x24, x23, [sp, #16]
	ldp	x29, x30, [sp], #64
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w22
	.cfi_restore w23
	.cfi_restore w24
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB7_10:
	.cfi_restore_state
.Ltmp117:
	ldr	x1, [x21, #8]
	mov	x8, x21
	mov	x21, x0
	cbz	x1, .LBB7_12
	ldr	x2, [x8, #16]
	mov	x0, x22
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB7_12:
	subs	x23, x23, #1
	b.eq	.LBB7_14
	ldp	x0, x1, [x24, #-8]
	add	x24, x24, #16
.Ltmp118:
	bl	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E
.Ltmp119:
	b	.LBB7_12
.LBB7_14:
	ldr	x8, [x20]
	cbz	x8, .LBB7_16
	lsl	x1, x8, #4
	mov	x0, x19
	mov	w2, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB7_16:
	mov	x0, x21
	bl	_Unwind_Resume
.LBB7_17:
.Ltmp120:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.Lfunc_end7:
	.size	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE, .Lfunc_end7-_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE","a",@progbits
	.p2align	2, 0x0
GCC_except_table7:
.Lexception4:
	.byte	255
	.byte	156
	.uleb128 .Lttbase2-.Lttbaseref2
.Lttbaseref2:
	.byte	1
	.uleb128 .Lcst_end4-.Lcst_begin4
.Lcst_begin4:
	.uleb128 .Ltmp115-.Lfunc_begin4
	.uleb128 .Ltmp116-.Ltmp115
	.uleb128 .Ltmp117-.Lfunc_begin4
	.byte	0
	.uleb128 .Ltmp118-.Lfunc_begin4
	.uleb128 .Ltmp119-.Ltmp118
	.uleb128 .Ltmp120-.Lfunc_begin4
	.byte	1
	.uleb128 .Ltmp119-.Lfunc_begin4
	.uleb128 .Lfunc_end7-.Ltmp119
	.byte	0
	.byte	0
.Lcst_end4:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase2:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E,@function
_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E:
.Lfunc_begin5:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception5
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	ldr	x8, [x0]
	cbz	x8, .LBB8_6
	ldr	x19, [x0, #8]
	cbz	x19, .LBB8_6
	ldr	x20, [x0, #16]
	ldr	x8, [x20]
	cbz	x8, .LBB8_4
.Ltmp121:
	mov	x0, x19
	blr	x8
.Ltmp122:
.LBB8_4:
	ldr	x1, [x20, #8]
	cbz	x1, .LBB8_6
	ldr	x2, [x20, #16]
	mov	x0, x19
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB8_6:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB8_7:
	.cfi_restore_state
.Ltmp123:
	ldr	x1, [x20, #8]
	mov	x8, x20
	mov	x20, x0
	cbz	x1, .LBB8_9
	ldr	x2, [x8, #16]
	mov	x0, x19
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB8_9:
	mov	x0, x20
	bl	_Unwind_Resume
.Lfunc_end8:
	.size	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E, .Lfunc_end8-_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E","a",@progbits
	.p2align	2, 0x0
GCC_except_table8:
.Lexception5:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end5-.Lcst_begin5
.Lcst_begin5:
	.uleb128 .Ltmp121-.Lfunc_begin5
	.uleb128 .Ltmp122-.Ltmp121
	.uleb128 .Ltmp123-.Lfunc_begin5
	.byte	0
	.uleb128 .Ltmp122-.Lfunc_begin5
	.uleb128 .Lfunc_end8-.Ltmp122
	.byte	0
	.byte	0
.Lcst_end5:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E,@function
_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E:
.Lfunc_begin6:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception6
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	mov	x19, x0
.Ltmp124:
	bl	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E
.Ltmp125:
	ldr	x1, [x19, #32]!
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB9_3
	mov	x0, x19
	dmb	ishld
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.LBB9_3:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB9_4:
	.cfi_restore_state
.Ltmp126:
	ldr	x1, [x19, #32]!
	mov	x20, x0
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB9_6
	dmb	ishld
.Ltmp127:
	mov	x0, x19
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
.Ltmp128:
.LBB9_6:
	mov	x0, x20
	bl	_Unwind_Resume
.LBB9_7:
.Ltmp129:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.Lfunc_end9:
	.size	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E, .Lfunc_end9-_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E","a",@progbits
	.p2align	2, 0x0
GCC_except_table9:
.Lexception6:
	.byte	255
	.byte	156
	.uleb128 .Lttbase3-.Lttbaseref3
.Lttbaseref3:
	.byte	1
	.uleb128 .Lcst_end6-.Lcst_begin6
.Lcst_begin6:
	.uleb128 .Ltmp124-.Lfunc_begin6
	.uleb128 .Ltmp125-.Ltmp124
	.uleb128 .Ltmp126-.Lfunc_begin6
	.byte	0
	.uleb128 .Ltmp125-.Lfunc_begin6
	.uleb128 .Ltmp127-.Ltmp125
	.byte	0
	.byte	0
	.uleb128 .Ltmp127-.Lfunc_begin6
	.uleb128 .Ltmp128-.Ltmp127
	.uleb128 .Ltmp129-.Lfunc_begin6
	.byte	1
	.uleb128 .Ltmp128-.Lfunc_begin6
	.uleb128 .Lfunc_end9-.Ltmp128
	.byte	0
	.byte	0
.Lcst_end6:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase3:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E,@function
_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E:
.Lfunc_begin7:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception7
	stp	x29, x30, [sp, #-48]!
	.cfi_def_cfa_offset 48
	str	x21, [sp, #16]
	stp	x20, x19, [sp, #32]
	mov	x29, sp
	.cfi_def_cfa w29, 48
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w21, -32
	.cfi_offset w30, -40
	.cfi_offset w29, -48
	.cfi_remember_state
	ldr	x19, [x0]
	and	x8, x19, #0x3
	sub	x9, x8, #2
	cmp	x9, #2
	ccmp	x8, #0, #4, hs
	b.ne	.LBB10_2
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB10_2:
	.cfi_restore_state
	.cfi_remember_state
	ldr	x20, [x19, #-1]!
	ldr	x21, [x19, #8]
	ldr	x8, [x21]
	cbz	x8, .LBB10_4
.Ltmp130:
	mov	x0, x20
	blr	x8
.Ltmp131:
.LBB10_4:
	ldr	x1, [x21, #8]
	cbz	x1, .LBB10_6
	ldr	x2, [x21, #16]
	mov	x0, x20
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB10_6:
	mov	x0, x19
	mov	w1, #24
	mov	w2, #8
	.cfi_def_cfa wsp, 48
	ldp	x20, x19, [sp, #32]
	ldr	x21, [sp, #16]
	ldp	x29, x30, [sp], #48
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w21
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB10_7:
	.cfi_restore_state
.Ltmp132:
	ldr	x1, [x21, #8]
	mov	x8, x21
	mov	x21, x0
	cbz	x1, .LBB10_9
	ldr	x2, [x8, #16]
	mov	x0, x20
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB10_9:
	mov	x0, x19
	mov	w1, #24
	mov	w2, #8
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
	mov	x0, x21
	bl	_Unwind_Resume
.Lfunc_end10:
	.size	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E, .Lfunc_end10-_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E","a",@progbits
	.p2align	2, 0x0
GCC_except_table10:
.Lexception7:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end7-.Lcst_begin7
.Lcst_begin7:
	.uleb128 .Ltmp130-.Lfunc_begin7
	.uleb128 .Ltmp131-.Ltmp130
	.uleb128 .Ltmp132-.Lfunc_begin7
	.byte	0
	.uleb128 .Ltmp131-.Lfunc_begin7
	.uleb128 .Lfunc_end10-.Ltmp131
	.byte	0
	.byte	0
.Lcst_end7:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E,@function
_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E:
.Lfunc_begin8:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception8
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	ldr	x1, [x0]
	mov	x19, x0
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB11_2
	dmb	ishld
.Ltmp133:
	mov	x0, x19
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp134:
.LBB11_2:
	ldp	x19, x20, [x19, #8]
	ldr	x8, [x20]
	cbz	x8, .LBB11_4
.Ltmp139:
	mov	x0, x19
	blr	x8
.Ltmp140:
.LBB11_4:
	ldr	x1, [x20, #8]
	cbz	x1, .LBB11_6
	ldr	x2, [x20, #16]
	mov	x0, x19
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB11_6:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB11_7:
	.cfi_restore_state
.Ltmp135:
	ldp	x8, x1, [x19, #8]
	mov	x20, x0
.Ltmp136:
	mov	x0, x8
	bl	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hcd2d0c9ae9964925E
.Ltmp137:
	b	.LBB11_11
.LBB11_8:
.Ltmp138:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB11_9:
.Ltmp141:
	ldr	x1, [x20, #8]
	mov	x8, x20
	mov	x20, x0
	cbz	x1, .LBB11_11
	ldr	x2, [x8, #16]
	mov	x0, x19
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB11_11:
	mov	x0, x20
	bl	_Unwind_Resume
.Lfunc_end11:
	.size	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E, .Lfunc_end11-_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17h5d18557ce4f48311E","a",@progbits
	.p2align	2, 0x0
GCC_except_table11:
.Lexception8:
	.byte	255
	.byte	156
	.uleb128 .Lttbase4-.Lttbaseref4
.Lttbaseref4:
	.byte	1
	.uleb128 .Lcst_end8-.Lcst_begin8
.Lcst_begin8:
	.uleb128 .Lfunc_begin8-.Lfunc_begin8
	.uleb128 .Ltmp133-.Lfunc_begin8
	.byte	0
	.byte	0
	.uleb128 .Ltmp133-.Lfunc_begin8
	.uleb128 .Ltmp134-.Ltmp133
	.uleb128 .Ltmp135-.Lfunc_begin8
	.byte	0
	.uleb128 .Ltmp139-.Lfunc_begin8
	.uleb128 .Ltmp140-.Ltmp139
	.uleb128 .Ltmp141-.Lfunc_begin8
	.byte	0
	.uleb128 .Ltmp136-.Lfunc_begin8
	.uleb128 .Ltmp137-.Ltmp136
	.uleb128 .Ltmp138-.Lfunc_begin8
	.byte	1
	.uleb128 .Ltmp137-.Lfunc_begin8
	.uleb128 .Lfunc_end11-.Ltmp137
	.byte	0
	.byte	0
.Lcst_end8:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase4:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E,@function
_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E:
.Lfunc_begin9:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception9
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	mov	x19, x0
.Ltmp142:
	add	x0, x0, #24
	bl	_RNvXNtNtCshxTglP3SOjd_3std6thread9spawnhookNtB2_10SpawnHooksNtNtNtCs6Hz1PecaLG4_4core3ops4drop4Drop4drop
.Ltmp143:
	ldur	x1, [x19, #24]
	cbz	x1, .LBB12_4
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB12_4
	dmb	ishld
.Ltmp148:
	add	x0, x19, #24
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread9spawnhook9SpawnHookE9drop_slowBM_
.Ltmp149:
.LBB12_4:
	mov	x0, x19
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE
.LBB12_5:
	.cfi_restore_state
.Ltmp150:
	mov	x20, x0
	b	.LBB12_9
.LBB12_6:
.Ltmp144:
	ldur	x1, [x19, #24]
	mov	x20, x0
	cbz	x1, .LBB12_9
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB12_9
	dmb	ishld
.Ltmp145:
	add	x0, x19, #24
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread9spawnhook9SpawnHookE9drop_slowBM_
.Ltmp146:
.LBB12_9:
.Ltmp151:
	mov	x0, x19
	bl	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17h508c029581eed11bE
.Ltmp152:
	mov	x0, x20
	bl	_Unwind_Resume
.LBB12_11:
.Ltmp147:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB12_12:
.Ltmp153:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.Lfunc_end12:
	.size	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E, .Lfunc_end12-_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17h88f97e20c24aedd8E","a",@progbits
	.p2align	2, 0x0
GCC_except_table12:
.Lexception9:
	.byte	255
	.byte	156
	.uleb128 .Lttbase5-.Lttbaseref5
.Lttbaseref5:
	.byte	1
	.uleb128 .Lcst_end9-.Lcst_begin9
.Lcst_begin9:
	.uleb128 .Ltmp142-.Lfunc_begin9
	.uleb128 .Ltmp143-.Ltmp142
	.uleb128 .Ltmp144-.Lfunc_begin9
	.byte	0
	.uleb128 .Ltmp143-.Lfunc_begin9
	.uleb128 .Ltmp148-.Ltmp143
	.byte	0
	.byte	0
	.uleb128 .Ltmp148-.Lfunc_begin9
	.uleb128 .Ltmp149-.Ltmp148
	.uleb128 .Ltmp150-.Lfunc_begin9
	.byte	0
	.uleb128 .Ltmp149-.Lfunc_begin9
	.uleb128 .Ltmp145-.Ltmp149
	.byte	0
	.byte	0
	.uleb128 .Ltmp145-.Lfunc_begin9
	.uleb128 .Ltmp146-.Ltmp145
	.uleb128 .Ltmp147-.Lfunc_begin9
	.byte	1
	.uleb128 .Ltmp151-.Lfunc_begin9
	.uleb128 .Ltmp152-.Ltmp151
	.uleb128 .Ltmp153-.Lfunc_begin9
	.byte	1
	.uleb128 .Ltmp152-.Lfunc_begin9
	.uleb128 .Lfunc_end12-.Ltmp152
	.byte	0
	.byte	0
.Lcst_end9:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase5:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE","ax",@progbits
	.p2align	2
	.type	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE,@function
_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE:
.Lfunc_begin10:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception10
	sub	sp, sp, #96
	.cfi_def_cfa_offset 96
	stp	x29, x30, [sp, #16]
	str	x25, [sp, #32]
	stp	x24, x23, [sp, #48]
	stp	x22, x21, [sp, #64]
	stp	x20, x19, [sp, #80]
	add	x29, sp, #16
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
	mov	x19, x0
	mov	x20, x0
	ldp	x24, x21, [x19, #8]!
	cmp	x21, #0
	cset	w25, ne
	cbz	x24, .LBB13_6
	cbz	x21, .LBB13_6
	ldr	x23, [x20, #24]
	ldr	x8, [x23]
	cbz	x8, .LBB13_4
.Ltmp154:
	mov	x0, x21
	blr	x8
.Ltmp155:
.LBB13_4:
	ldr	x1, [x23, #8]
	cbz	x1, .LBB13_6
	ldr	x2, [x23, #16]
	mov	x0, x21
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB13_6:
	str	xzr, [x19]
.LBB13_7:
	ldr	x22, [x20]
	cbz	x22, .LBB13_11
.Ltmp170:
	add	x0, x22, #16
	and	w1, w24, w25
	bl	_RNvMNtNtCshxTglP3SOjd_3std6thread6scopedNtB2_9ScopeData29decrement_num_running_threads
.Ltmp171:
	mov	x0, #-1
	mov	x1, x22
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB13_11
	dmb	ishld
.Ltmp175:
	mov	x0, x20
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
.Ltmp176:
.LBB13_11:
	ldr	x8, [x19]
	cbz	x8, .LBB13_17
	ldr	x19, [x20, #16]
	cbz	x19, .LBB13_17
	ldr	x20, [x20, #24]
	ldr	x8, [x20]
	cbz	x8, .LBB13_15
.Ltmp181:
	mov	x0, x19
	blr	x8
.Ltmp182:
.LBB13_15:
	ldr	x1, [x20, #8]
	cbz	x1, .LBB13_17
	ldr	x2, [x20, #16]
	mov	x0, x19
	.cfi_def_cfa wsp, 96
	ldp	x20, x19, [sp, #80]
	ldr	x25, [sp, #32]
	ldp	x22, x21, [sp, #64]
	ldp	x24, x23, [sp, #48]
	ldp	x29, x30, [sp, #16]
	add	sp, sp, #96
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
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB13_17:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 96
	ldp	x20, x19, [sp, #80]
	ldr	x25, [sp, #32]
	ldp	x22, x21, [sp, #64]
	ldp	x24, x23, [sp, #48]
	ldp	x29, x30, [sp, #16]
	add	sp, sp, #96
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
	ret
.LBB13_18:
	.cfi_restore_state
.Ltmp183:
	ldr	x1, [x20, #8]
	mov	x21, x0
	cbz	x1, .LBB13_38
	ldr	x2, [x20, #16]
	mov	x0, x19
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
	mov	x0, x21
	bl	_Unwind_Resume
.LBB13_20:
.Ltmp156:
	ldr	x1, [x23, #8]
	mov	x22, x0
	cbz	x1, .LBB13_22
	ldr	x2, [x23, #16]
	mov	x0, x21
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB13_22:
	str	xzr, [x19]
.Ltmp157:
	mov	x0, x22
	bl	_RNvNvNtCshxTglP3SOjd_3std9panicking12catch_unwind7cleanup
.Ltmp158:
	mov	x22, x0
	cbz	x0, .LBB13_7
.Ltmp160:
	mov	x23, x1
	adrp	x1, .Lanon.8237690aa1ed0b145f80bff47c997adc.16
	add	x1, x1, :lo12:.Lanon.8237690aa1ed0b145f80bff47c997adc.16
	add	x0, x29, #31
	mov	w2, #62
	bl	_ZN3std2io5Write9write_all17h9313e362643cf870E
.Ltmp161:
	str	x0, [sp, #8]
	cbz	x0, .LBB13_27
.Ltmp162:
	add	x0, sp, #8
	bl	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E
.Ltmp163:
.LBB13_27:
.Ltmp164:
	bl	_RNvNtCshxTglP3SOjd_3std7process5abort
.Ltmp165:
	brk	#0x1
.LBB13_29:
.Ltmp166:
	mov	x21, x0
.Ltmp167:
	mov	x0, x22
	mov	x1, x23
	bl	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17hbc2f0c1946265e45E
.Ltmp168:
	ldr	x22, [x20]
	cbnz	x22, .LBB13_35
	b	.LBB13_37
.LBB13_31:
.Ltmp169:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.LBB13_32:
.Ltmp159:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking19panic_cannot_unwind
.LBB13_33:
.Ltmp177:
	mov	x21, x0
	b	.LBB13_37
.LBB13_34:
.Ltmp172:
	mov	x21, x0
.LBB13_35:
	mov	x0, #-1
	mov	x1, x22
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB13_37
	dmb	ishld
.Ltmp173:
	mov	x0, x20
	bl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
.Ltmp174:
.LBB13_37:
.Ltmp178:
	mov	x0, x19
	bl	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17he4575e0ad9a52278E
.Ltmp179:
.LBB13_38:
	mov	x0, x21
	bl	_Unwind_Resume
.LBB13_39:
.Ltmp180:
	bl	_RNvNtCs6Hz1PecaLG4_4core9panicking16panic_in_cleanup
.Lfunc_end13:
	.size	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE, .Lfunc_end13-_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE","a",@progbits
	.p2align	2, 0x0
GCC_except_table13:
.Lexception10:
	.byte	255
	.byte	156
	.uleb128 .Lttbase6-.Lttbaseref6
.Lttbaseref6:
	.byte	1
	.uleb128 .Lcst_end10-.Lcst_begin10
.Lcst_begin10:
	.uleb128 .Ltmp154-.Lfunc_begin10
	.uleb128 .Ltmp155-.Ltmp154
	.uleb128 .Ltmp156-.Lfunc_begin10
	.byte	5
	.uleb128 .Ltmp170-.Lfunc_begin10
	.uleb128 .Ltmp171-.Ltmp170
	.uleb128 .Ltmp172-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp171-.Lfunc_begin10
	.uleb128 .Ltmp175-.Ltmp171
	.byte	0
	.byte	0
	.uleb128 .Ltmp175-.Lfunc_begin10
	.uleb128 .Ltmp176-.Ltmp175
	.uleb128 .Ltmp177-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp181-.Lfunc_begin10
	.uleb128 .Ltmp182-.Ltmp181
	.uleb128 .Ltmp183-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp182-.Lfunc_begin10
	.uleb128 .Ltmp157-.Ltmp182
	.byte	0
	.byte	0
	.uleb128 .Ltmp157-.Lfunc_begin10
	.uleb128 .Ltmp158-.Ltmp157
	.uleb128 .Ltmp159-.Lfunc_begin10
	.byte	1
	.uleb128 .Ltmp160-.Lfunc_begin10
	.uleb128 .Ltmp165-.Ltmp160
	.uleb128 .Ltmp166-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp167-.Lfunc_begin10
	.uleb128 .Ltmp168-.Ltmp167
	.uleb128 .Ltmp169-.Lfunc_begin10
	.byte	1
	.uleb128 .Ltmp168-.Lfunc_begin10
	.uleb128 .Ltmp173-.Ltmp168
	.byte	0
	.byte	0
	.uleb128 .Ltmp173-.Lfunc_begin10
	.uleb128 .Ltmp179-.Ltmp173
	.uleb128 .Ltmp180-.Lfunc_begin10
	.byte	1
	.uleb128 .Ltmp179-.Lfunc_begin10
	.uleb128 .Lfunc_end13-.Ltmp179
	.byte	0
	.byte	0
.Lcst_end10:
	.byte	127
	.byte	0
	.byte	0
	.byte	0
	.byte	1
	.byte	125
	.p2align	2, 0x0
	.xword	0
.Lttbase6:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E","ax",@progbits
	.globl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
	.p2align	2
	.type	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E,@function
_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E:
.Lfunc_begin11:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception11
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	ldr	x19, [x0]
.Ltmp184:
	add	x0, x19, #16
	bl	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hff3737a08df1108aE
.Ltmp185:
	cmn	x19, #1
	b.eq	.LBB14_4
	add	x1, x19, #8
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB14_4
	mov	x0, x19
	mov	w1, #48
	mov	w2, #8
	dmb	ishld
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB14_4:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB14_5:
	.cfi_restore_state
.Ltmp186:
	cmn	x19, #1
	mov	x20, x0
	b.eq	.LBB14_8
	add	x1, x19, #8
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB14_8
	mov	x0, x19
	mov	w1, #48
	mov	w2, #8
	dmb	ishld
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB14_8:
	mov	x0, x20
	bl	_Unwind_Resume
.Lfunc_end14:
	.size	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E, .Lfunc_end14-_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E
	.cfi_endproc
	.section	".gcc_except_table._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h0909a83eb53abcc8E","a",@progbits
	.p2align	2, 0x0
GCC_except_table14:
.Lexception11:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end11-.Lcst_begin11
.Lcst_begin11:
	.uleb128 .Ltmp184-.Lfunc_begin11
	.uleb128 .Ltmp185-.Ltmp184
	.uleb128 .Ltmp186-.Lfunc_begin11
	.byte	0
	.uleb128 .Ltmp185-.Lfunc_begin11
	.uleb128 .Lfunc_end14-.Ltmp185
	.byte	0
	.byte	0
.Lcst_end11:
	.p2align	2, 0x0

	.section	".text._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E","ax",@progbits
	.globl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
	.p2align	2
	.type	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E,@function
_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E:
.Lfunc_begin12:
	.cfi_startproc
	.cfi_personality 156, DW.ref.rust_eh_personality
	.cfi_lsda 28, .Lexception12
	stp	x29, x30, [sp, #-32]!
	.cfi_def_cfa_offset 32
	stp	x20, x19, [sp, #16]
	mov	x29, sp
	.cfi_def_cfa w29, 32
	.cfi_offset w19, -8
	.cfi_offset w20, -16
	.cfi_offset w30, -24
	.cfi_offset w29, -32
	.cfi_remember_state
	ldr	x19, [x0]
	mov	x0, #-1
	mov	x20, x19
	ldr	x1, [x20, #16]!
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB15_2
	dmb	ishld
.Ltmp187:
	mov	x0, x20
	bl	_RNvMsn_NtCs3U9RWQJh2dM_5alloc4syncINtB5_3ArcNtNtNtCshxTglP3SOjd_3std6thread6thread5InnerNtNtBM_5alloc6SystemE9drop_slowBM_
.Ltmp188:
.LBB15_2:
	cmn	x19, #1
	b.eq	.LBB15_5
	add	x1, x19, #8
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB15_5
	mov	x0, x19
	mov	w1, #40
	mov	w2, #8
	dmb	ishld
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	b	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB15_5:
	.cfi_restore_state
	.cfi_remember_state
	.cfi_def_cfa wsp, 32
	ldp	x20, x19, [sp, #16]
	ldp	x29, x30, [sp], #32
	.cfi_def_cfa_offset 0
	.cfi_restore w19
	.cfi_restore w20
	.cfi_restore w30
	.cfi_restore w29
	ret
.LBB15_6:
	.cfi_restore_state
.Ltmp189:
	cmn	x19, #1
	mov	x20, x0
	b.eq	.LBB15_9
	add	x1, x19, #8
	mov	x0, #-1
	bl	__aarch64_ldadd8_rel
	cmp	x0, #1
	b.ne	.LBB15_9
	mov	x0, x19
	mov	w1, #40
	mov	w2, #8
	dmb	ishld
	bl	_RNvCsfLfy6EI15iL_7___rustc14___rust_dealloc
.LBB15_9:
	mov	x0, x20
	bl	_Unwind_Resume
.Lfunc_end15:
	.size	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E, .Lfunc_end15-_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E
	.cfi_endproc
	.section	".gcc_except_table._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h4f7d58032cb30822E","a",@progbits
	.p2align	2, 0x0
GCC_except_table15:
.Lexception12:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end12-.Lcst_begin12
.Lcst_begin12:
	.uleb128 .Lfunc_begin12-.Lfunc_begin12
	.uleb128 .Ltmp187-.Lfunc_begin12
	.byte	0
	.byte	0
	.uleb128 .Ltmp187-.Lfunc_begin12
	.uleb128 .Ltmp188-.Ltmp187
	.uleb128 .Ltmp189-.Lfunc_begin12
	.byte	0
	.uleb128 .Ltmp188-.Lfunc_begin12
	.uleb128 .Lfunc_end15-.Ltmp188
	.byte	0
	.byte	0
.Lcst_end12:
	.p2align	2, 0x0

	.section	.text.compiler_fence_seqcst,"ax",@progbits
	.globl	compiler_fence_seqcst
	.p2align	2
	.type	compiler_fence_seqcst,@function
compiler_fence_seqcst:
	.cfi_startproc
	//MEMBARRIER
	ret
.Lfunc_end16:
	.size	compiler_fence_seqcst, .Lfunc_end16-compiler_fence_seqcst
	.cfi_endproc

	.section	.text.fence_acqrel,"ax",@progbits
	.globl	fence_acqrel
	.p2align	2
	.type	fence_acqrel,@function
fence_acqrel:
	.cfi_startproc
	dmb	ish
	ret
.Lfunc_end17:
	.size	fence_acqrel, .Lfunc_end17-fence_acqrel
	.cfi_endproc

	.section	.text.fence_acquire,"ax",@progbits
	.globl	fence_acquire
	.p2align	2
	.type	fence_acquire,@function
fence_acquire:
	.cfi_startproc
	dmb	ishld
	ret
.Lfunc_end18:
	.size	fence_acquire, .Lfunc_end18-fence_acquire
	.cfi_endproc

	.section	.text.fence_release,"ax",@progbits
	.globl	fence_release
	.p2align	2
	.type	fence_release,@function
fence_release:
	.cfi_startproc
	dmb	ish
	ret
.Lfunc_end19:
	.size	fence_release, .Lfunc_end19-fence_release
	.cfi_endproc

	.section	.text.fence_seqcst,"ax",@progbits
	.globl	fence_seqcst
	.p2align	2
	.type	fence_seqcst,@function
fence_seqcst:
	.cfi_startproc
	dmb	ish
	ret
.Lfunc_end20:
	.size	fence_seqcst, .Lfunc_end20-fence_seqcst
	.cfi_endproc

	.section	.text.fetch_add_acqrel,"ax",@progbits
	.globl	fetch_add_acqrel
	.p2align	2
	.type	fetch_add_acqrel,@function
fetch_add_acqrel:
	.cfi_startproc
	stp	x29, x30, [sp, #-16]!
	.cfi_def_cfa_offset 16
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x8, x0
	mov	x0, x1
	mov	x1, x8
	bl	__aarch64_ldadd8_acq_rel
	.cfi_def_cfa wsp, 16
	ldp	x29, x30, [sp], #16
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end21:
	.size	fetch_add_acqrel, .Lfunc_end21-fetch_add_acqrel
	.cfi_endproc

	.section	.text.fetch_add_acquire,"ax",@progbits
	.globl	fetch_add_acquire
	.p2align	2
	.type	fetch_add_acquire,@function
fetch_add_acquire:
	.cfi_startproc
	stp	x29, x30, [sp, #-16]!
	.cfi_def_cfa_offset 16
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x8, x0
	mov	x0, x1
	mov	x1, x8
	bl	__aarch64_ldadd8_acq
	.cfi_def_cfa wsp, 16
	ldp	x29, x30, [sp], #16
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end22:
	.size	fetch_add_acquire, .Lfunc_end22-fetch_add_acquire
	.cfi_endproc

	.section	.text.fetch_add_relaxed,"ax",@progbits
	.globl	fetch_add_relaxed
	.p2align	2
	.type	fetch_add_relaxed,@function
fetch_add_relaxed:
	.cfi_startproc
	stp	x29, x30, [sp, #-16]!
	.cfi_def_cfa_offset 16
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x8, x0
	mov	x0, x1
	mov	x1, x8
	bl	__aarch64_ldadd8_relax
	.cfi_def_cfa wsp, 16
	ldp	x29, x30, [sp], #16
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end23:
	.size	fetch_add_relaxed, .Lfunc_end23-fetch_add_relaxed
	.cfi_endproc

	.section	.text.fetch_add_release,"ax",@progbits
	.globl	fetch_add_release
	.p2align	2
	.type	fetch_add_release,@function
fetch_add_release:
	.cfi_startproc
	stp	x29, x30, [sp, #-16]!
	.cfi_def_cfa_offset 16
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x8, x0
	mov	x0, x1
	mov	x1, x8
	bl	__aarch64_ldadd8_rel
	.cfi_def_cfa wsp, 16
	ldp	x29, x30, [sp], #16
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end24:
	.size	fetch_add_release, .Lfunc_end24-fetch_add_release
	.cfi_endproc

	.section	.text.fetch_add_seqcst,"ax",@progbits
	.globl	fetch_add_seqcst
	.p2align	2
	.type	fetch_add_seqcst,@function
fetch_add_seqcst:
	.cfi_startproc
	stp	x29, x30, [sp, #-16]!
	.cfi_def_cfa_offset 16
	mov	x29, sp
	.cfi_def_cfa w29, 16
	.cfi_offset w30, -8
	.cfi_offset w29, -16
	mov	x8, x0
	mov	x0, x1
	mov	x1, x8
	bl	__aarch64_ldadd8_acq_rel
	.cfi_def_cfa wsp, 16
	ldp	x29, x30, [sp], #16
	.cfi_def_cfa_offset 0
	.cfi_restore w30
	.cfi_restore w29
	ret
.Lfunc_end25:
	.size	fetch_add_seqcst, .Lfunc_end25-fetch_add_seqcst
	.cfi_endproc

	.section	.text.load_acquire,"ax",@progbits
	.globl	load_acquire
	.p2align	2
	.type	load_acquire,@function
load_acquire:
	.cfi_startproc
	ldar	x0, [x0]
	ret
.Lfunc_end26:
	.size	load_acquire, .Lfunc_end26-load_acquire
	.cfi_endproc

	.section	.text.load_relaxed,"ax",@progbits
	.globl	load_relaxed
	.p2align	2
	.type	load_relaxed,@function
load_relaxed:
	.cfi_startproc
	ldr	x0, [x0]
	ret
.Lfunc_end27:
	.size	load_relaxed, .Lfunc_end27-load_relaxed
	.cfi_endproc

	.section	.text.load_seqcst,"ax",@progbits
	.globl	load_seqcst
	.p2align	2
	.type	load_seqcst,@function
load_seqcst:
	.cfi_startproc
	ldar	x0, [x0]
	ret
.Lfunc_end28:
	.size	load_seqcst, .Lfunc_end28-load_seqcst
	.cfi_endproc

	.section	.text.store_relaxed,"ax",@progbits
	.globl	store_relaxed
	.p2align	2
	.type	store_relaxed,@function
store_relaxed:
	.cfi_startproc
	str	x1, [x0]
	ret
.Lfunc_end29:
	.size	store_relaxed, .Lfunc_end29-store_relaxed
	.cfi_endproc

	.section	.text.store_release,"ax",@progbits
	.globl	store_release
	.p2align	2
	.type	store_release,@function
store_release:
	.cfi_startproc
	stlr	x1, [x0]
	ret
.Lfunc_end30:
	.size	store_release, .Lfunc_end30-store_release
	.cfi_endproc

	.section	.text.store_seqcst,"ax",@progbits
	.globl	store_seqcst
	.p2align	2
	.type	store_seqcst,@function
store_seqcst:
	.cfi_startproc
	stlr	x1, [x0]
	ret
.Lfunc_end31:
	.size	store_seqcst, .Lfunc_end31-store_seqcst
	.cfi_endproc

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.0,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.0,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.0:
	.ascii	"rounds must be nonzero"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.0, 22

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.1,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.8237690aa1ed0b145f80bff47c997adc.1:
	.asciz	"/tmp/topic22-5f93fdb-arm/source/topics/022-cpu-memory-model-atomic-lowering/src/lib.rs"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.1, 87

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.2,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.2,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.2:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.1
	.asciz	"V\000\000\000\000\000\000\000\252\000\000\000\005\000\000"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.2, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.3,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.3,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.3:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.1
	.asciz	"V\000\000\000\000\000\000\000\257\000\000\000\005\000\000"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.3, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.4,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.4,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.4:
	.ascii	"failed to spawn thread"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.4, 22

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.5,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.8237690aa1ed0b145f80bff47c997adc.5:
	.asciz	"/local/home/ahrav/.rustup/toolchains/stable-aarch64-unknown-linux-gnu/lib/rustlib/src/rust/library/std/src/thread/scoped.rs"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.5, 124

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.6,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.6,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.6:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.5
	.asciz	"{\000\000\000\000\000\000\000\316\000\000\000.\000\000"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.6, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.7,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.7,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.7:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.1
	.asciz	"V\000\000\000\000\000\000\000\276\000\000\000\r\000\000"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.7, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.8,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.8237690aa1ed0b145f80bff47c997adc.8:
	.asciz	"/local/home/ahrav/.rustup/toolchains/stable-aarch64-unknown-linux-gnu/lib/rustlib/src/rust/library/std/src/io/mod.rs"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.8, 117

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.9,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.9,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.9:
	.ascii	"failed to write whole buffer"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.9, 28

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.10,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.10,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.10:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.9
	.ascii	"\034\000\000\000\000\000\000\000\027"
	.zero	7
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.10, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.11,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.11,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.11:
	.xword	.Lanon.8237690aa1ed0b145f80bff47c997adc.8
	.asciz	"t\000\000\000\000\000\000\000Y\007\000\000$\000\000"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.11, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.12,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.12,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.12:
	.ascii	"a scoped thread panicked"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.12, 24

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.13,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.13,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.13:
	.xword	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb77ca42d43bc2c88E
	.asciz	"H\000\000\000\000\000\000\000\b\000\000\000\000\000\000"
	.xword	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17h3c4419d3f19c734dE
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.13, 32

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.14,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.14,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.14:
	.ascii	"RUST_MIN_STACK"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.14, 14

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.15,@object
	.section	.data.rel.ro..Lanon.8237690aa1ed0b145f80bff47c997adc.15,"aw",@progbits
	.p2align	3, 0x0
.Lanon.8237690aa1ed0b145f80bff47c997adc.15:
	.xword	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h1f42686a6b9423b6E
	.asciz	"\b\000\000\000\000\000\000\000\b\000\000\000\000\000\000"
	.xword	_RNvXNtNtCshxTglP3SOjd_3std2io5errorNtB2_5ErrorNtNtCs6Hz1PecaLG4_4core3fmt5Debug3fmt
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.15, 32

	.type	.Lanon.8237690aa1ed0b145f80bff47c997adc.16,@object
	.section	.rodata..Lanon.8237690aa1ed0b145f80bff47c997adc.16,"a",@progbits
.Lanon.8237690aa1ed0b145f80bff47c997adc.16:
	.ascii	"fatal runtime error: thread result panicked on drop, aborting\n"
	.size	.Lanon.8237690aa1ed0b145f80bff47c997adc.16, 62

	.hidden	DW.ref.rust_eh_personality
	.weak	DW.ref.rust_eh_personality
	.section	.data.DW.ref.rust_eh_personality,"awG",@progbits,DW.ref.rust_eh_personality,comdat
	.p2align	3, 0x0
	.type	DW.ref.rust_eh_personality,@object
	.size	DW.ref.rust_eh_personality, 8
DW.ref.rust_eh_personality:
	.xword	rust_eh_personality
	.ident	"rustc version 1.95.0 (59807616e 2026-04-14)"
	.section	".note.GNU-stack","",@progbits
