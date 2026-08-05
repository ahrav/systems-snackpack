	.file	"lib.11a904da3c715d79-cgu.0"
	.section	.text._ZN3lib21publication_roundtrip17h1d0bf3def212a71aE,"ax",@progbits
	.globl	_ZN3lib21publication_roundtrip17h1d0bf3def212a71aE
	.p2align	4
	.type	_ZN3lib21publication_roundtrip17h1d0bf3def212a71aE,@function
_ZN3lib21publication_roundtrip17h1d0bf3def212a71aE:
.Lfunc_begin0:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception0
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
	subq	$280, %rsp
	.cfi_def_cfa_offset 336
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	.cfi_offset %rbp, -16
	movq	%rdi, 112(%rsp)
	testq	%rdi, %rdi
	je	.LBB0_69
	movq	$0, 96(%rsp)
	movq	$0, 104(%rsp)
	movq	$0, 120(%rsp)
	callq	*_ZN3std6thread7current18current_or_unnamed17h3a8a289fb49a86cfE@GOTPCREL(%rip)
	movq	%rax, %r15
	movq	$1, 16(%rsp)
	movq	$1, 24(%rsp)
	movq	%rax, 32(%rsp)
	movq	$0, 40(%rsp)
	movb	$0, 48(%rsp)
	callq	*_RNvCsdBezzDwma51_7___rustc35___rust_no_alloc_shim_is_unstable_v2@GOTPCREL(%rip)
	movl	$40, %edi
	movl	$8, %esi
	callq	*_RNvCsdBezzDwma51_7___rustc12___rust_alloc@GOTPCREL(%rip)
	testq	%rax, %rax
	je	.LBB0_70
	movq	%rax, %rbx
	movq	48(%rsp), %rax
	movq	%rax, 32(%rbx)
	movabsq	$-9223372036854775808, %r12
	vmovups	16(%rsp), %ymm0
	vmovups	%ymm0, (%rbx)
	movq	%rbx, 128(%rsp)
	movq	%r12, 256(%rsp)
	lock		incq	(%rbx)
	jle	.LBB0_81
	movq	%rbx, 216(%rsp)
	movq	_ZN3std6thread9lifecycle15spawn_unchecked28_$u7b$$u7b$closure$u7d$$u7d$3MIN17heb58e166151882deE@GOTPCREL(%rip), %r13
	movq	(%r13), %r14
	testq	%r14, %r14
	je	.LBB0_5
	decq	%r14
	jmp	.LBB0_36
.LBB0_5:
.Ltmp0:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.14(%rip), %rsi
	leaq	144(%rsp), %rdi
	movl	$14, %edx
	vzeroupper
	callq	*_ZN3std3env7_var_os17h6e1d94da7de7999dE@GOTPCREL(%rip)
.Ltmp1:
	movq	144(%rsp), %r15
	movl	$2097152, %r14d
	cmpq	%r12, %r15
	je	.LBB0_35
	movq	152(%rsp), %r12
	movq	160(%rsp), %rdx
.Ltmp2:
	leaq	16(%rsp), %rdi
	movq	%r12, %rsi
	callq	*_ZN4core3str8converts9from_utf817h98213b8934c661a6E@GOTPCREL(%rip)
.Ltmp3:
	cmpl	$1, 16(%rsp)
	je	.LBB0_32
	movq	32(%rsp), %rcx
	testq	%rcx, %rcx
	je	.LBB0_32
	movq	24(%rsp), %rsi
	cmpq	$1, %rcx
	jne	.LBB0_16
	movzbl	(%rsi), %eax
	cmpl	$43, %eax
	je	.LBB0_32
	cmpl	$45, %eax
	je	.LBB0_32
	jmp	.LBB0_17
.LBB0_16:
	movzbl	(%rsi), %eax
.LBB0_17:
	xorl	%edi, %edi
	cmpb	$43, %al
	sete	%dil
	movq	%rcx, %rdx
	subq	%rdi, %rdx
	addq	%rdi, %rsi
	movq	%rdi, %rax
	negq	%rax
	cmpq	$17, %rdx
	jae	.LBB0_22
	testq	%rdx, %rdx
	je	.LBB0_29
	addq	%rax, %rcx
	negq	%rcx
	xorl	%eax, %eax
	xorl	%r14d, %r14d
	.p2align	4
.LBB0_20:
	movzbl	(%rsi,%rax), %edx
	addl	$-48, %edx
	cmpl	$9, %edx
	ja	.LBB0_32
	leaq	(%r14,%r14,4), %rdi
	movl	%edx, %edx
	leaq	(%rdx,%rdi,2), %r14
	incq	%rax
	movq	%rcx, %rdx
	addq	%rax, %rdx
	jne	.LBB0_20
	jmp	.LBB0_33
.LBB0_22:
	addq	%rax, %rcx
	negq	%rcx
	xorl	%edi, %edi
	movl	$10, %r8d
	xorl	%r14d, %r14d
	.p2align	4
.LBB0_23:
	movq	%rcx, %rax
	addq	%rdi, %rax
	je	.LBB0_33
	movzbl	(%rsi,%rdi), %r9d
	addl	$-48, %r9d
	cmpl	$9, %r9d
	ja	.LBB0_32
	movq	%r14, %rax
	mulq	%r8
	movl	%r9d, %r14d
	seto	%dl
	addq	%rax, %r14
	setb	%al
	testb	%dl, %dl
	jne	.LBB0_32
	incq	%rdi
	testb	%al, %al
	je	.LBB0_23
.LBB0_32:
	movl	$2097152, %r14d
.LBB0_33:
	testq	%r15, %r15
	je	.LBB0_35
.LBB0_34:
	movl	$1, %edx
	movq	%r12, %rdi
	movq	%r15, %rsi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB0_35:
	leaq	1(%r14), %rax
	movq	%rax, (%r13)
.LBB0_36:
.Ltmp5:
	vzeroupper
	callq	*_ZN3std6thread2id8ThreadId3new17hb08b34ae2e7edb5bE@GOTPCREL(%rip)
.Ltmp6:
.Ltmp7:
	leaq	256(%rsp), %rsi
	movq	%rax, %rdi
	callq	*_ZN3std6thread6thread6Thread3new17h8db5d782c2606e0eE@GOTPCREL(%rip)
.Ltmp8:
	movq	%rax, 8(%rsp)
.Ltmp10:
	leaq	224(%rsp), %rdi
	leaq	8(%rsp), %rsi
	callq	*_ZN3std6thread9spawnhook15run_spawn_hooks17ha93b3e536e07adaaE@GOTPCREL(%rip)
.Ltmp11:
	movq	$1, 16(%rsp)
	movq	$1, 24(%rsp)
	movq	%rbx, 32(%rsp)
	movq	$0, 40(%rsp)
	callq	*_RNvCsdBezzDwma51_7___rustc35___rust_no_alloc_shim_is_unstable_v2@GOTPCREL(%rip)
	movl	$48, %edi
	movl	$8, %esi
	callq	*_RNvCsdBezzDwma51_7___rustc12___rust_alloc@GOTPCREL(%rip)
	testq	%rax, %rax
	je	.LBB0_71
	movq	%rax, %r15
	vmovups	16(%rsp), %ymm0
	vmovups	32(%rsp), %ymm1
	vmovups	%ymm1, 16(%rax)
	vmovups	%ymm0, (%rax)
	movq	%rax, 136(%rsp)
	lock		incq	(%rax)
	jle	.LBB0_81
	leaq	112(%rsp), %rax
	movq	%rax, 184(%rsp)
	leaq	120(%rsp), %rax
	movq	%rax, 192(%rsp)
	leaq	96(%rsp), %rax
	movq	%rax, 200(%rsp)
	leaq	104(%rsp), %rax
	movq	%rax, 208(%rsp)
	vmovups	224(%rsp), %ymm0
	vmovups	%ymm0, 144(%rsp)
	movq	%r15, 176(%rsp)
	movq	16(%r15), %rdi
	testq	%rdi, %rdi
	je	.LBB0_43
	addq	$16, %rdi
.Ltmp13:
	vzeroupper
	callq	*_ZN3std6thread6scoped9ScopeData29increment_num_running_threads17hcf4ddf12d9ea8b07E@GOTPCREL(%rip)
.Ltmp14:
.LBB0_43:
	movq	208(%rsp), %rax
	movq	%rax, 80(%rsp)
	movq	176(%rsp), %rax
	movq	%rax, 48(%rsp)
	movq	184(%rsp), %rax
	movq	%rax, 56(%rsp)
	movq	192(%rsp), %rax
	movq	%rax, 64(%rsp)
	vmovups	144(%rsp), %ymm0
	movq	200(%rsp), %rax
	movq	%rax, 72(%rsp)
	vmovups	%ymm0, 16(%rsp)
	vzeroupper
	callq	*_RNvCsdBezzDwma51_7___rustc35___rust_no_alloc_shim_is_unstable_v2@GOTPCREL(%rip)
	movl	$72, %edi
	movl	$8, %esi
	callq	*_RNvCsdBezzDwma51_7___rustc12___rust_alloc@GOTPCREL(%rip)
	testq	%rax, %rax
	je	.LBB0_73
	movq	208(%rsp), %rcx
	movq	%rcx, 64(%rax)
	vmovups	144(%rsp), %ymm0
	vmovups	176(%rsp), %ymm1
	vmovups	%ymm1, 32(%rax)
	vmovups	%ymm0, (%rax)
	movq	8(%rsp), %rcx
	lock		incq	(%rcx)
	jle	.LBB0_81
	movq	8(%rsp), %rcx
	movq	%rcx, 16(%rsp)
	movq	%rax, 24(%rsp)
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.13(%rip), %rax
	movq	%rax, 32(%rsp)
	vzeroupper
	callq	*_RNvCsdBezzDwma51_7___rustc35___rust_no_alloc_shim_is_unstable_v2@GOTPCREL(%rip)
	movl	$24, %edi
	movl	$8, %esi
	callq	*_RNvCsdBezzDwma51_7___rustc12___rust_alloc@GOTPCREL(%rip)
	testq	%rax, %rax
	je	.LBB0_74
	movq	32(%rsp), %rcx
	movq	%rcx, 16(%rax)
	vmovups	16(%rsp), %xmm0
	vmovups	%xmm0, (%rax)
.Ltmp18:
	movq	%r14, %rdi
	movq	%rax, %rsi
	callq	*_ZN3std3sys6thread4unix6Thread3new17heb8efce15a43abb3E@GOTPCREL(%rip)
.Ltmp19:
	testb	$1, %al
	jne	.LBB0_76
	movq	8(%rsp), %rax
	movq	%rax, 16(%rsp)
	leaq	24(%rsp), %r12
	movq	%r15, 24(%rsp)
	leaq	32(%rsp), %rdi
	movq	%rdx, 32(%rsp)
.Ltmp21:
	callq	*_ZN72_$LT$std..sys..thread..unix..Thread$u20$as$u20$core..ops..drop..Drop$GT$4drop17h097535a2337a440cE@GOTPCREL(%rip)
.Ltmp22:
	movq	16(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_51
	#MEMBARRIER
.Ltmp26:
	leaq	16(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp27:
.LBB0_51:
	movq	24(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_53
	#MEMBARRIER
.Ltmp32:
	movq	%r12, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp33:
.LBB0_53:
	movq	112(%rsp), %rax
	testq	%rax, %rax
	je	.LBB0_60
	movl	$1, %edx
	movl	$1, %ecx
	.p2align	4
.LBB0_55:
	cmpq	%rax, %rdx
	adcq	$0, %rcx
	movq	%rdx, 144(%rsp)
	movq	104(%rsp), %rsi
	cmpq	%rdx, %rsi
	je	.LBB0_57
	.p2align	4
.LBB0_56:
	pause
	movq	104(%rsp), %rsi
	cmpq	%rdx, %rsi
	jne	.LBB0_56
.LBB0_57:
	movq	96(%rsp), %rsi
	movq	%rsi, 16(%rsp)
	cmpq	%rdx, %rsi
	jne	.LBB0_68
	movq	%rdx, 120(%rsp)
	cmpq	%rax, %rdx
	jae	.LBB0_60
	movq	%rcx, %rdx
	cmpq	%rax, %rcx
	jbe	.LBB0_55
.LBB0_60:
	xorl	%r15d, %r15d
	movq	%rbx, %r14
	addq	$16, %r14
	.p2align	4
.LBB0_61:
	movq	24(%rbx), %rax
	testq	%rax, %rax
	je	.LBB0_63
.Ltmp78:
	movq	%r14, %rdi
	callq	*_ZN3std6thread6thread6Thread4park17h6ca6da5189cb8427E@GOTPCREL(%rip)
.Ltmp79:
	jmp	.LBB0_61
.LBB0_63:
	testq	%r15, %r15
	jne	.LBB0_75
	movzbl	32(%rbx), %eax
	testb	%al, %al
	jne	.LBB0_72
	lock		decq	(%rbx)
	jne	.LBB0_67
	#MEMBARRIER
	leaq	128(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E@GOTPCREL(%rip)
.LBB0_67:
	movq	96(%rsp), %rax
	addq	$280, %rsp
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
.LBB0_68:
	.cfi_def_cfa_offset 336
.Ltmp34:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.7(%rip), %r9
	leaq	16(%rsp), %rsi
	leaq	144(%rsp), %rdx
	xorl	%edi, %edi
	xorl	%ecx, %ecx
	callq	*_ZN4core9panicking13assert_failed17h96c228186ef0cf65E@GOTPCREL(%rip)
.Ltmp35:
	jmp	.LBB0_81
.LBB0_29:
	xorl	%r14d, %r14d
	testq	%r15, %r15
	jne	.LBB0_34
	jmp	.LBB0_35
.LBB0_69:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.0(%rip), %rdi
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.2(%rip), %rdx
	movl	$45, %esi
	callq	*_ZN4core9panicking9panic_fmt17ha4414e4328fe24a0E@GOTPCREL(%rip)
.LBB0_70:
.Ltmp91:
	leaq	32(%rsp), %rbx
	movl	$8, %edi
	movl	$40, %esi
	callq	*_ZN5alloc5alloc18handle_alloc_error17h96ccf7ea5a15db6bE@GOTPCREL(%rip)
.Ltmp92:
	jmp	.LBB0_81
.LBB0_71:
.Ltmp62:
	leaq	32(%rsp), %r15
	movl	$8, %edi
	movl	$48, %esi
	callq	*_ZN5alloc5alloc18handle_alloc_error17h96ccf7ea5a15db6bE@GOTPCREL(%rip)
.Ltmp63:
	jmp	.LBB0_81
.LBB0_72:
.Ltmp85:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.12(%rip), %rdi
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.3(%rip), %rdx
	movl	$49, %esi
	callq	*_ZN4core9panicking9panic_fmt17ha4414e4328fe24a0E@GOTPCREL(%rip)
.Ltmp86:
	jmp	.LBB0_81
.LBB0_73:
.Ltmp54:
	movl	$8, %edi
	movl	$72, %esi
	callq	*_ZN5alloc5alloc18handle_alloc_error17h96ccf7ea5a15db6bE@GOTPCREL(%rip)
.Ltmp55:
	jmp	.LBB0_81
.LBB0_74:
.Ltmp48:
	movl	$8, %edi
	movl	$24, %esi
	callq	*_ZN5alloc5alloc18handle_alloc_error17h96ccf7ea5a15db6bE@GOTPCREL(%rip)
.Ltmp49:
	jmp	.LBB0_81
.LBB0_75:
.Ltmp83:
	movq	%r15, %rdi
	movq	%r12, %rsi
	callq	*_ZN3std5panic13resume_unwind17h2c31e69098ee986aE@GOTPCREL(%rip)
.Ltmp84:
	jmp	.LBB0_81
.LBB0_76:
	movq	%rdx, %r14
	lock		decq	(%r15)
	jne	.LBB0_78
	#MEMBARRIER
.Ltmp36:
	leaq	136(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp37:
.LBB0_78:
	movq	8(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_80
	#MEMBARRIER
.Ltmp39:
	leaq	8(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp40:
.LBB0_80:
	movq	%r14, 16(%rsp)
.Ltmp42:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.4(%rip), %rdi
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.15(%rip), %rcx
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.6(%rip), %r8
	leaq	16(%rsp), %rdx
	movl	$22, %esi
	callq	*_ZN4core6result13unwrap_failed17hac9339a6c7ad693bE@GOTPCREL(%rip)
.Ltmp43:
.LBB0_81:
	ud2
.LBB0_82:
.Ltmp4:
	movq	%rax, %r14
	testq	%r15, %r15
	je	.LBB0_113
	movl	$1, %edx
	movq	%r12, %rdi
	movq	%r15, %rsi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
	jmp	.LBB0_113
.LBB0_84:
.Ltmp38:
	movq	%rax, %r14
	jmp	.LBB0_109
.LBB0_85:
.Ltmp28:
	movq	%rax, %r14
	jmp	.LBB0_91
.LBB0_86:
.Ltmp44:
	movq	%rax, %r14
.Ltmp45:
	leaq	16(%rsp), %rdi
	callq	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E
.Ltmp46:
	jmp	.LBB0_126
.LBB0_87:
.Ltmp47:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_88:
.Ltmp15:
	movq	%rax, %r14
.Ltmp16:
	leaq	144(%rsp), %rdi
	callq	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE
.Ltmp17:
	jmp	.LBB0_102
.LBB0_89:
.Ltmp23:
	movq	%rax, %r14
	movq	16(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_91
	#MEMBARRIER
.Ltmp24:
	leaq	16(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp25:
.LBB0_91:
	movq	24(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_126
	#MEMBARRIER
.Ltmp29:
	movq	%r12, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp30:
	jmp	.LBB0_126
.LBB0_93:
.Ltmp31:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_94:
.Ltmp20:
	movq	%rax, %r14
	jmp	.LBB0_102
.LBB0_95:
.Ltmp12:
	movq	%rax, %r14
	movb	$1, %bpl
	jmp	.LBB0_110
.LBB0_96:
.Ltmp9:
	movq	%rax, %r14
	jmp	.LBB0_113
.LBB0_97:
.Ltmp80:
	movq	%rax, %r14
	testq	%r15, %r15
	je	.LBB0_121
.Ltmp81:
	movq	%r15, %rdi
	movq	%r12, %rsi
	callq	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E
.Ltmp82:
	jmp	.LBB0_121
.LBB0_99:
.Ltmp50:
	movq	%rax, %r14
.Ltmp51:
	leaq	16(%rsp), %rdi
	callq	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E
.Ltmp52:
	jmp	.LBB0_102
.LBB0_100:
.Ltmp53:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_101:
.Ltmp56:
	movq	%rax, %r14
.Ltmp57:
	leaq	16(%rsp), %rdi
	callq	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE
.Ltmp58:
.LBB0_102:
	lock		decq	(%r15)
	jne	.LBB0_109
	#MEMBARRIER
.Ltmp60:
	leaq	136(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp61:
	jmp	.LBB0_109
.LBB0_106:
.Ltmp59:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_107:
.Ltmp64:
	movq	%rax, %r14
.Ltmp65:
	movq	%r15, %rdi
	callq	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE
.Ltmp66:
.Ltmp68:
	leaq	224(%rsp), %rdi
	callq	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E
.Ltmp69:
.LBB0_109:
	xorl	%ebp, %ebp
.LBB0_110:
	movq	8(%rsp), %rax
	lock		decq	(%rax)
	jne	.LBB0_112
	#MEMBARRIER
.Ltmp70:
	leaq	8(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp71:
.LBB0_112:
	testb	%bpl, %bpl
	je	.LBB0_126
.LBB0_113:
	lock		decq	(%rbx)
	jne	.LBB0_126
	#MEMBARRIER
.Ltmp72:
	leaq	216(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E@GOTPCREL(%rip)
.Ltmp73:
	jmp	.LBB0_126
.LBB0_115:
.Ltmp67:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_116:
.Ltmp74:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_117:
.Ltmp93:
	movq	%rax, %r14
	lock		decq	(%r15)
	jne	.LBB0_123
	#MEMBARRIER
.Ltmp94:
	movq	%rbx, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp95:
	jmp	.LBB0_123
.LBB0_119:
.Ltmp96:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_120:
.Ltmp87:
	movq	%rax, %r14
.LBB0_121:
	lock		decq	(%rbx)
	jne	.LBB0_123
	#MEMBARRIER
.Ltmp88:
	leaq	128(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E@GOTPCREL(%rip)
.Ltmp89:
.LBB0_123:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.LBB0_124:
.Ltmp90:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB0_125:
.Ltmp41:
	movq	%rax, %r14
.LBB0_126:
.Ltmp75:
	movq	%r14, %rdi
	callq	*_ZN3std9panicking12catch_unwind7cleanup17hd1f9d9ec33cd656bE@GOTPCREL(%rip)
.Ltmp76:
	movq	%rax, %r15
	movq	%rdx, %r12
	movq	%rbx, %r14
	addq	$16, %r14
	jmp	.LBB0_61
.LBB0_128:
.Ltmp77:
	callq	*_ZN4core9panicking19panic_cannot_unwind17h9d41c6c1d0e0d4e5E@GOTPCREL(%rip)
.Lfunc_end0:
	.size	_ZN3lib21publication_roundtrip17h1d0bf3def212a71aE, .Lfunc_end0-_ZN3lib21publication_roundtrip17h1d0bf3def212a71aE
	.cfi_endproc
	.section	.gcc_except_table._ZN3lib21publication_roundtrip17h1d0bf3def212a71aE,"a",@progbits
	.p2align	2, 0x0
GCC_except_table0:
.Lexception0:
	.byte	255
	.byte	155
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
	.uleb128 .Ltmp13-.Lfunc_begin0
	.uleb128 .Ltmp14-.Ltmp13
	.uleb128 .Ltmp15-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp18-.Lfunc_begin0
	.uleb128 .Ltmp19-.Ltmp18
	.uleb128 .Ltmp20-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp21-.Lfunc_begin0
	.uleb128 .Ltmp22-.Ltmp21
	.uleb128 .Ltmp23-.Lfunc_begin0
	.byte	5
	.uleb128 .Ltmp26-.Lfunc_begin0
	.uleb128 .Ltmp27-.Ltmp26
	.uleb128 .Ltmp28-.Lfunc_begin0
	.byte	5
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
	.uleb128 .Ltmp36-.Lfunc_begin0
	.uleb128 .Ltmp37-.Ltmp36
	.uleb128 .Ltmp38-.Lfunc_begin0
	.byte	5
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
	.uleb128 .Ltmp24-.Lfunc_begin0
	.uleb128 .Ltmp30-.Ltmp24
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
	.uleb128 .Ltmp60-.Lfunc_begin0
	.uleb128 .Ltmp61-.Ltmp60
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp65-.Lfunc_begin0
	.uleb128 .Ltmp66-.Ltmp65
	.uleb128 .Ltmp67-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp68-.Lfunc_begin0
	.uleb128 .Ltmp73-.Ltmp68
	.uleb128 .Ltmp74-.Lfunc_begin0
	.byte	1
	.uleb128 .Ltmp94-.Lfunc_begin0
	.uleb128 .Ltmp95-.Ltmp94
	.uleb128 .Ltmp96-.Lfunc_begin0
	.byte	1
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
	.long	0
.Lttbase0:
	.byte	0
	.p2align	2, 0x0

	.section	.text._ZN3std2io5Write9write_all17h4a2cc97feea30fefE,"ax",@progbits
	.p2align	4
	.type	_ZN3std2io5Write9write_all17h4a2cc97feea30fefE,@function
_ZN3std2io5Write9write_all17h4a2cc97feea30fefE:
.Lfunc_begin1:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception1
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
	testq	%rdx, %rdx
	je	.LBB1_18
	movq	%rdx, %rbx
	movq	%rsi, %r14
	movq	%rdi, %r15
	movq	_ZN64_$LT$std..sys..stdio..unix..Stderr$u20$as$u20$std..io..Write$GT$5write17hc04dc6e87e8ab63cE@GOTPCREL(%rip), %r13
	leaq	.LJTI1_0(%rip), %rbp
	movq	_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip), %r12
	movq	%rdi, (%rsp)
	jmp	.LBB1_4
.LBB1_15:
	movq	%rdx, %rax
	movabsq	$-4294967296, %rcx
	andq	%rcx, %rax
	movabsq	$17179869184, %rcx
	cmpq	%rcx, %rax
	jne	.LBB1_20
	.p2align	4
.LBB1_3:
	testq	%rbx, %rbx
	je	.LBB1_18
.LBB1_4:
	movq	%r15, %rdi
	movq	%r14, %rsi
	movq	%rbx, %rdx
	callq	*%r13
	testb	$1, %al
	je	.LBB1_12
	movl	%edx, %eax
	andl	$3, %eax
	movslq	(%rbp,%rax,4), %rax
	addq	%rbp, %rax
	jmpq	*%rax
.LBB1_2:
	cmpb	$35, 16(%rdx)
	je	.LBB1_3
	jmp	.LBB1_20
	.p2align	4
.LBB1_12:
	testq	%rdx, %rdx
	je	.LBB1_19
	movq	%rbx, %rax
	subq	%rdx, %rax
	jb	.LBB1_21
	addq	%rdx, %r14
	movq	%rax, %rbx
	jmp	.LBB1_3
.LBB1_16:
	movq	%rdx, %rax
	movabsq	$-4294967296, %rcx
	andq	%rcx, %rax
	movabsq	$150323855360, %rcx
	cmpq	%rcx, %rax
	je	.LBB1_3
	jmp	.LBB1_20
.LBB1_6:
	cmpb	$35, 15(%rdx)
	jne	.LBB1_20
	movq	%rdx, %r13
	decq	%r13
	movq	-1(%rdx), %r15
	movq	7(%rdx), %rbp
	movq	(%rbp), %rax
	testq	%rax, %rax
	je	.LBB1_9
.Ltmp97:
	movq	%r15, %rdi
	callq	*%rax
.Ltmp98:
.LBB1_9:
	movq	8(%rbp), %rsi
	testq	%rsi, %rsi
	je	.LBB1_11
	movq	16(%rbp), %rdx
	movq	%r15, %rdi
	callq	*%r12
.LBB1_11:
	movl	$24, %esi
	movl	$8, %edx
	movq	%r13, %rdi
	callq	*%r12
	movq	_ZN64_$LT$std..sys..stdio..unix..Stderr$u20$as$u20$std..io..Write$GT$5write17hc04dc6e87e8ab63cE@GOTPCREL(%rip), %r13
	leaq	.LJTI1_0(%rip), %rbp
	movq	(%rsp), %r15
	jmp	.LBB1_3
.LBB1_18:
	xorl	%edx, %edx
.LBB1_20:
	movq	%rdx, %rax
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
.LBB1_19:
	.cfi_def_cfa_offset 64
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.10(%rip), %rdx
	jmp	.LBB1_20
.LBB1_21:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.11(%rip), %rcx
	movq	%rdx, %rdi
	movq	%rbx, %rsi
	movq	%rbx, %rdx
	callq	*_ZN4core5slice5index16slice_index_fail17h62807bcaa490c9c1E@GOTPCREL(%rip)
.LBB1_22:
.Ltmp99:
	movq	%rax, %rbx
	movq	8(%rbp), %rsi
	testq	%rsi, %rsi
	je	.LBB1_24
	movq	16(%rbp), %rdx
	movq	%r15, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB1_24:
	movl	$24, %esi
	movl	$8, %edx
	movq	%r13, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
	movq	%rbx, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end1:
	.size	_ZN3std2io5Write9write_all17h4a2cc97feea30fefE, .Lfunc_end1-_ZN3std2io5Write9write_all17h4a2cc97feea30fefE
	.cfi_endproc
	.section	.rodata._ZN3std2io5Write9write_all17h4a2cc97feea30fefE,"a",@progbits
	.p2align	2, 0x0
.LJTI1_0:
	.long	.LBB1_2-.LJTI1_0
	.long	.LBB1_6-.LJTI1_0
	.long	.LBB1_15-.LJTI1_0
	.long	.LBB1_16-.LJTI1_0
	.section	.gcc_except_table._ZN3std2io5Write9write_all17h4a2cc97feea30fefE,"a",@progbits
	.p2align	2, 0x0
GCC_except_table1:
.Lexception1:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end1-.Lcst_begin1
.Lcst_begin1:
	.uleb128 .Lfunc_begin1-.Lfunc_begin1
	.uleb128 .Ltmp97-.Lfunc_begin1
	.byte	0
	.byte	0
	.uleb128 .Ltmp97-.Lfunc_begin1
	.uleb128 .Ltmp98-.Ltmp97
	.uleb128 .Ltmp99-.Lfunc_begin1
	.byte	0
	.uleb128 .Ltmp98-.Lfunc_begin1
	.uleb128 .Lfunc_end1-.Ltmp98
	.byte	0
	.byte	0
.Lcst_end1:
	.p2align	2, 0x0

	.section	.text._ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E,"ax",@progbits
	.globl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E
	.p2align	4
	.type	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E,@function
_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E:
	.cfi_startproc
	movq	(%rdi), %rax
	movq	(%rax), %rax
	testq	%rax, %rax
	je	.LBB2_6
	movq	8(%rdi), %rcx
	movq	16(%rdi), %rdx
	movq	24(%rdi), %rsi
	movl	$1, %r8d
	movl	$1, %edi
	.p2align	4
.LBB2_2:
	cmpq	%rax, %r8
	adcq	$0, %rdi
	leaq	-1(%r8), %r9
	movq	(%rcx), %r10
	cmpq	%r9, %r10
	je	.LBB2_4
	.p2align	4
.LBB2_7:
	pause
	movq	(%rcx), %r10
	cmpq	%r9, %r10
	jne	.LBB2_7
.LBB2_4:
	movq	%r8, (%rdx)
	movq	%r8, (%rsi)
	cmpq	%rax, %r8
	jae	.LBB2_6
	movq	%rdi, %r8
	cmpq	%rax, %rdi
	jbe	.LBB2_2
.LBB2_6:
	#APP
	#NO_APP
	retq
.Lfunc_end2:
	.size	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E, .Lfunc_end2-_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E
	.cfi_endproc

	.section	.text._ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E,"ax",@progbits
	.globl	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E
	.p2align	4
	.type	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E,@function
_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E:
	.cfi_startproc
	subq	$40, %rsp
	.cfi_def_cfa_offset 48
	vmovups	(%rdi), %ymm0
	vmovups	%ymm0, (%rsp)
	movq	%rsp, %rdi
	vzeroupper
	callq	*_ZN3std6thread9spawnhook15ChildSpawnHooks3run17h6aafd3c876dc04cbE@GOTPCREL(%rip)
	#APP
	#NO_APP
	addq	$40, %rsp
	.cfi_def_cfa_offset 8
	retq
.Lfunc_end3:
	.size	_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E, .Lfunc_end3-_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E
	.cfi_endproc

	.section	".text._ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E,@function
_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E:
.Lfunc_begin2:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception2
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
	subq	$136, %rsp
	.cfi_def_cfa_offset 192
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	.cfi_offset %rbp, -16
	movq	%rdi, %rbx
	vmovups	40(%rdi), %ymm0
	vmovups	%ymm0, 96(%rsp)
	vmovups	16(%rdi), %xmm1
	vmovaps	%xmm1, 80(%rsp)
	vmovups	(%rdi), %xmm1
	vmovaps	%xmm1, 16(%rsp)
	vmovups	80(%rsp), %xmm1
	vmovups	%xmm1, 32(%rsp)
	vmovups	96(%rsp), %xmm1
	vmovups	%xmm1, 48(%rsp)
	vmovups	%ymm0, 48(%rsp)
.Ltmp100:
	leaq	16(%rsp), %rdi
	vzeroupper
	callq	*_ZN3std3sys9backtrace28__rust_begin_short_backtrace17hb08c55c57aba46c9E@GOTPCREL(%rip)
.Ltmp101:
	leaq	48(%rsp), %rdi
.Ltmp102:
	callq	*_ZN3std3sys9backtrace28__rust_begin_short_backtrace17h103eece1de3dba68E@GOTPCREL(%rip)
.Ltmp103:
	xorl	%r14d, %r14d
	movq	32(%rbx), %rbp
	cmpq	$0, 24(%rbp)
	je	.LBB4_12
.LBB4_7:
	movq	32(%rbp), %r12
	testq	%r12, %r12
	je	.LBB4_12
	movq	40(%rbp), %r13
	movq	(%r13), %rax
	testq	%rax, %rax
	je	.LBB4_10
.Ltmp108:
	addq	$32, %rbx
	movq	%r12, %rdi
	callq	*%rax
.Ltmp109:
.LBB4_10:
	movq	8(%r13), %rsi
	testq	%rsi, %rsi
	je	.LBB4_12
	movq	16(%r13), %rdx
	movq	%r12, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB4_12:
	movq	$1, 24(%rbp)
	movq	%r14, 32(%rbp)
	movq	%r15, 40(%rbp)
	movq	%rbp, 8(%rsp)
	lock		decq	(%rbp)
	jne	.LBB4_14
	#MEMBARRIER
	leaq	8(%rsp), %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.LBB4_14:
	addq	$136, %rsp
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
.LBB4_15:
	.cfi_def_cfa_offset 192
.Ltmp110:
	movq	%rax, (%rsp)
	movq	8(%r13), %rsi
	testq	%rsi, %rsi
	je	.LBB4_17
	movq	16(%r13), %rdx
	movq	%r12, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB4_17:
	movq	$1, 24(%rbp)
	movq	%r14, 32(%rbp)
	movq	%r15, 40(%rbp)
	lock		decq	(%rbp)
	jne	.LBB4_19
	#MEMBARRIER
.Ltmp111:
	movq	%rbx, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp112:
.LBB4_19:
	movq	(%rsp), %rdi
	callq	_Unwind_Resume@PLT
.LBB4_20:
.Ltmp113:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB4_4:
.Ltmp104:
.Ltmp105:
	movq	%rax, %rdi
	callq	*_ZN3std9panicking12catch_unwind7cleanup17hd1f9d9ec33cd656bE@GOTPCREL(%rip)
.Ltmp106:
	movq	%rax, %r14
	movq	%rdx, %r15
	movq	32(%rbx), %rbp
	cmpq	$0, 24(%rbp)
	jne	.LBB4_7
	jmp	.LBB4_12
.LBB4_3:
.Ltmp107:
	callq	*_ZN4core9panicking19panic_cannot_unwind17h9d41c6c1d0e0d4e5E@GOTPCREL(%rip)
.Lfunc_end4:
	.size	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E, .Lfunc_end4-_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E","a",@progbits
	.p2align	2, 0x0
GCC_except_table4:
.Lexception2:
	.byte	255
	.byte	155
	.uleb128 .Lttbase1-.Lttbaseref1
.Lttbaseref1:
	.byte	1
	.uleb128 .Lcst_end2-.Lcst_begin2
.Lcst_begin2:
	.uleb128 .Ltmp100-.Lfunc_begin2
	.uleb128 .Ltmp103-.Ltmp100
	.uleb128 .Ltmp104-.Lfunc_begin2
	.byte	3
	.uleb128 .Ltmp108-.Lfunc_begin2
	.uleb128 .Ltmp109-.Ltmp108
	.uleb128 .Ltmp110-.Lfunc_begin2
	.byte	0
	.uleb128 .Ltmp109-.Lfunc_begin2
	.uleb128 .Ltmp111-.Ltmp109
	.byte	0
	.byte	0
	.uleb128 .Ltmp111-.Lfunc_begin2
	.uleb128 .Ltmp112-.Ltmp111
	.uleb128 .Ltmp113-.Lfunc_begin2
	.byte	1
	.uleb128 .Ltmp112-.Lfunc_begin2
	.uleb128 .Ltmp105-.Ltmp112
	.byte	0
	.byte	0
	.uleb128 .Ltmp105-.Lfunc_begin2
	.uleb128 .Ltmp106-.Ltmp105
	.uleb128 .Ltmp107-.Lfunc_begin2
	.byte	1
.Lcst_end2:
	.byte	127
	.byte	0
	.byte	1
	.byte	0
	.p2align	2, 0x0
	.long	0
.Lttbase1:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE,@function
_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE:
.Lfunc_begin3:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception3
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	testq	%rdi, %rdi
	je	.LBB5_8
	movq	%rsi, %r14
	movq	%rdi, %rbx
	movq	(%rsi), %rax
	testq	%rax, %rax
	je	.LBB5_3
.Ltmp114:
	movq	%rbx, %rdi
	callq	*%rax
.Ltmp115:
.LBB5_3:
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB5_8
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB5_8:
	.cfi_def_cfa_offset 32
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	retq
.LBB5_5:
	.cfi_def_cfa_offset 32
.Ltmp116:
	movq	%rax, %r15
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB5_7
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB5_7:
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end5:
	.size	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE, .Lfunc_end5-_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE","a",@progbits
	.p2align	2, 0x0
GCC_except_table5:
.Lexception3:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end3-.Lcst_begin3
.Lcst_begin3:
	.uleb128 .Ltmp114-.Lfunc_begin3
	.uleb128 .Ltmp115-.Ltmp114
	.uleb128 .Ltmp116-.Lfunc_begin3
	.byte	0
	.uleb128 .Ltmp115-.Lfunc_begin3
	.uleb128 .Lfunc_end5-.Ltmp115
	.byte	0
	.byte	0
.Lcst_end3:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E,@function
_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E:
.Lfunc_begin4:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception4
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	movq	%rsi, %r14
	movq	%rdi, %rbx
	movq	(%rsi), %rax
	testq	%rax, %rax
	je	.LBB6_2
.Ltmp117:
	movq	%rbx, %rdi
	callq	*%rax
.Ltmp118:
.LBB6_2:
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB6_3
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB6_3:
	.cfi_def_cfa_offset 32
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	retq
.LBB6_4:
	.cfi_def_cfa_offset 32
.Ltmp119:
	movq	%rax, %r15
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB6_6
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB6_6:
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end6:
	.size	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E, .Lfunc_end6-_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E","a",@progbits
	.p2align	2, 0x0
GCC_except_table6:
.Lexception4:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end4-.Lcst_begin4
.Lcst_begin4:
	.uleb128 .Ltmp117-.Lfunc_begin4
	.uleb128 .Ltmp118-.Ltmp117
	.uleb128 .Ltmp119-.Lfunc_begin4
	.byte	0
	.uleb128 .Ltmp118-.Lfunc_begin4
	.uleb128 .Lfunc_end6-.Ltmp118
	.byte	0
	.byte	0
.Lcst_end4:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E,@function
_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E:
.Lfunc_begin5:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception5
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
	movq	%rdi, %r14
	movq	8(%rdi), %rax
	movq	%rax, (%rsp)
	movq	16(%rdi), %r13
	testq	%r13, %r13
	je	.LBB7_7
	movq	(%rsp), %rax
	leaq	24(%rax), %rbp
	movq	_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip), %r15
	jmp	.LBB7_2
	.p2align	4
.LBB7_6:
	addq	$16, %rbp
	decq	%r13
	je	.LBB7_7
.LBB7_2:
	movq	-24(%rbp), %r12
	movq	-16(%rbp), %rbx
	movq	(%rbx), %rax
	testq	%rax, %rax
	je	.LBB7_4
.Ltmp120:
	movq	%r12, %rdi
	callq	*%rax
.Ltmp121:
.LBB7_4:
	movq	8(%rbx), %rsi
	testq	%rsi, %rsi
	je	.LBB7_6
	movq	16(%rbx), %rdx
	movq	%r12, %rdi
	callq	*%r15
	jmp	.LBB7_6
.LBB7_7:
	movq	(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB7_17
	shlq	$4, %rsi
	movl	$8, %edx
	movq	(%rsp), %rdi
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
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB7_17:
	.cfi_def_cfa_offset 64
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
.LBB7_9:
	.cfi_def_cfa_offset 64
.Ltmp122:
	movq	%rax, %r15
	movq	8(%rbx), %rsi
	testq	%rsi, %rsi
	je	.LBB7_11
	movq	16(%rbx), %rdx
	movq	%r12, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
	.p2align	4
.LBB7_11:
	decq	%r13
	je	.LBB7_14
	leaq	16(%rbp), %rbx
	movq	-8(%rbp), %rdi
	movq	(%rbp), %rsi
.Ltmp123:
	callq	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E
.Ltmp124:
	movq	%rbx, %rbp
	jmp	.LBB7_11
.LBB7_14:
	movq	(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB7_16
	shlq	$4, %rsi
	movl	$8, %edx
	movq	(%rsp), %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB7_16:
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.LBB7_13:
.Ltmp125:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.Lfunc_end7:
	.size	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E, .Lfunc_end7-_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E","a",@progbits
	.p2align	2, 0x0
GCC_except_table7:
.Lexception5:
	.byte	255
	.byte	155
	.uleb128 .Lttbase2-.Lttbaseref2
.Lttbaseref2:
	.byte	1
	.uleb128 .Lcst_end5-.Lcst_begin5
.Lcst_begin5:
	.uleb128 .Ltmp120-.Lfunc_begin5
	.uleb128 .Ltmp121-.Ltmp120
	.uleb128 .Ltmp122-.Lfunc_begin5
	.byte	0
	.uleb128 .Ltmp121-.Lfunc_begin5
	.uleb128 .Ltmp123-.Ltmp121
	.byte	0
	.byte	0
	.uleb128 .Ltmp123-.Lfunc_begin5
	.uleb128 .Ltmp124-.Ltmp123
	.uleb128 .Ltmp125-.Lfunc_begin5
	.byte	1
	.uleb128 .Ltmp124-.Lfunc_begin5
	.uleb128 .Lfunc_end7-.Ltmp124
	.byte	0
	.byte	0
.Lcst_end5:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase2:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE,@function
_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE:
.Lfunc_begin6:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception6
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	cmpq	$0, (%rdi)
	je	.LBB8_9
	movq	8(%rdi), %rbx
	testq	%rbx, %rbx
	je	.LBB8_9
	movq	16(%rdi), %r15
	movq	(%r15), %rax
	testq	%rax, %rax
	je	.LBB8_4
.Ltmp126:
	movq	%rbx, %rdi
	callq	*%rax
.Ltmp127:
.LBB8_4:
	movq	8(%r15), %rsi
	testq	%rsi, %rsi
	je	.LBB8_9
	movq	16(%r15), %rdx
	movq	%rbx, %rdi
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB8_9:
	.cfi_def_cfa_offset 32
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	retq
.LBB8_6:
	.cfi_def_cfa_offset 32
.Ltmp128:
	movq	%rax, %r14
	movq	8(%r15), %rsi
	testq	%rsi, %rsi
	je	.LBB8_8
	movq	16(%r15), %rdx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB8_8:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end8:
	.size	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE, .Lfunc_end8-_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE","a",@progbits
	.p2align	2, 0x0
GCC_except_table8:
.Lexception6:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end6-.Lcst_begin6
.Lcst_begin6:
	.uleb128 .Ltmp126-.Lfunc_begin6
	.uleb128 .Ltmp127-.Ltmp126
	.uleb128 .Ltmp128-.Lfunc_begin6
	.byte	0
	.uleb128 .Ltmp127-.Lfunc_begin6
	.uleb128 .Lfunc_end8-.Ltmp127
	.byte	0
	.byte	0
.Lcst_end6:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE,@function
_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE:
.Lfunc_begin7:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception7
	pushq	%r14
	.cfi_def_cfa_offset 16
	pushq	%rbx
	.cfi_def_cfa_offset 24
	pushq	%rax
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -24
	.cfi_offset %r14, -16
	movq	%rdi, %rbx
.Ltmp129:
	callq	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E
.Ltmp130:
	movq	32(%rbx), %rax
	lock		decq	(%rax)
	jne	.LBB9_6
	addq	$32, %rbx
	#MEMBARRIER
	movq	%rbx, %rdi
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	jmpq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.LBB9_6:
	.cfi_def_cfa_offset 32
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	retq
.LBB9_3:
	.cfi_def_cfa_offset 32
.Ltmp131:
	movq	%rax, %r14
	movq	32(%rbx), %rax
	lock		decq	(%rax)
	jne	.LBB9_5
	addq	$32, %rbx
	#MEMBARRIER
.Ltmp132:
	movq	%rbx, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E@GOTPCREL(%rip)
.Ltmp133:
.LBB9_5:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.LBB9_7:
.Ltmp134:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.Lfunc_end9:
	.size	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE, .Lfunc_end9-_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE","a",@progbits
	.p2align	2, 0x0
GCC_except_table9:
.Lexception7:
	.byte	255
	.byte	155
	.uleb128 .Lttbase3-.Lttbaseref3
.Lttbaseref3:
	.byte	1
	.uleb128 .Lcst_end7-.Lcst_begin7
.Lcst_begin7:
	.uleb128 .Ltmp129-.Lfunc_begin7
	.uleb128 .Ltmp130-.Ltmp129
	.uleb128 .Ltmp131-.Lfunc_begin7
	.byte	0
	.uleb128 .Ltmp130-.Lfunc_begin7
	.uleb128 .Ltmp132-.Ltmp130
	.byte	0
	.byte	0
	.uleb128 .Ltmp132-.Lfunc_begin7
	.uleb128 .Ltmp133-.Ltmp132
	.uleb128 .Ltmp134-.Lfunc_begin7
	.byte	1
	.uleb128 .Ltmp133-.Lfunc_begin7
	.uleb128 .Lfunc_end9-.Ltmp133
	.byte	0
	.byte	0
.Lcst_end7:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase3:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E,@function
_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E:
.Lfunc_begin8:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception8
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%r12
	.cfi_def_cfa_offset 32
	pushq	%rbx
	.cfi_def_cfa_offset 40
	pushq	%rax
	.cfi_def_cfa_offset 48
	.cfi_offset %rbx, -40
	.cfi_offset %r12, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	movq	(%rdi), %rax
	movl	%eax, %ecx
	andl	$3, %ecx
	cmpl	$1, %ecx
	je	.LBB10_1
	addq	$8, %rsp
	.cfi_def_cfa_offset 40
	popq	%rbx
	.cfi_def_cfa_offset 32
	popq	%r12
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	retq
.LBB10_1:
	.cfi_def_cfa_offset 48
	leaq	-1(%rax), %rbx
	movq	-1(%rax), %r14
	movq	7(%rax), %r12
	movq	(%r12), %rax
	testq	%rax, %rax
	je	.LBB10_3
.Ltmp135:
	movq	%r14, %rdi
	callq	*%rax
.Ltmp136:
.LBB10_3:
	movq	8(%r12), %rsi
	testq	%rsi, %rsi
	je	.LBB10_5
	movq	16(%r12), %rdx
	movq	%r14, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB10_5:
	movl	$24, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	addq	$8, %rsp
	.cfi_def_cfa_offset 40
	popq	%rbx
	.cfi_def_cfa_offset 32
	popq	%r12
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB10_6:
	.cfi_def_cfa_offset 48
.Ltmp137:
	movq	%rax, %r15
	movq	8(%r12), %rsi
	testq	%rsi, %rsi
	je	.LBB10_8
	movq	16(%r12), %rdx
	movq	%r14, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB10_8:
	movl	$24, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end10:
	.size	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E, .Lfunc_end10-_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E","a",@progbits
	.p2align	2, 0x0
GCC_except_table10:
.Lexception8:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end8-.Lcst_begin8
.Lcst_begin8:
	.uleb128 .Ltmp135-.Lfunc_begin8
	.uleb128 .Ltmp136-.Ltmp135
	.uleb128 .Ltmp137-.Lfunc_begin8
	.byte	0
	.uleb128 .Ltmp136-.Lfunc_begin8
	.uleb128 .Lfunc_end10-.Ltmp136
	.byte	0
	.byte	0
.Lcst_end8:
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E,@function
_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E:
.Lfunc_begin9:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception9
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	movq	%rdi, %r15
	movq	(%rdi), %rax
	lock		decq	(%rax)
	jne	.LBB11_2
	#MEMBARRIER
.Ltmp138:
	movq	%r15, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp139:
.LBB11_2:
	movq	8(%r15), %r14
	movq	16(%r15), %r15
	movq	(%r15), %rax
	testq	%rax, %rax
	je	.LBB11_4
.Ltmp144:
	movq	%r14, %rdi
	callq	*%rax
.Ltmp145:
.LBB11_4:
	movq	8(%r15), %rsi
	testq	%rsi, %rsi
	je	.LBB11_10
	movq	16(%r15), %rdx
	movq	%r14, %rdi
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB11_10:
	.cfi_def_cfa_offset 32
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	retq
.LBB11_6:
	.cfi_def_cfa_offset 32
.Ltmp140:
	movq	%rax, %rbx
	movq	8(%r15), %rdi
	movq	16(%r15), %rsi
.Ltmp141:
	callq	_ZN4core3ptr154drop_in_place$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$17hc80f68bcc1d7b802E
.Ltmp142:
	jmp	.LBB11_9
.LBB11_11:
.Ltmp143:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB11_7:
.Ltmp146:
	movq	%rax, %rbx
	movq	8(%r15), %rsi
	testq	%rsi, %rsi
	je	.LBB11_9
	movq	16(%r15), %rdx
	movq	%r14, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB11_9:
	movq	%rbx, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end11:
	.size	_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E, .Lfunc_end11-_ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr55drop_in_place$LT$std..thread..lifecycle..ThreadInit$GT$17ha7d699e09d4a6f02E","a",@progbits
	.p2align	2, 0x0
GCC_except_table11:
.Lexception9:
	.byte	255
	.byte	155
	.uleb128 .Lttbase4-.Lttbaseref4
.Lttbaseref4:
	.byte	1
	.uleb128 .Lcst_end9-.Lcst_begin9
.Lcst_begin9:
	.uleb128 .Ltmp138-.Lfunc_begin9
	.uleb128 .Ltmp139-.Ltmp138
	.uleb128 .Ltmp140-.Lfunc_begin9
	.byte	0
	.uleb128 .Ltmp144-.Lfunc_begin9
	.uleb128 .Ltmp145-.Ltmp144
	.uleb128 .Ltmp146-.Lfunc_begin9
	.byte	0
	.uleb128 .Ltmp141-.Lfunc_begin9
	.uleb128 .Ltmp142-.Ltmp141
	.uleb128 .Ltmp143-.Lfunc_begin9
	.byte	1
	.uleb128 .Ltmp142-.Lfunc_begin9
	.uleb128 .Lfunc_end11-.Ltmp142
	.byte	0
	.byte	0
.Lcst_end9:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase4:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E,@function
_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E:
.Lfunc_begin10:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception10
	pushq	%r15
	.cfi_def_cfa_offset 16
	pushq	%r14
	.cfi_def_cfa_offset 24
	pushq	%rbx
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -32
	.cfi_offset %r14, -24
	.cfi_offset %r15, -16
	movq	%rdi, %rbx
	leaq	24(%rdi), %r15
.Ltmp147:
	movq	%r15, %rdi
	callq	*_ZN76_$LT$std..thread..spawnhook..SpawnHooks$u20$as$u20$core..ops..drop..Drop$GT$4drop17hd2c35755f43fd5daE@GOTPCREL(%rip)
.Ltmp148:
	movq	(%r15), %rax
	testq	%rax, %rax
	je	.LBB12_4
	lock		decq	(%rax)
	jne	.LBB12_4
	#MEMBARRIER
.Ltmp153:
	movq	%r15, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h3060fe8aaede2a56E@GOTPCREL(%rip)
.Ltmp154:
.LBB12_4:
	movq	%rbx, %rdi
	popq	%rbx
	.cfi_def_cfa_offset 24
	popq	%r14
	.cfi_def_cfa_offset 16
	popq	%r15
	.cfi_def_cfa_offset 8
	jmp	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E
.LBB12_9:
	.cfi_def_cfa_offset 32
.Ltmp155:
	movq	%rax, %r14
	jmp	.LBB12_10
.LBB12_5:
.Ltmp149:
	movq	%rax, %r14
	movq	(%r15), %rax
	testq	%rax, %rax
	je	.LBB12_10
	lock		decq	(%rax)
	jne	.LBB12_10
	#MEMBARRIER
.Ltmp150:
	movq	%r15, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h3060fe8aaede2a56E@GOTPCREL(%rip)
.Ltmp151:
.LBB12_10:
.Ltmp156:
	movq	%rbx, %rdi
	callq	_ZN4core3ptr177drop_in_place$LT$alloc..vec..Vec$LT$alloc..boxed..Box$LT$dyn$u20$core..ops..function..FnOnce$LT$$LP$$RP$$GT$$u2b$Output$u20$$u3d$$u20$$LP$$RP$$u2b$core..marker..Send$GT$$GT$$GT$17he46712607f6ad878E
.Ltmp157:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.LBB12_8:
.Ltmp152:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB12_12:
.Ltmp158:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.Lfunc_end12:
	.size	_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E, .Lfunc_end12-_ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr60drop_in_place$LT$std..thread..spawnhook..ChildSpawnHooks$GT$17hc0dd1ced56a20749E","a",@progbits
	.p2align	2, 0x0
GCC_except_table12:
.Lexception10:
	.byte	255
	.byte	155
	.uleb128 .Lttbase5-.Lttbaseref5
.Lttbaseref5:
	.byte	1
	.uleb128 .Lcst_end10-.Lcst_begin10
.Lcst_begin10:
	.uleb128 .Ltmp147-.Lfunc_begin10
	.uleb128 .Ltmp148-.Ltmp147
	.uleb128 .Ltmp149-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp153-.Lfunc_begin10
	.uleb128 .Ltmp154-.Ltmp153
	.uleb128 .Ltmp155-.Lfunc_begin10
	.byte	0
	.uleb128 .Ltmp154-.Lfunc_begin10
	.uleb128 .Ltmp150-.Ltmp154
	.byte	0
	.byte	0
	.uleb128 .Ltmp150-.Lfunc_begin10
	.uleb128 .Ltmp151-.Ltmp150
	.uleb128 .Ltmp152-.Lfunc_begin10
	.byte	1
	.uleb128 .Ltmp156-.Lfunc_begin10
	.uleb128 .Ltmp157-.Ltmp156
	.uleb128 .Ltmp158-.Lfunc_begin10
	.byte	1
	.uleb128 .Ltmp157-.Lfunc_begin10
	.uleb128 .Lfunc_end12-.Ltmp157
	.byte	0
	.byte	0
.Lcst_end10:
	.byte	127
	.byte	0
	.p2align	2, 0x0
.Lttbase5:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE","ax",@progbits
	.p2align	4
	.type	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE,@function
_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE:
.Lfunc_begin11:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception11
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
	subq	$24, %rsp
	.cfi_def_cfa_offset 80
	.cfi_offset %rbx, -56
	.cfi_offset %r12, -48
	.cfi_offset %r13, -40
	.cfi_offset %r14, -32
	.cfi_offset %r15, -24
	.cfi_offset %rbp, -16
	movq	%rdi, %r14
	leaq	8(%rdi), %rbx
	movq	8(%rdi), %rbp
	movq	16(%rdi), %r15
	testq	%r15, %r15
	setne	%r13b
	testq	%rbp, %rbp
	je	.LBB13_6
	testq	%r15, %r15
	je	.LBB13_6
	movq	24(%r14), %r12
	movq	(%r12), %rax
	testq	%rax, %rax
	je	.LBB13_4
.Ltmp159:
	movq	%r15, %rdi
	callq	*%rax
.Ltmp160:
.LBB13_4:
	movq	8(%r12), %rsi
	testq	%rsi, %rsi
	je	.LBB13_6
	movq	16(%r12), %rdx
	movq	%r15, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB13_6:
	movq	$0, (%rbx)
.LBB13_7:
	movq	(%r14), %r12
	testq	%r12, %r12
	je	.LBB13_11
	andb	%r13b, %bpl
	leaq	16(%r12), %rdi
.Ltmp175:
	movzbl	%bpl, %esi
	callq	*_ZN3std6thread6scoped9ScopeData29decrement_num_running_threads17h4dcc73c9f6daaaaeE@GOTPCREL(%rip)
.Ltmp176:
	lock		decq	(%r12)
	jne	.LBB13_11
	#MEMBARRIER
.Ltmp180:
	movq	%r14, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E@GOTPCREL(%rip)
.Ltmp181:
.LBB13_11:
	cmpq	$0, (%rbx)
	je	.LBB13_38
	movq	16(%r14), %rbx
	testq	%rbx, %rbx
	je	.LBB13_38
	movq	24(%r14), %r14
	movq	(%r14), %rax
	testq	%rax, %rax
	je	.LBB13_15
.Ltmp186:
	movq	%rbx, %rdi
	callq	*%rax
.Ltmp187:
.LBB13_15:
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB13_38
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	addq	$24, %rsp
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
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB13_38:
	.cfi_def_cfa_offset 80
	addq	$24, %rsp
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
.LBB13_35:
	.cfi_def_cfa_offset 80
.Ltmp188:
	movq	%rax, %r15
	movq	8(%r14), %rsi
	testq	%rsi, %rsi
	je	.LBB13_37
	movq	16(%r14), %rdx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.LBB13_17:
.Ltmp161:
	movq	%rax, 8(%rsp)
	movq	8(%r12), %rsi
	testq	%rsi, %rsi
	je	.LBB13_19
	movq	16(%r12), %rdx
	movq	%r15, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB13_19:
	movq	$0, (%rbx)
.Ltmp162:
	movq	8(%rsp), %rdi
	callq	*_ZN3std9panicking12catch_unwind7cleanup17hd1f9d9ec33cd656bE@GOTPCREL(%rip)
	movq	%rdx, 8(%rsp)
.Ltmp163:
	movq	%rax, %r12
	testq	%rax, %rax
	je	.LBB13_7
.Ltmp165:
	leaq	.Lanon.228b9293dd6a618083e1440756268b92.16(%rip), %rsi
	leaq	7(%rsp), %rdi
	movl	$62, %edx
	callq	_ZN3std2io5Write9write_all17h4a2cc97feea30fefE
.Ltmp166:
	movq	%rax, 16(%rsp)
	testq	%rax, %rax
	je	.LBB13_24
.Ltmp167:
	leaq	16(%rsp), %rdi
	callq	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E
.Ltmp168:
.LBB13_24:
.Ltmp169:
	callq	*_ZN3std7process5abort17ha9b4297bc434c261E@GOTPCREL(%rip)
.Ltmp170:
	ud2
.LBB13_29:
.Ltmp171:
	movq	%rax, %r15
.Ltmp172:
	movq	%r12, %rdi
	movq	8(%rsp), %rsi
	callq	_ZN4core3ptr130drop_in_place$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$17h214e6c7ff0984debE
.Ltmp173:
	movq	(%r14), %r12
	testq	%r12, %r12
	jne	.LBB13_31
	jmp	.LBB13_33
.LBB13_27:
.Ltmp174:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.LBB13_26:
.Ltmp164:
	callq	*_ZN4core9panicking19panic_cannot_unwind17h9d41c6c1d0e0d4e5E@GOTPCREL(%rip)
.LBB13_34:
.Ltmp182:
	movq	%rax, %r15
	jmp	.LBB13_33
.LBB13_28:
.Ltmp177:
	movq	%rax, %r15
.LBB13_31:
	lock		decq	(%r12)
	jne	.LBB13_33
	#MEMBARRIER
.Ltmp178:
	movq	%r14, %rdi
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E@GOTPCREL(%rip)
.Ltmp179:
.LBB13_33:
.Ltmp183:
	movq	%rbx, %rdi
	callq	_ZN4core3ptr188drop_in_place$LT$core..cell..UnsafeCell$LT$core..option..Option$LT$core..result..Result$LT$$LP$$RP$$C$alloc..boxed..Box$LT$dyn$u20$core..any..Any$u2b$core..marker..Send$GT$$GT$$GT$$GT$$GT$17h6f193f8a5ec3c19aE
.Ltmp184:
.LBB13_37:
	movq	%r15, %rdi
	callq	_Unwind_Resume@PLT
.LBB13_39:
.Ltmp185:
	callq	*_ZN4core9panicking16panic_in_cleanup17h5f6bde45d17ae243E@GOTPCREL(%rip)
.Lfunc_end13:
	.size	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE, .Lfunc_end13-_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE
	.cfi_endproc
	.section	".gcc_except_table._ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE","a",@progbits
	.p2align	2, 0x0
GCC_except_table13:
.Lexception11:
	.byte	255
	.byte	155
	.uleb128 .Lttbase6-.Lttbaseref6
.Lttbaseref6:
	.byte	1
	.uleb128 .Lcst_end11-.Lcst_begin11
.Lcst_begin11:
	.uleb128 .Ltmp159-.Lfunc_begin11
	.uleb128 .Ltmp160-.Ltmp159
	.uleb128 .Ltmp161-.Lfunc_begin11
	.byte	5
	.uleb128 .Ltmp175-.Lfunc_begin11
	.uleb128 .Ltmp176-.Ltmp175
	.uleb128 .Ltmp177-.Lfunc_begin11
	.byte	0
	.uleb128 .Ltmp180-.Lfunc_begin11
	.uleb128 .Ltmp181-.Ltmp180
	.uleb128 .Ltmp182-.Lfunc_begin11
	.byte	0
	.uleb128 .Ltmp186-.Lfunc_begin11
	.uleb128 .Ltmp187-.Ltmp186
	.uleb128 .Ltmp188-.Lfunc_begin11
	.byte	0
	.uleb128 .Ltmp187-.Lfunc_begin11
	.uleb128 .Ltmp162-.Ltmp187
	.byte	0
	.byte	0
	.uleb128 .Ltmp162-.Lfunc_begin11
	.uleb128 .Ltmp163-.Ltmp162
	.uleb128 .Ltmp164-.Lfunc_begin11
	.byte	1
	.uleb128 .Ltmp165-.Lfunc_begin11
	.uleb128 .Ltmp170-.Ltmp165
	.uleb128 .Ltmp171-.Lfunc_begin11
	.byte	0
	.uleb128 .Ltmp172-.Lfunc_begin11
	.uleb128 .Ltmp173-.Ltmp172
	.uleb128 .Ltmp174-.Lfunc_begin11
	.byte	1
	.uleb128 .Ltmp178-.Lfunc_begin11
	.uleb128 .Ltmp184-.Ltmp178
	.uleb128 .Ltmp185-.Lfunc_begin11
	.byte	1
	.uleb128 .Ltmp184-.Lfunc_begin11
	.uleb128 .Lfunc_end13-.Ltmp184
	.byte	0
	.byte	0
.Lcst_end11:
	.byte	127
	.byte	0
	.byte	0
	.byte	0
	.byte	1
	.byte	125
	.p2align	2, 0x0
	.long	0
.Lttbase6:
	.byte	0
	.p2align	2, 0x0

	.section	".text._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E","ax",@progbits
	.globl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E
	.p2align	4
	.type	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E,@function
_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E:
.Lfunc_begin12:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception12
	pushq	%r14
	.cfi_def_cfa_offset 16
	pushq	%rbx
	.cfi_def_cfa_offset 24
	pushq	%rax
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -24
	.cfi_offset %r14, -16
	movq	(%rdi), %rbx
	leaq	16(%rbx), %rdi
.Ltmp189:
	callq	_ZN4core3ptr67drop_in_place$LT$std..thread..lifecycle..Packet$LT$$LP$$RP$$GT$$GT$17hea94e2aaf6e507feE
.Ltmp190:
	cmpq	$-1, %rbx
	je	.LBB14_8
	lock		decq	8(%rbx)
	jne	.LBB14_8
	#MEMBARRIER
	movl	$48, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB14_8:
	.cfi_def_cfa_offset 32
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	retq
.LBB14_4:
	.cfi_def_cfa_offset 32
.Ltmp191:
	movq	%rax, %r14
	cmpq	$-1, %rbx
	je	.LBB14_7
	lock		decq	8(%rbx)
	jne	.LBB14_7
	#MEMBARRIER
	movl	$48, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB14_7:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end14:
	.size	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E, .Lfunc_end14-_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E
	.cfi_endproc
	.section	".gcc_except_table._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h215d7dab384617c3E","a",@progbits
	.p2align	2, 0x0
GCC_except_table14:
.Lexception12:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end12-.Lcst_begin12
.Lcst_begin12:
	.uleb128 .Ltmp189-.Lfunc_begin12
	.uleb128 .Ltmp190-.Ltmp189
	.uleb128 .Ltmp191-.Lfunc_begin12
	.byte	0
	.uleb128 .Ltmp190-.Lfunc_begin12
	.uleb128 .Lfunc_end14-.Ltmp190
	.byte	0
	.byte	0
.Lcst_end12:
	.p2align	2, 0x0

	.section	".text._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E","ax",@progbits
	.globl	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E
	.p2align	4
	.type	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E,@function
_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E:
.Lfunc_begin13:
	.cfi_startproc
	.cfi_personality 155, DW.ref.rust_eh_personality
	.cfi_lsda 27, .Lexception13
	pushq	%r14
	.cfi_def_cfa_offset 16
	pushq	%rbx
	.cfi_def_cfa_offset 24
	pushq	%rax
	.cfi_def_cfa_offset 32
	.cfi_offset %rbx, -24
	.cfi_offset %r14, -16
	movq	(%rdi), %rbx
	movq	16(%rbx), %rax
	lock		decq	(%rax)
	jne	.LBB15_2
	leaq	16(%rbx), %rdi
	#MEMBARRIER
.Ltmp192:
	callq	*_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17h168f5a2d86c304bdE@GOTPCREL(%rip)
.Ltmp193:
.LBB15_2:
	cmpq	$-1, %rbx
	je	.LBB15_9
	lock		decq	8(%rbx)
	jne	.LBB15_9
	#MEMBARRIER
	movl	$40, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	jmpq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB15_9:
	.cfi_def_cfa_offset 32
	addq	$8, %rsp
	.cfi_def_cfa_offset 24
	popq	%rbx
	.cfi_def_cfa_offset 16
	popq	%r14
	.cfi_def_cfa_offset 8
	retq
.LBB15_5:
	.cfi_def_cfa_offset 32
.Ltmp194:
	movq	%rax, %r14
	cmpq	$-1, %rbx
	je	.LBB15_8
	lock		decq	8(%rbx)
	jne	.LBB15_8
	#MEMBARRIER
	movl	$40, %esi
	movl	$8, %edx
	movq	%rbx, %rdi
	callq	*_RNvCsdBezzDwma51_7___rustc14___rust_dealloc@GOTPCREL(%rip)
.LBB15_8:
	movq	%r14, %rdi
	callq	_Unwind_Resume@PLT
.Lfunc_end15:
	.size	_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E, .Lfunc_end15-_ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E
	.cfi_endproc
	.section	".gcc_except_table._ZN5alloc4sync16Arc$LT$T$C$A$GT$9drop_slow17hf29844f82ede3ac0E","a",@progbits
	.p2align	2, 0x0
GCC_except_table15:
.Lexception13:
	.byte	255
	.byte	255
	.byte	1
	.uleb128 .Lcst_end13-.Lcst_begin13
.Lcst_begin13:
	.uleb128 .Ltmp192-.Lfunc_begin13
	.uleb128 .Ltmp193-.Ltmp192
	.uleb128 .Ltmp194-.Lfunc_begin13
	.byte	0
	.uleb128 .Ltmp193-.Lfunc_begin13
	.uleb128 .Lfunc_end15-.Ltmp193
	.byte	0
	.byte	0
.Lcst_end13:
	.p2align	2, 0x0

	.section	.text.compiler_fence_seqcst,"ax",@progbits
	.globl	compiler_fence_seqcst
	.p2align	4
	.type	compiler_fence_seqcst,@function
compiler_fence_seqcst:
	.cfi_startproc
	#MEMBARRIER
	retq
.Lfunc_end16:
	.size	compiler_fence_seqcst, .Lfunc_end16-compiler_fence_seqcst
	.cfi_endproc

	.section	.text.fence_acqrel,"ax",@progbits
	.globl	fence_acqrel
	.p2align	4
	.type	fence_acqrel,@function
fence_acqrel:
	.cfi_startproc
	#MEMBARRIER
	retq
.Lfunc_end17:
	.size	fence_acqrel, .Lfunc_end17-fence_acqrel
	.cfi_endproc

	.section	.text.fence_acquire,"ax",@progbits
	.globl	fence_acquire
	.p2align	4
	.type	fence_acquire,@function
fence_acquire:
	.cfi_startproc
	#MEMBARRIER
	retq
.Lfunc_end18:
	.size	fence_acquire, .Lfunc_end18-fence_acquire
	.cfi_endproc

	.section	.text.fence_release,"ax",@progbits
	.globl	fence_release
	.p2align	4
	.type	fence_release,@function
fence_release:
	.cfi_startproc
	#MEMBARRIER
	retq
.Lfunc_end19:
	.size	fence_release, .Lfunc_end19-fence_release
	.cfi_endproc

	.section	.text.fence_seqcst,"ax",@progbits
	.globl	fence_seqcst
	.p2align	4
	.type	fence_seqcst,@function
fence_seqcst:
	.cfi_startproc
	lock		orl	$0, -64(%rsp)
	retq
.Lfunc_end20:
	.size	fence_seqcst, .Lfunc_end20-fence_seqcst
	.cfi_endproc

	.section	.text.fetch_add_acqrel,"ax",@progbits
	.globl	fetch_add_acqrel
	.p2align	4
	.type	fetch_add_acqrel,@function
fetch_add_acqrel:
	.cfi_startproc
	movq	%rsi, %rax
	lock		xaddq	%rax, (%rdi)
	retq
.Lfunc_end21:
	.size	fetch_add_acqrel, .Lfunc_end21-fetch_add_acqrel
	.cfi_endproc

	.section	.text.fetch_add_acquire,"ax",@progbits
	.globl	fetch_add_acquire
	.p2align	4
	.type	fetch_add_acquire,@function
fetch_add_acquire:
	.cfi_startproc
	movq	%rsi, %rax
	lock		xaddq	%rax, (%rdi)
	retq
.Lfunc_end22:
	.size	fetch_add_acquire, .Lfunc_end22-fetch_add_acquire
	.cfi_endproc

	.section	.text.fetch_add_relaxed,"ax",@progbits
	.globl	fetch_add_relaxed
	.p2align	4
	.type	fetch_add_relaxed,@function
fetch_add_relaxed:
	.cfi_startproc
	movq	%rsi, %rax
	lock		xaddq	%rax, (%rdi)
	retq
.Lfunc_end23:
	.size	fetch_add_relaxed, .Lfunc_end23-fetch_add_relaxed
	.cfi_endproc

	.section	.text.fetch_add_release,"ax",@progbits
	.globl	fetch_add_release
	.p2align	4
	.type	fetch_add_release,@function
fetch_add_release:
	.cfi_startproc
	movq	%rsi, %rax
	lock		xaddq	%rax, (%rdi)
	retq
.Lfunc_end24:
	.size	fetch_add_release, .Lfunc_end24-fetch_add_release
	.cfi_endproc

	.section	.text.fetch_add_seqcst,"ax",@progbits
	.globl	fetch_add_seqcst
	.p2align	4
	.type	fetch_add_seqcst,@function
fetch_add_seqcst:
	.cfi_startproc
	movq	%rsi, %rax
	lock		xaddq	%rax, (%rdi)
	retq
.Lfunc_end25:
	.size	fetch_add_seqcst, .Lfunc_end25-fetch_add_seqcst
	.cfi_endproc

	.section	.text.load_acquire,"ax",@progbits
	.globl	load_acquire
	.p2align	4
	.type	load_acquire,@function
load_acquire:
	.cfi_startproc
	movq	(%rdi), %rax
	retq
.Lfunc_end26:
	.size	load_acquire, .Lfunc_end26-load_acquire
	.cfi_endproc

	.section	.text.load_relaxed,"ax",@progbits
	.globl	load_relaxed
	.p2align	4
	.type	load_relaxed,@function
load_relaxed:
	.cfi_startproc
	movq	(%rdi), %rax
	retq
.Lfunc_end27:
	.size	load_relaxed, .Lfunc_end27-load_relaxed
	.cfi_endproc

	.section	.text.load_seqcst,"ax",@progbits
	.globl	load_seqcst
	.p2align	4
	.type	load_seqcst,@function
load_seqcst:
	.cfi_startproc
	movq	(%rdi), %rax
	retq
.Lfunc_end28:
	.size	load_seqcst, .Lfunc_end28-load_seqcst
	.cfi_endproc

	.section	.text.store_relaxed,"ax",@progbits
	.globl	store_relaxed
	.p2align	4
	.type	store_relaxed,@function
store_relaxed:
	.cfi_startproc
	movq	%rsi, (%rdi)
	retq
.Lfunc_end29:
	.size	store_relaxed, .Lfunc_end29-store_relaxed
	.cfi_endproc

	.section	.text.store_release,"ax",@progbits
	.globl	store_release
	.p2align	4
	.type	store_release,@function
store_release:
	.cfi_startproc
	movq	%rsi, (%rdi)
	retq
.Lfunc_end30:
	.size	store_release, .Lfunc_end30-store_release
	.cfi_endproc

	.section	.text.store_seqcst,"ax",@progbits
	.globl	store_seqcst
	.p2align	4
	.type	store_seqcst,@function
store_seqcst:
	.cfi_startproc
	xchgq	%rsi, (%rdi)
	retq
.Lfunc_end31:
	.size	store_seqcst, .Lfunc_end31-store_seqcst
	.cfi_endproc

	.type	.Lanon.228b9293dd6a618083e1440756268b92.0,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.0,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.0:
	.ascii	"rounds must be nonzero"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.0, 22

	.type	.Lanon.228b9293dd6a618083e1440756268b92.1,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.228b9293dd6a618083e1440756268b92.1:
	.asciz	"/tmp/topic22-5f93fdb-xxl/topics/022-cpu-memory-model-atomic-lowering/src/lib.rs"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.1, 80

	.type	.Lanon.228b9293dd6a618083e1440756268b92.2,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.2,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.2:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.1
	.asciz	"O\000\000\000\000\000\000\000\252\000\000\000\005\000\000"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.2, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.3,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.3,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.3:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.1
	.asciz	"O\000\000\000\000\000\000\000\257\000\000\000\005\000\000"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.3, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.4,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.4,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.4:
	.ascii	"failed to spawn thread"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.4, 22

	.type	.Lanon.228b9293dd6a618083e1440756268b92.5,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.228b9293dd6a618083e1440756268b92.5:
	.asciz	"/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/std/src/thread/scoped.rs"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.5, 81

	.type	.Lanon.228b9293dd6a618083e1440756268b92.6,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.6,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.6:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.5
	.asciz	"P\000\000\000\000\000\000\000\313\000\000\000.\000\000"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.6, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.7,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.7,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.7:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.1
	.asciz	"O\000\000\000\000\000\000\000\276\000\000\000\r\000\000"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.7, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.8,@object
	.section	.rodata.str1.1,"aMS",@progbits,1
.Lanon.228b9293dd6a618083e1440756268b92.8:
	.asciz	"/rustc/01f6ddf7588f42ae2d7eb0a2f21d44e8e96674cf/library/std/src/io/mod.rs"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.8, 74

	.type	.Lanon.228b9293dd6a618083e1440756268b92.9,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.9,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.9:
	.ascii	"failed to write whole buffer"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.9, 28

	.type	.Lanon.228b9293dd6a618083e1440756268b92.10,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.10,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.10:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.9
	.ascii	"\034\000\000\000\000\000\000\000\027"
	.zero	7
	.size	.Lanon.228b9293dd6a618083e1440756268b92.10, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.11,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.11,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.11:
	.quad	.Lanon.228b9293dd6a618083e1440756268b92.8
	.asciz	"I\000\000\000\000\000\000\000Y\007\000\000$\000\000"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.11, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.12,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.12,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.12:
	.ascii	"a scoped thread panicked"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.12, 24

	.type	.Lanon.228b9293dd6a618083e1440756268b92.13,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.13,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.13:
	.quad	_ZN4core3ptr192drop_in_place$LT$std..thread..lifecycle..spawn_unchecked$LT$lib..publication_roundtrip..$u7b$$u7b$closure$u7d$$u7d$..$u7b$$u7b$closure$u7d$$u7d$$C$$LP$$RP$$GT$..$u7b$$u7b$closure$u7d$$u7d$$GT$17hb60bc72d89975b7eE
	.asciz	"H\000\000\000\000\000\000\000\b\000\000\000\000\000\000"
	.quad	_ZN4core3ops8function6FnOnce40call_once$u7b$$u7b$vtable.shim$u7d$$u7d$17ha788ca1ae7cb7821E
	.size	.Lanon.228b9293dd6a618083e1440756268b92.13, 32

	.type	.Lanon.228b9293dd6a618083e1440756268b92.14,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.14,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.14:
	.ascii	"RUST_MIN_STACK"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.14, 14

	.type	.Lanon.228b9293dd6a618083e1440756268b92.15,@object
	.section	.data.rel.ro..Lanon.228b9293dd6a618083e1440756268b92.15,"aw",@progbits
	.p2align	3, 0x0
.Lanon.228b9293dd6a618083e1440756268b92.15:
	.quad	_ZN4core3ptr42drop_in_place$LT$std..io..error..Error$GT$17h0b8fafd3b4cf7e69E
	.asciz	"\b\000\000\000\000\000\000\000\b\000\000\000\000\000\000"
	.quad	_ZN58_$LT$std..io..error..Error$u20$as$u20$core..fmt..Debug$GT$3fmt17h4c28df66b49f43a5E
	.size	.Lanon.228b9293dd6a618083e1440756268b92.15, 32

	.type	.Lanon.228b9293dd6a618083e1440756268b92.16,@object
	.section	.rodata..Lanon.228b9293dd6a618083e1440756268b92.16,"a",@progbits
.Lanon.228b9293dd6a618083e1440756268b92.16:
	.ascii	"fatal runtime error: thread result panicked on drop, aborting\n"
	.size	.Lanon.228b9293dd6a618083e1440756268b92.16, 62

	.hidden	DW.ref.rust_eh_personality
	.weak	DW.ref.rust_eh_personality
	.section	.data.DW.ref.rust_eh_personality,"awG",@progbits,DW.ref.rust_eh_personality,comdat
	.p2align	3, 0x0
	.type	DW.ref.rust_eh_personality,@object
	.size	DW.ref.rust_eh_personality, 8
DW.ref.rust_eh_personality:
	.quad	rust_eh_personality
	.ident	"rustc version 1.93.1 (01f6ddf75 2026-02-11)"
	.section	".note.GNU-stack","",@progbits
