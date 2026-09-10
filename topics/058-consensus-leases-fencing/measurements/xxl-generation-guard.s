_RNvCscfwii8jw0yV_24consensus_leases_fencing18accepts_generation:
	.cfi_startproc
	testq	%rsi, %rsi
	setne	%cl
	cmpq	%rdi, %rsi
	sete	%al
	andb	%cl, %al
	retq
.Lfunc_end8:
