_RNvCs66g1pVT0cAG_24lsm_compaction_economics9next_debt:
	.cfi_startproc
	movq	%rdx, %rax
	mulq	%rsi
	addq	%rdi, %rax
	adcq	$0, %rdx
	xorl	%esi, %esi
	subq	%rcx, %rax
	sbbq	$0, %rdx
	cmovbq	%rsi, %rdx
	cmovaeq	%rax, %rsi
	xorl	%eax, %eax
	testq	%rdx, %rdx
	sete	%al
	movq	%rsi, %rdx
	retq
.Lfunc_end6:
