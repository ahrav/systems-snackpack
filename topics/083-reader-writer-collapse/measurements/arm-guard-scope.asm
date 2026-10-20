   15c1c:	d503201f 	nop
   15c20:	b9400328 	ldr	w8, [x25]
   15c24:	79400b29 	ldrh	w9, [x25, #4]
   15c28:	6b15011f 	cmp	w8, w21
   15c2c:	528d6c68 	mov	w8, #0x6b63                	// #27491
   15c30:	7a480120 	ccmp	w9, w8, #0x0, eq	// eq = none
   15c34:	540016a1 	b.ne	15f08 <std::sys::backtrace::__rust_begin_short_backtrace+0x728>  // b.any
   15c38:	b9400288 	ldr	w8, [x20]
   15c3c:	529fffa9 	mov	w9, #0xfffd                	// #65533
   15c40:	72a7ffe9 	movk	w9, #0x3fff, lsl #16
   15c44:	6b09011f 	cmp	w8, w9
   15c48:	54000348 	b.hi	15cb0 <std::sys::backtrace::__rust_begin_short_backtrace+0x4d0>  // b.pmore
   15c4c:	11000509 	add	w9, w8, #0x1
   15c50:	2a0803ea 	mov	w10, w8
   15c54:	88ea7e89 	casa	w10, w9, [x20]
   15c58:	6b08015f 	cmp	w10, w8
   15c5c:	540002a1 	b.ne	15cb0 <std::sys::backtrace::__rust_begin_short_backtrace+0x4d0>  // b.any
   15c60:	39402288 	ldrb	w8, [x20, #8]
   15c64:	350015e8 	cbnz	w8, 15f20 <std::sys::backtrace::__rust_begin_short_backtrace+0x740>
   15c68:	f94007e8 	ldr	x8, [sp, #8]
   15c6c:	3dc00100 	ldr	q0, [x8]
   15c70:	910203e8 	add	x8, sp, #0x80
   15c74:	3d8023e0 	str	q0, [sp, #128]
   15c78:	a94807e0 	ldp	x0, x1, [sp, #128]
   15c7c:	ca1802c2 	eor	x2, x22, x24
   15c80:	2a1303e3 	mov	w3, w19
   15c84:	940011d7 	bl	1a3e0 <reader_writer_collapse::compute>
   15c88:	b87b0288 	ldaddl	w27, w8, [x20]
   15c8c:	51000501 	sub	w1, w8, #0x1
   15c90:	12017828 	and	w8, w1, #0xbfffffff
   15c94:	6b1c011f 	cmp	w8, w28
   15c98:	54000160 	b.eq	15cc4 <std::sys::backtrace::__rust_begin_short_backtrace+0x4e4>  // b.none
   15c9c:	910006d6 	add	x22, x22, #0x1
   15ca0:	8b1a001a 	add	x26, x0, x26
   15ca4:	eb1602ff 	cmp	x23, x22
   15ca8:	54fffbc1 	b.ne	15c20 <std::sys::backtrace::__rust_begin_short_backtrace+0x440>  // b.any
   15cac:	14000010 	b	15cec <std::sys::backtrace::__rust_begin_short_backtrace+0x50c>
   15cb0:	aa1403e0 	mov	x0, x20
   15cb4:	97ffed2e 	bl	1116c <std::sys::sync::rwlock::futex::RwLock::read_contended>
   15cb8:	39402288 	ldrb	w8, [x20, #8]
   15cbc:	34fffd68 	cbz	w8, 15c68 <std::sys::backtrace::__rust_begin_short_backtrace+0x488>
   15cc0:	14000098 	b	15f20 <std::sys::backtrace::__rust_begin_short_backtrace+0x740>
   15cc4:	f90003e0 	str	x0, [sp]
   15cc8:	aa1403e0 	mov	x0, x20
   15ccc:	97ffed92 	bl	11314 <std::sys::sync::rwlock::futex::RwLock::wake_writer_or_readers>
   15cd0:	f94003e0 	ldr	x0, [sp]
   15cd4:	910006d6 	add	x22, x22, #0x1
   15cd8:	8b1a001a 	add	x26, x0, x26
   15cdc:	eb1602ff 	cmp	x23, x22
   15ce0:	54fffa01 	b.ne	15c20 <std::sys::backtrace::__rust_begin_short_backtrace+0x440>  // b.any
   15ce4:	14000002 	b	15cec <std::sys::backtrace::__rust_begin_short_backtrace+0x50c>
   15ce8:	aa1f03fa 	mov	x26, xzr
   15cec:	f90043fa 	str	x26, [sp, #128]
   15cf0:	910203e8 	add	x8, sp, #0x80
   15cf4:	f94043e0 	ldr	x0, [sp, #128]
   15cf8:	a95b4ff4 	ldp	x20, x19, [sp, #432]
   15cfc:	a95a57f6 	ldp	x22, x21, [sp, #416]
   15d00:	a9595ff8 	ldp	x24, x23, [sp, #400]
   15d04:	a95867fa 	ldp	x26, x25, [sp, #384]
   15d08:	a9576ffc 	ldp	x28, x27, [sp, #368]
   15d0c:	a9567bfd 	ldp	x29, x30, [sp, #352]
   15d10:	910703ff 	add	sp, sp, #0x1c0
   15d14:	d65f03c0 	ret
   15d18:	d00003dc 	adrp	x28, 8f000 <__dso_handle+0x1f38>
   15d1c:	f9401ab4 	ldr	x20, [x21, #48]
   15d20:	aa1f03fa 	mov	x26, xzr
   15d24:	aa1f03fb 	mov	x27, xzr
   15d28:	910203f5 	add	x21, sp, #0x80
   15d2c:	f9479b9c 	ldr	x28, [x28, #3888]
   15d30:	d503201f 	nop
   15d34:	d503201f 	nop
   15d38:	d503201f 	nop
   15d3c:	d503201f 	nop
   15d40:	b9400328 	ldr	w8, [x25]
   15d44:	39401329 	ldrb	w9, [x25, #4]
   15d48:	528eadaa 	mov	w10, #0x756d                	// #30061
   15d4c:	72acae8a 	movk	w10, #0x6574, lsl #16
   15d50:	6b0a011f 	cmp	w8, w10
   15d54:	52800f08 	mov	w8, #0x78                  	// #120
   15d58:	7a480120 	ccmp	w9, w8, #0x0, eq	// eq = none
   15d5c:	54000d61 	b.ne	15f08 <std::sys::backtrace::__rust_begin_short_backtrace+0x728>  // b.any
   15d60:	2a1f03e8 	mov	w8, wzr
   15d64:	52800029 	mov	w9, #0x1                   	// #1
   15d68:	88e87e89 	casa	w8, w9, [x20]
   15d6c:	7100011f 	cmp	w8, #0x0
   15d70:	54000321 	b.ne	15dd4 <std::sys::backtrace::__rust_begin_short_backtrace+0x5f4>  // b.any
   15d74:	f9400388 	ldr	x8, [x28]
   15d78:	f240f91f 	tst	x8, #0x7fffffffffffffff
   15d7c:	54000361 	b.ne	15de8 <std::sys::backtrace::__rust_begin_short_backtrace+0x608>  // b.any
   15d80:	2a1f03f6 	mov	w22, wzr
   15d84:	39401288 	ldrb	w8, [x20, #4]
   15d88:	35000e48 	cbnz	w8, 15f50 <std::sys::backtrace::__rust_begin_short_backtrace+0x770>
   15d8c:	3cc08280 	ldur	q0, [x20, #8]
   15d90:	3d8023e0 	str	q0, [sp, #128]
   15d94:	a94807e0 	ldp	x0, x1, [sp, #128]
   15d98:	ca180362 	eor	x2, x27, x24
   15d9c:	2a1303e3 	mov	w3, w19
   15da0:	94001190 	bl	1a3e0 <reader_writer_collapse::compute>
   15da4:	37000096 	tbnz	w22, #0, 15db4 <std::sys::backtrace::__rust_begin_short_backtrace+0x5d4>
   15da8:	f9400388 	ldr	x8, [x28]
   15dac:	f240f91f 	tst	x8, #0x7fffffffffffffff
   15db0:	54000361 	b.ne	15e1c <std::sys::backtrace::__rust_begin_short_backtrace+0x63c>  // b.any
   15db4:	b87f8288 	swpl	wzr, w8, [x20]
   15db8:	7100091f 	cmp	w8, #0x2
   15dbc:	54000200 	b.eq	15dfc <std::sys::backtrace::__rust_begin_short_backtrace+0x61c>  // b.none
   15dc0:	9100077b 	add	x27, x27, #0x1
   15dc4:	8b1a001a 	add	x26, x0, x26
   15dc8:	eb1b02ff 	cmp	x23, x27
   15dcc:	54fffba1 	b.ne	15d40 <std::sys::backtrace::__rust_begin_short_backtrace+0x560>  // b.any
   15dd0:	17ffffc7 	b	15cec <std::sys::backtrace::__rust_begin_short_backtrace+0x50c>
   15dd4:	aa1403e0 	mov	x0, x20
   15dd8:	97ffec9f 	bl	11054 <std::sys::sync::mutex::futex::Mutex::lock_contended>
   15ddc:	f9400388 	ldr	x8, [x28]
   15de0:	f240f91f 	tst	x8, #0x7fffffffffffffff
   15de4:	54fffce0 	b.eq	15d80 <std::sys::backtrace::__rust_begin_short_backtrace+0x5a0>  // b.none
   15de8:	97ffee65 	bl	1177c <std::panicking::panic_count::is_zero_slow_path>
   15dec:	52000016 	eor	w22, w0, #0x1
   15df0:	39401288 	ldrb	w8, [x20, #4]
   15df4:	34fffcc8 	cbz	w8, 15d8c <std::sys::backtrace::__rust_begin_short_backtrace+0x5ac>
   15df8:	14000056 	b	15f50 <std::sys::backtrace::__rust_begin_short_backtrace+0x770>
   15dfc:	aa0003f6 	mov	x22, x0
   15e00:	aa1403e0 	mov	x0, x20
   15e04:	97ffecd5 	bl	11158 <std::sys::sync::mutex::futex::Mutex::wake>
   15e08:	9100077b 	add	x27, x27, #0x1
   15e0c:	8b1a02da 	add	x26, x22, x26
   15e10:	eb1b02ff 	cmp	x23, x27
   15e14:	54fff961 	b.ne	15d40 <std::sys::backtrace::__rust_begin_short_backtrace+0x560>  // b.any
   15e18:	17ffffb5 	b	15cec <std::sys::backtrace::__rust_begin_short_backtrace+0x50c>
   15e1c:	aa0003f6 	mov	x22, x0
   15e20:	97ffee57 	bl	1177c <std::panicking::panic_count::is_zero_slow_path>
   15e24:	2a0003e8 	mov	w8, w0
   15e28:	aa1603e0 	mov	x0, x22
   15e2c:	3707fc48 	tbnz	w8, #0, 15db4 <std::sys::backtrace::__rust_begin_short_backtrace+0x5d4>
   15e30:	52800028 	mov	w8, #0x1                   	// #1
   15e34:	39001288 	strb	w8, [x20, #4]
   15e38:	17ffffdf 	b	15db4 <std::sys::backtrace::__rust_begin_short_backtrace+0x5d4>
   15e3c:	f100211f 	cmp	x8, #0x8
   15e40:	54000641 	b.ne	15f08 <std::sys::backtrace::__rust_begin_short_backtrace+0x728>  // b.any
   15e44:	aa1f03fa 	mov	x26, xzr
   15e48:	aa1f03f5 	mov	x21, xzr
   15e4c:	f9400328 	ldr	x8, [x25]
   15e50:	d28dce69 	mov	x9, #0x6e73                	// #28275
   15e54:	f2ae0c29 	movk	x9, #0x7061, lsl #16
   15e58:	f2cd0e69 	movk	x9, #0x6873, lsl #32
   15e5c:	f2ee8de9 	movk	x9, #0x746f, lsl #48
   15e60:	eb09011f 	cmp	x8, x9
   15e64:	54000521 	b.ne	15f08 <std::sys::backtrace::__rust_begin_short_backtrace+0x728>  // b.any
   15e68:	b9400288 	ldr	w8, [x20]
   15e6c:	529fffa9 	mov	w9, #0xfffd                	// #65533
   15e70:	72a7ffe9 	movk	w9, #0x3fff, lsl #16
   15e74:	6b09011f 	cmp	w8, w9
   15e78:	54000388 	b.hi	15ee8 <std::sys::backtrace::__rust_begin_short_backtrace+0x708>  // b.pmore
   15e7c:	11000509 	add	w9, w8, #0x1
   15e80:	2a0803ea 	mov	w10, w8
   15e84:	88ea7e89 	casa	w10, w9, [x20]
   15e88:	6b08015f 	cmp	w10, w8
   15e8c:	540002e1 	b.ne	15ee8 <std::sys::backtrace::__rust_begin_short_backtrace+0x708>  // b.any
   15e90:	39402288 	ldrb	w8, [x20, #8]
   15e94:	35000768 	cbnz	w8, 15f80 <std::sys::backtrace::__rust_begin_short_backtrace+0x7a0>
   15e98:	12800008 	mov	w8, #0xffffffff            	// #-1
   15e9c:	a9416e96 	ldp	x22, x27, [x20, #16]
   15ea0:	52b00009 	mov	w9, #0x80000000            	// #-2147483648
   15ea4:	b8680288 	ldaddl	w8, w8, [x20]
   15ea8:	51000501 	sub	w1, w8, #0x1
   15eac:	12017828 	and	w8, w1, #0xbfffffff
   15eb0:	6b09011f 	cmp	w8, w9
   15eb4:	54000240 	b.eq	15efc <std::sys::backtrace::__rust_begin_short_backtrace+0x71c>  // b.none
   15eb8:	a9086ff6 	stp	x22, x27, [sp, #128]
   15ebc:	910203e8 	add	x8, sp, #0x80
   15ec0:	ca1802a2 	eor	x2, x21, x24
   15ec4:	2a1303e3 	mov	w3, w19
   15ec8:	910006bc 	add	x28, x21, #0x1
   15ecc:	a94807e0 	ldp	x0, x1, [sp, #128]
   15ed0:	94001144 	bl	1a3e0 <reader_writer_collapse::compute>
   15ed4:	8b1a001a 	add	x26, x0, x26
   15ed8:	eb1c02ff 	cmp	x23, x28
   15edc:	aa1c03f5 	mov	x21, x28
   15ee0:	54fffb61 	b.ne	15e4c <std::sys::backtrace::__rust_begin_short_backtrace+0x66c>  // b.any
   15ee4:	17ffff82 	b	15cec <std::sys::backtrace::__rust_begin_short_backtrace+0x50c>
   15ee8:	aa1403e0 	mov	x0, x20
   15eec:	97ffeca0 	bl	1116c <std::sys::sync::rwlock::futex::RwLock::read_contended>
   15ef0:	39402288 	ldrb	w8, [x20, #8]
   15ef4:	34fffd28 	cbz	w8, 15e98 <std::sys::backtrace::__rust_begin_short_backtrace+0x6b8>
   15ef8:	14000022 	b	15f80 <std::sys::backtrace::__rust_begin_short_backtrace+0x7a0>
   15efc:	aa1403e0 	mov	x0, x20
   15f00:	97ffed05 	bl	11314 <std::sys::sync::rwlock::futex::RwLock::wake_writer_or_readers>
   15f04:	17ffffed 	b	15eb8 <std::sys::backtrace::__rust_begin_short_backtrace+0x6d8>
   15f08:	b0000260 	adrp	x0, 62000 <_fini+0xad68>
   15f0c:	9100c800 	add	x0, x0, #0x32
   15f10:	900003c2 	adrp	x2, 8d000 <GCC_except_table0+0x19a28>
   15f14:	91154042 	add	x2, x2, #0x550
   15f18:	52800501 	mov	w1, #0x28                  	// #40
   15f1c:	97fffccb 	bl	15248 <core::panicking::panic>
   15f20:	f94007e8 	ldr	x8, [sp, #8]
   15f24:	a90853e8 	stp	x8, x20, [sp, #128]
   15f28:	b0000260 	adrp	x0, 62000 <_fini+0xad68>
