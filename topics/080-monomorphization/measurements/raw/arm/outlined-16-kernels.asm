0000000000014ce8 <probe::kernels::outlined::<probe::kernels::Format<16>>>:
   14ce8:	52800202 	mov	w2, #0x10                  	// #16
   14cec:	14000302 	b	158f4 <probe::kernels::shared_core>

0000000000014cf0 <probe::kernels::outlined::<probe::kernels::Format<1>>>:
   14cf0:	52800022 	mov	w2, #0x1                   	// #1
   14cf4:	14000300 	b	158f4 <probe::kernels::shared_core>

0000000000014cf8 <probe::kernels::outlined::<probe::kernels::Format<2>>>:
   14cf8:	52800042 	mov	w2, #0x2                   	// #2
   14cfc:	140002fe 	b	158f4 <probe::kernels::shared_core>

0000000000014d00 <probe::kernels::outlined::<probe::kernels::Format<3>>>:
   14d00:	52800062 	mov	w2, #0x3                   	// #3
   14d04:	140002fc 	b	158f4 <probe::kernels::shared_core>

0000000000014d08 <probe::kernels::outlined::<probe::kernels::Format<4>>>:
   14d08:	52800082 	mov	w2, #0x4                   	// #4
   14d0c:	140002fa 	b	158f4 <probe::kernels::shared_core>

0000000000014d10 <probe::kernels::outlined::<probe::kernels::Format<5>>>:
   14d10:	528000a2 	mov	w2, #0x5                   	// #5
   14d14:	140002f8 	b	158f4 <probe::kernels::shared_core>

0000000000014d18 <probe::kernels::outlined::<probe::kernels::Format<6>>>:
   14d18:	528000c2 	mov	w2, #0x6                   	// #6
   14d1c:	140002f6 	b	158f4 <probe::kernels::shared_core>

0000000000014d20 <probe::kernels::outlined::<probe::kernels::Format<7>>>:
   14d20:	528000e2 	mov	w2, #0x7                   	// #7
   14d24:	140002f4 	b	158f4 <probe::kernels::shared_core>

0000000000014d28 <probe::kernels::outlined::<probe::kernels::Format<8>>>:
   14d28:	52800102 	mov	w2, #0x8                   	// #8
   14d2c:	140002f2 	b	158f4 <probe::kernels::shared_core>

0000000000014d30 <probe::kernels::outlined::<probe::kernels::Format<9>>>:
   14d30:	52800122 	mov	w2, #0x9                   	// #9
   14d34:	140002f0 	b	158f4 <probe::kernels::shared_core>

0000000000014d38 <probe::kernels::outlined::<probe::kernels::Format<10>>>:
   14d38:	52800142 	mov	w2, #0xa                   	// #10
   14d3c:	140002ee 	b	158f4 <probe::kernels::shared_core>

0000000000014d40 <probe::kernels::outlined::<probe::kernels::Format<11>>>:
   14d40:	52800162 	mov	w2, #0xb                   	// #11
   14d44:	140002ec 	b	158f4 <probe::kernels::shared_core>

0000000000014d48 <probe::kernels::outlined::<probe::kernels::Format<12>>>:
   14d48:	52800182 	mov	w2, #0xc                   	// #12
   14d4c:	140002ea 	b	158f4 <probe::kernels::shared_core>

0000000000014d50 <probe::kernels::outlined::<probe::kernels::Format<13>>>:
   14d50:	528001a2 	mov	w2, #0xd                   	// #13
   14d54:	140002e8 	b	158f4 <probe::kernels::shared_core>

0000000000014d58 <probe::kernels::outlined::<probe::kernels::Format<14>>>:
   14d58:	528001c2 	mov	w2, #0xe                   	// #14
   14d5c:	140002e6 	b	158f4 <probe::kernels::shared_core>

0000000000014d60 <probe::kernels::outlined::<probe::kernels::Format<15>>>:
   14d60:	528001e2 	mov	w2, #0xf                   	// #15
   14d64:	140002e4 	b	158f4 <probe::kernels::shared_core>

00000000000158f4 <probe::kernels::shared_core>:
   158f4:	b4000121 	cbz	x1, 15918 <probe::kernels::shared_core+0x24>
   158f8:	d2803668 	mov	x8, #0x1b3                 	// #435
   158fc:	f2c02008 	movk	x8, #0x100, lsl #32
   15900:	38401409 	ldrb	w9, [x0], #1
   15904:	f1000421 	subs	x1, x1, #0x1
   15908:	ca090049 	eor	x9, x2, x9
   1590c:	9b087d29 	mul	x9, x9, x8
   15910:	93c9e522 	ror	x2, x9, #57
   15914:	54ffff61 	b.ne	15900 <probe::kernels::shared_core+0xc>  // b.any
   15918:	aa0203e0 	mov	x0, x2
   1591c:	d65f03c0 	ret
