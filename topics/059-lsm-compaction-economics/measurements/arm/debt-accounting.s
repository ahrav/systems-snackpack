_RNvCshWuqkEVdhE8_24lsm_compaction_economics9next_debt:
	.cfi_startproc
	mul	x8, x2, x1
	umulh	x9, x2, x1
	adds	x8, x8, x0
	cinc	x9, x9, hs
	subs	x8, x8, x3
	sbcs	x9, x9, xzr
	csel	x9, xzr, x9, lo
	csel	x1, xzr, x8, lo
	cmp	x9, #0
	cset	w0, eq
	ret
.Lfunc_end6:
