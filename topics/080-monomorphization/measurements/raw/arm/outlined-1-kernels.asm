0000000000014ce8 <probe::kernels::outlined::<probe::kernels::Format<1>>>:
   14ce8:	14000206 	b	15500 <probe::kernels::shared_core>

0000000000015500 <probe::kernels::shared_core>:
   15500:	b4000181 	cbz	x1, 15530 <probe::kernels::shared_core+0x30>
   15504:	d2803669 	mov	x9, #0x1b3                 	// #435
   15508:	aa0003e8 	mov	x8, x0
   1550c:	52800020 	mov	w0, #0x1                   	// #1
   15510:	f2c02009 	movk	x9, #0x100, lsl #32
   15514:	3840150a 	ldrb	w10, [x8], #1
   15518:	f1000421 	subs	x1, x1, #0x1
   1551c:	ca0a000a 	eor	x10, x0, x10
   15520:	9b097d4a 	mul	x10, x10, x9
   15524:	93cae540 	ror	x0, x10, #57
   15528:	54ffff61 	b.ne	15514 <probe::kernels::shared_core+0x14>  // b.any
   1552c:	d65f03c0 	ret
   15530:	52800020 	mov	w0, #0x1                   	// #1
   15534:	d65f03c0 	ret
