_RNvCs3Zr3VSSmLc0_24consensus_leases_fencing18accepts_generation:
	.cfi_startproc
	cmp	x1, #0
	ccmp	x1, x0, #0, ne
	cset	w0, eq
	ret
.Lfunc_end8:
