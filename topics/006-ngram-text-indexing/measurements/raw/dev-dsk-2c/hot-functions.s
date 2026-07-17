_ZN27systems_snackpack_topic_00610scan_count17h37f5a2fc28c61894E:
.Lfunc_begin0:
	.file	1 "/tmp/systems-snackpack-topic006-b2fb451" "topics/006-ngram-text-indexing/src/lib.rs"
	.loc	1 185 0
	.cfi_startproc
	pushq	%rbp
	.cfi_def_cfa_offset 16
	pushq	%r15
	.cfi_def_cfa_offset 24
	pushq	%r14
	.cfi_def_cfa_offset 32
	pushq	%r13
	.cfi_def_cfa_offset 40
	pushq	%r12
	.cfi_def_cfa_offset 48
	pushq	%rbx
	.cfi_def_cfa_offset 56
	pushq	%rax
	.cfi_def_cfa_offset 64
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	.cfi_offset %rbp, -16
	.file	2 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/ptr" "non_null.rs"
	.loc	2 1692 9 prologue_end
	testq	%rsi, %rsi
.Ltmp0:
	.file	3 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/slice/iter" "macros.rs"
	.loc	3 25 86
	je	.LBB0_1
.Ltmp1:
	.loc	3 284 24
	shlq	$3, %rsi
	movq	%rcx, %rbx
	movq	%rdx, %r14
	movq	%rdi, %r15
	xorl	%ebp, %ebp
	xorl	%r12d, %r12d
	leaq	(%rsi,%rsi,2), %r13
	.loc	3 0 24 is_stmt 0
.Ltmp2:
	.p2align	4
.LBB0_3:
	.loc	3 279 27 is_stmt 1
	movq	8(%r15,%rbp), %rdi
	movq	16(%r15,%rbp), %rsi
.Ltmp3:
	.loc	1 188 28
	movq	%r14, %rdx
	movq	%rbx, %rcx
	callq	_ZN27systems_snackpack_topic_00614contains_exact17h5b728807dbcb1fe9E
.Ltmp4:
	.file	4 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/iter/adapters" "filter.rs"
	.loc	4 138 22
	movzbl	%al, %eax
.Ltmp5:
	.loc	3 284 24
	addq	$24, %rbp
.Ltmp6:
	.file	5 "/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/core/src/iter/traits" "accum.rs"
	.loc	5 53 28
	addq	%rax, %r12
.Ltmp7:
	.loc	3 284 24
	cmpq	%rbp, %r13
	jne	.LBB0_3
	jmp	.LBB0_4
.Ltmp8:
.LBB0_1:
	.loc	3 0 24 is_stmt 0
	xorl	%r12d, %r12d
.LBB0_4:
	.loc	1 190 2 is_stmt 1
	movq	%r12, %rax
	.loc	1 190 2 epilogue_begin is_stmt 0
	addq	$8, %rsp
	.cfi_def_cfa_offset 56
	popq	%rbx
	.cfi_def_cfa_offset 48
	popq	%r12
	.cfi_def_cfa_offset 40
	popq	%r13
	.cfi_def_cfa_offset 32
	popq	%r14
	.cfi_def_cfa_offset 24
	popq	%r15
	.cfi_def_cfa_offset 16
	popq	%rbp
	.cfi_def_cfa_offset 8
	retq
.Ltmp9:
.Lfunc_end0:
	.size	_ZN27systems_snackpack_topic_00610scan_count17h37f5a2fc28c61894E, .Lfunc_end0-_ZN27systems_snackpack_topic_00610scan_count17h37f5a2fc28c61894E
_ZN27systems_snackpack_topic_00614contains_exact17h5b728807dbcb1fe9E:
.Lfunc_begin3:
	.loc	1 197 0 is_stmt 1
	.cfi_startproc
	pushq	%rbp
	.cfi_def_cfa_offset 16
	pushq	%r15
	.cfi_def_cfa_offset 24
	pushq	%r14
	.cfi_def_cfa_offset 32
	pushq	%r13
	.cfi_def_cfa_offset 40
	pushq	%r12
	.cfi_def_cfa_offset 48
	pushq	%rbx
	.cfi_def_cfa_offset 56
	pushq	%rax
	.cfi_def_cfa_offset 64
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	.cfi_offset %rbp, -16
	movq	%rdx, (%rsp)
.Ltmp860:
	.loc	35 136 9 prologue_end
	testq	%rcx, %rcx
.Ltmp861:
	.loc	1 198 8
	je	.LBB3_9
	.loc	1 0 8 is_stmt 0
	movq	%rsi, %r15
	.loc	1 201 8 is_stmt 1
	subq	%rcx, %r15
	movq	%rcx, %rbx
	jae	.LBB3_4
	.loc	1 0 8 is_stmt 0
	xorl	%eax, %eax
	.loc	1 201 8
	jmp	.LBB3_10
.LBB3_4:
	.loc	1 0 8
	movq	(%rsp), %rax
	movq	%rdi, %r12
	xorl	%r13d, %r13d
.Ltmp862:
	.loc	28 1162 17 is_stmt 1
	xorl	%r14d, %r14d
.Ltmp863:
	.loc	1 205 17
	movzbl	(%rax), %ebp
	.loc	1 0 17 is_stmt 0
.Ltmp864:
	.p2align	4
.LBB3_5:
.Ltmp865:
	.loc	21 1903 50 is_stmt 1
	cmpq	%r15, %r13
.Ltmp866:
	.loc	28 1162 17
	adcq	$0, %r14
.Ltmp867:
	.loc	1 207 12
	cmpb	%bpl, (%r12,%r13)
	jne	.LBB3_7
	.loc	1 0 12 is_stmt 0
	movq	(%rsp), %rsi
	.loc	1 207 0
	leaq	(%r12,%r13), %rdi
.Ltmp868:
	.loc	20 152 13 is_stmt 1
	movq	%rbx, %rdx
	callq	*bcmp@GOTPCREL(%rip)
	testl	%eax, %eax
.Ltmp869:
	.loc	1 207 41
	je	.LBB3_9
.Ltmp870:
.LBB3_7:
	.loc	1 0 41 is_stmt 0
	xorl	%eax, %eax
.Ltmp871:
	.loc	21 1903 50 is_stmt 1
	cmpq	%r15, %r13
.Ltmp872:
	.loc	29 563 9
	jae	.LBB3_10
	.loc	29 0 9 is_stmt 0
	movq	%r14, %r13
	.loc	29 563 9
	cmpq	%r15, %r14
	jbe	.LBB3_5
	jmp	.LBB3_10
.Ltmp873:
.LBB3_9:
	.loc	29 0 9
	movb	$1, %al
.LBB3_10:
	.loc	1 212 2 epilogue_begin is_stmt 1
	addq	$8, %rsp
	.cfi_def_cfa_offset 56
	popq	%rbx
	.cfi_def_cfa_offset 48
	popq	%r12
	.cfi_def_cfa_offset 40
	popq	%r13
	.cfi_def_cfa_offset 32
	popq	%r14
	.cfi_def_cfa_offset 24
	popq	%r15
	.cfi_def_cfa_offset 16
	popq	%rbp
	.cfi_def_cfa_offset 8
	retq
.Ltmp874:
.Lfunc_end3:
	.size	_ZN27systems_snackpack_topic_00614contains_exact17h5b728807dbcb1fe9E, .Lfunc_end3-_ZN27systems_snackpack_topic_00614contains_exact17h5b728807dbcb1fe9E
