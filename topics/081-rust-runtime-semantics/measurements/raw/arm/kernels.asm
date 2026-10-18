0000000000014d00 <topic081_rust_runtime::Policy::batch>:
   14d00:	b4000102 	cbz	x2, 14d20 <topic081_rust_runtime::Policy::batch+0x20>
   14d04:	f9400008 	ldr	x8, [x0]
   14d08:	04a0e3eb 	cntw	x11
   14d0c:	eb0b005f 	cmp	x2, x11
   14d10:	540000c2 	b.cs	14d28 <topic081_rust_runtime::Policy::batch+0x28>  // b.hs, b.nlast
   14d14:	aa1f03e9 	mov	x9, xzr
   14d18:	aa1f03e0 	mov	x0, xzr
   14d1c:	1400001a 	b	14d84 <topic081_rust_runtime::Policy::batch+0x84>
   14d20:	aa1f03e0 	mov	x0, xzr
   14d24:	d65f03c0 	ret
   14d28:	d1000569 	sub	x9, x11, #0x1
   14d2c:	05e03901 	mov	z1.d, x8
   14d30:	6f00e400 	movi	v0.2d, #0x0
   14d34:	6f00e402 	movi	v2.2d, #0x0
   14d38:	aa0103ed 	mov	x13, x1
   14d3c:	8a09004a 	and	x10, x2, x9
   14d40:	04bf504c 	rdvl	x12, #2
   14d44:	cb0a0049 	sub	x9, x2, x10
   14d48:	aa0903ee 	mov	x14, x9
   14d4c:	858041a3 	ldr	z3, [x13]
   14d50:	858045a4 	ldr	z4, [x13, #1, mul vl]
   14d54:	04e10000 	add	z0.d, z0.d, z1.d
   14d58:	04e10042 	add	z2.d, z2.d, z1.d
   14d5c:	eb0b01ce 	subs	x14, x14, x11
   14d60:	8b0c01ad 	add	x13, x13, x12
   14d64:	04e30000 	add	z0.d, z0.d, z3.d
   14d68:	04e40042 	add	z2.d, z2.d, z4.d
   14d6c:	54ffff01 	b.ne	14d4c <topic081_rust_runtime::Policy::batch+0x4c>  // b.any
   14d70:	04e00040 	add	z0.d, z2.d, z0.d
   14d74:	25d8e3e0 	ptrue	p0.d
   14d78:	04c12000 	uaddv	d0, p0, z0.d
   14d7c:	9e660000 	fmov	x0, d0
   14d80:	b400010a 	cbz	x10, 14da0 <topic081_rust_runtime::Policy::batch+0xa0>
   14d84:	cb09004a 	sub	x10, x2, x9
   14d88:	8b090c29 	add	x9, x1, x9, lsl #3
   14d8c:	f840852b 	ldr	x11, [x9], #8
   14d90:	8b08000c 	add	x12, x0, x8
   14d94:	f100054a 	subs	x10, x10, #0x1
   14d98:	8b0b0180 	add	x0, x12, x11
   14d9c:	54ffff81 	b.ne	14d8c <topic081_rust_runtime::Policy::batch+0x8c>  // b.any
   14da0:	d65f03c0 	ret
   14da4:	d503201f 	nop
   14da8:	d503201f 	nop
   14dac:	d503201f 	nop
   14db0:	d503201f 	nop
   14db4:	d503201f 	nop
   14db8:	d503201f 	nop
   14dbc:	d503201f 	nop


0000000000014dc0 <topic081_rust_runtime::Policy::batch>:
   14dc0:	b4000182 	cbz	x2, 14df0 <topic081_rust_runtime::Policy::batch+0x30>
   14dc4:	f9400008 	ldr	x8, [x0]
   14dc8:	d29da069 	mov	x9, #0xed03                	// #60675
   14dcc:	04a0e3ec 	cntw	x12
   14dd0:	f2ba3249 	movk	x9, #0xd192, lsl #16
   14dd4:	f2c94649 	movk	x9, #0x4a32, lsl #32
   14dd8:	eb0c005f 	cmp	x2, x12
   14ddc:	f2fa36a9 	movk	x9, #0xd1b5, lsl #48
   14de0:	540000c2 	b.cs	14df8 <topic081_rust_runtime::Policy::batch+0x38>  // b.hs, b.nlast
   14de4:	aa1f03ea 	mov	x10, xzr
   14de8:	aa1f03e0 	mov	x0, xzr
   14dec:	14000023 	b	14e78 <topic081_rust_runtime::Policy::batch+0xb8>
   14df0:	aa1f03e0 	mov	x0, xzr
   14df4:	d65f03c0 	ret
   14df8:	d100058a 	sub	x10, x12, #0x1
   14dfc:	05e03900 	mov	z0.d, x8
   14e00:	6f00e401 	movi	v1.2d, #0x0
   14e04:	6f00e403 	movi	v3.2d, #0x0
   14e08:	aa0103ee 	mov	x14, x1
   14e0c:	8a0a004b 	and	x11, x2, x10
   14e10:	05e03922 	mov	z2.d, x9
   14e14:	cb0b004a 	sub	x10, x2, x11
   14e18:	25d8e3e0 	ptrue	p0.d
   14e1c:	aa0a03ef 	mov	x15, x10
   14e20:	04bf504d 	rdvl	x13, #2
   14e24:	858041c4 	ldr	z4, [x14]
   14e28:	858045c5 	ldr	z5, [x14, #1, mul vl]
   14e2c:	eb0c01ef 	subs	x15, x15, x12
   14e30:	8b0d01ce 	add	x14, x14, x13
   14e34:	04d00004 	mul	z4.d, p0/m, z4.d, z0.d
   14e38:	04d00005 	mul	z5.d, p0/m, z5.d, z0.d
   14e3c:	04ad9486 	lsr	z6.d, z4.d, #51
   14e40:	04ad9c84 	lsl	z4.d, z4.d, #13
   14e44:	04663084 	orr	z4.d, z4.d, z6.d
   14e48:	04ad94a6 	lsr	z6.d, z5.d, #51
   14e4c:	04ad9ca5 	lsl	z5.d, z5.d, #13
   14e50:	046630a5 	orr	z5.d, z5.d, z6.d
   14e54:	04a23084 	eor	z4.d, z4.d, z2.d
   14e58:	04a230a5 	eor	z5.d, z5.d, z2.d
   14e5c:	04e10081 	add	z1.d, z4.d, z1.d
   14e60:	04e300a3 	add	z3.d, z5.d, z3.d
   14e64:	54fffe01 	b.ne	14e24 <topic081_rust_runtime::Policy::batch+0x64>  // b.any
   14e68:	04e10060 	add	z0.d, z3.d, z1.d
   14e6c:	04c12000 	uaddv	d0, p0, z0.d
   14e70:	9e660000 	fmov	x0, d0
   14e74:	b400012b 	cbz	x11, 14e98 <topic081_rust_runtime::Policy::batch+0xd8>
   14e78:	cb0a004b 	sub	x11, x2, x10
   14e7c:	8b0a0c2a 	add	x10, x1, x10, lsl #3
   14e80:	f840854c 	ldr	x12, [x10], #8
   14e84:	f100056b 	subs	x11, x11, #0x1
   14e88:	9b087d8c 	mul	x12, x12, x8
   14e8c:	cacccd2c 	eor	x12, x9, x12, ror #51
   14e90:	8b000180 	add	x0, x12, x0
   14e94:	54ffff61 	b.ne	14e80 <topic081_rust_runtime::Policy::batch+0xc0>  // b.any
   14e98:	d65f03c0 	ret
   14e9c:	d503201f 	nop


0000000000014ea0 <topic081_rust_runtime::generic>:
   14ea0:	b4000162 	cbz	x2, 14ecc <topic081_rust_runtime::generic+0x2c>
   14ea4:	d29da069 	mov	x9, #0xed03                	// #60675
   14ea8:	04a0e3e8 	cntw	x8
   14eac:	f2ba3249 	movk	x9, #0xd192, lsl #16
   14eb0:	f2c94649 	movk	x9, #0x4a32, lsl #32
   14eb4:	eb08005f 	cmp	x2, x8
   14eb8:	f2fa36a9 	movk	x9, #0xd1b5, lsl #48
   14ebc:	540000e2 	b.cs	14ed8 <topic081_rust_runtime::generic+0x38>  // b.hs, b.nlast
   14ec0:	aa1f03ea 	mov	x10, xzr
   14ec4:	aa1f03e8 	mov	x8, xzr
   14ec8:	14000024 	b	14f58 <topic081_rust_runtime::generic+0xb8>
   14ecc:	aa1f03e8 	mov	x8, xzr
   14ed0:	aa0803e0 	mov	x0, x8
   14ed4:	d65f03c0 	ret
   14ed8:	d100050a 	sub	x10, x8, #0x1
   14edc:	05e03800 	mov	z0.d, x0
   14ee0:	6f00e401 	movi	v1.2d, #0x0
   14ee4:	6f00e403 	movi	v3.2d, #0x0
   14ee8:	aa0103ed 	mov	x13, x1
   14eec:	8a0a004b 	and	x11, x2, x10
   14ef0:	05e03922 	mov	z2.d, x9
   14ef4:	cb0b004a 	sub	x10, x2, x11
   14ef8:	25d8e3e0 	ptrue	p0.d
   14efc:	aa0a03ee 	mov	x14, x10
   14f00:	04bf504c 	rdvl	x12, #2
   14f04:	858041a4 	ldr	z4, [x13]
   14f08:	858045a5 	ldr	z5, [x13, #1, mul vl]
   14f0c:	eb0801ce 	subs	x14, x14, x8
   14f10:	8b0c01ad 	add	x13, x13, x12
   14f14:	04d00004 	mul	z4.d, p0/m, z4.d, z0.d
   14f18:	04d00005 	mul	z5.d, p0/m, z5.d, z0.d
   14f1c:	04ad9486 	lsr	z6.d, z4.d, #51
   14f20:	04ad9c84 	lsl	z4.d, z4.d, #13
   14f24:	04663084 	orr	z4.d, z4.d, z6.d
   14f28:	04ad94a6 	lsr	z6.d, z5.d, #51
   14f2c:	04ad9ca5 	lsl	z5.d, z5.d, #13
   14f30:	046630a5 	orr	z5.d, z5.d, z6.d
   14f34:	04a23084 	eor	z4.d, z4.d, z2.d
   14f38:	04a230a5 	eor	z5.d, z5.d, z2.d
   14f3c:	04e10081 	add	z1.d, z4.d, z1.d
   14f40:	04e300a3 	add	z3.d, z5.d, z3.d
   14f44:	54fffe01 	b.ne	14f04 <topic081_rust_runtime::generic+0x64>  // b.any
   14f48:	04e10060 	add	z0.d, z3.d, z1.d
   14f4c:	04c12000 	uaddv	d0, p0, z0.d
   14f50:	9e660008 	fmov	x8, d0
   14f54:	b400012b 	cbz	x11, 14f78 <topic081_rust_runtime::generic+0xd8>
   14f58:	cb0a004b 	sub	x11, x2, x10
   14f5c:	8b0a0c2a 	add	x10, x1, x10, lsl #3
   14f60:	f840854c 	ldr	x12, [x10], #8
   14f64:	f100056b 	subs	x11, x11, #0x1
   14f68:	9b007d8c 	mul	x12, x12, x0
   14f6c:	cacccd2c 	eor	x12, x9, x12, ror #51
   14f70:	8b080188 	add	x8, x12, x8
   14f74:	54ffff61 	b.ne	14f60 <topic081_rust_runtime::generic+0xc0>  // b.any
   14f78:	aa0803e0 	mov	x0, x8
   14f7c:	d65f03c0 	ret


0000000000014f80 <topic081_rust_runtime::generic>:
   14f80:	b40000e2 	cbz	x2, 14f9c <topic081_rust_runtime::generic+0x1c>
   14f84:	04a0e3e8 	cntw	x8
   14f88:	eb08005f 	cmp	x2, x8
   14f8c:	540000e2 	b.cs	14fa8 <topic081_rust_runtime::generic+0x28>  // b.hs, b.nlast
   14f90:	aa1f03e9 	mov	x9, xzr
   14f94:	aa1f03e8 	mov	x8, xzr
   14f98:	1400001b 	b	15004 <topic081_rust_runtime::generic+0x84>
   14f9c:	aa1f03e8 	mov	x8, xzr
   14fa0:	aa0803e0 	mov	x0, x8
   14fa4:	d65f03c0 	ret
   14fa8:	d1000509 	sub	x9, x8, #0x1
   14fac:	05e03801 	mov	z1.d, x0
   14fb0:	6f00e400 	movi	v0.2d, #0x0
   14fb4:	6f00e402 	movi	v2.2d, #0x0
   14fb8:	aa0103ec 	mov	x12, x1
   14fbc:	8a09004a 	and	x10, x2, x9
   14fc0:	04bf504b 	rdvl	x11, #2
   14fc4:	cb0a0049 	sub	x9, x2, x10
   14fc8:	aa0903ed 	mov	x13, x9
   14fcc:	85804183 	ldr	z3, [x12]
   14fd0:	85804584 	ldr	z4, [x12, #1, mul vl]
   14fd4:	04e10000 	add	z0.d, z0.d, z1.d
   14fd8:	04e10042 	add	z2.d, z2.d, z1.d
   14fdc:	eb0801ad 	subs	x13, x13, x8
   14fe0:	8b0b018c 	add	x12, x12, x11
   14fe4:	04e30000 	add	z0.d, z0.d, z3.d
   14fe8:	04e40042 	add	z2.d, z2.d, z4.d
   14fec:	54ffff01 	b.ne	14fcc <topic081_rust_runtime::generic+0x4c>  // b.any
   14ff0:	04e00040 	add	z0.d, z2.d, z0.d
   14ff4:	25d8e3e0 	ptrue	p0.d
   14ff8:	04c12000 	uaddv	d0, p0, z0.d
   14ffc:	9e660008 	fmov	x8, d0
   15000:	b400010a 	cbz	x10, 15020 <topic081_rust_runtime::generic+0xa0>
   15004:	cb09004a 	sub	x10, x2, x9
   15008:	8b090c29 	add	x9, x1, x9, lsl #3
   1500c:	f840852b 	ldr	x11, [x9], #8
   15010:	8b000108 	add	x8, x8, x0
   15014:	f100054a 	subs	x10, x10, #0x1
   15018:	8b0b0108 	add	x8, x8, x11
   1501c:	54ffff81 	b.ne	1500c <topic081_rust_runtime::generic+0x8c>  // b.any
   15020:	aa0803e0 	mov	x0, x8
   15024:	d65f03c0 	ret
   15028:	d503201f 	nop
   1502c:	d503201f 	nop


0000000000015e90 <<topic081_rust_runtime::Add as topic081_rust_runtime::Policy>::apply>:
   15e90:	f9400008 	ldr	x8, [x0]
   15e94:	8b010100 	add	x0, x8, x1
   15e98:	d65f03c0 	ret
   15e9c:	d503201f 	nop


0000000000015ea0 <<topic081_rust_runtime::Mix as topic081_rust_runtime::Policy>::apply>:
   15ea0:	f9400008 	ldr	x8, [x0]
   15ea4:	d29da069 	mov	x9, #0xed03                	// #60675
   15ea8:	f2ba3249 	movk	x9, #0xd192, lsl #16
   15eac:	f2c94649 	movk	x9, #0x4a32, lsl #32
   15eb0:	f2fa36a9 	movk	x9, #0xd1b5, lsl #48
   15eb4:	9b017d08 	mul	x8, x8, x1
   15eb8:	cac8cd20 	eor	x0, x9, x8, ror #51
   15ebc:	d65f03c0 	ret


0000000000015f60 <topic081_rust_runtime::enumerated>:
   15f60:	b9400008 	ldr	w8, [x0]
   15f64:	7100051f 	cmp	w8, #0x1
   15f68:	540001a1 	b.ne	15f9c <topic081_rust_runtime::enumerated+0x3c>  // b.any
   15f6c:	b4000282 	cbz	x2, 15fbc <topic081_rust_runtime::enumerated+0x5c>
   15f70:	f9400408 	ldr	x8, [x0, #8]
   15f74:	d29da069 	mov	x9, #0xed03                	// #60675
   15f78:	04a0e3ec 	cntw	x12
   15f7c:	f2ba3249 	movk	x9, #0xd192, lsl #16
   15f80:	f2c94649 	movk	x9, #0x4a32, lsl #32
   15f84:	eb0c005f 	cmp	x2, x12
   15f88:	f2fa36a9 	movk	x9, #0xd1b5, lsl #48
   15f8c:	540001c2 	b.cs	15fc4 <topic081_rust_runtime::enumerated+0x64>  // b.hs, b.nlast
   15f90:	aa1f03ea 	mov	x10, xzr
   15f94:	aa1f03e0 	mov	x0, xzr
   15f98:	1400002f 	b	16054 <topic081_rust_runtime::enumerated+0xf4>
   15f9c:	b4000102 	cbz	x2, 15fbc <topic081_rust_runtime::enumerated+0x5c>
   15fa0:	f9400408 	ldr	x8, [x0, #8]
   15fa4:	04a0e3eb 	cntw	x11
   15fa8:	eb0b005f 	cmp	x2, x11
   15fac:	54000682 	b.cs	1607c <topic081_rust_runtime::enumerated+0x11c>  // b.hs, b.nlast
   15fb0:	aa1f03e9 	mov	x9, xzr
   15fb4:	aa1f03e0 	mov	x0, xzr
   15fb8:	14000048 	b	160d8 <topic081_rust_runtime::enumerated+0x178>
   15fbc:	aa1f03e0 	mov	x0, xzr
   15fc0:	d65f03c0 	ret
   15fc4:	d100058a 	sub	x10, x12, #0x1
   15fc8:	05e03900 	mov	z0.d, x8
   15fcc:	6f00e401 	movi	v1.2d, #0x0
   15fd0:	6f00e403 	movi	v3.2d, #0x0
   15fd4:	aa0103ee 	mov	x14, x1
   15fd8:	8a0a004b 	and	x11, x2, x10
   15fdc:	05e03922 	mov	z2.d, x9
   15fe0:	cb0b004a 	sub	x10, x2, x11
   15fe4:	25d8e3e0 	ptrue	p0.d
   15fe8:	aa0a03ef 	mov	x15, x10
   15fec:	04bf504d 	rdvl	x13, #2
   15ff0:	d503201f 	nop
   15ff4:	d503201f 	nop
   15ff8:	d503201f 	nop
   15ffc:	d503201f 	nop
   16000:	858041c4 	ldr	z4, [x14]
   16004:	858045c5 	ldr	z5, [x14, #1, mul vl]
   16008:	eb0c01ef 	subs	x15, x15, x12
   1600c:	8b0d01ce 	add	x14, x14, x13
   16010:	04d00004 	mul	z4.d, p0/m, z4.d, z0.d
   16014:	04d00005 	mul	z5.d, p0/m, z5.d, z0.d
   16018:	04ad9486 	lsr	z6.d, z4.d, #51
   1601c:	04ad9c84 	lsl	z4.d, z4.d, #13
   16020:	04663084 	orr	z4.d, z4.d, z6.d
   16024:	04ad94a6 	lsr	z6.d, z5.d, #51
   16028:	04ad9ca5 	lsl	z5.d, z5.d, #13
   1602c:	046630a5 	orr	z5.d, z5.d, z6.d
   16030:	04a23084 	eor	z4.d, z4.d, z2.d
   16034:	04a230a5 	eor	z5.d, z5.d, z2.d
   16038:	04e10081 	add	z1.d, z4.d, z1.d
   1603c:	04e300a3 	add	z3.d, z5.d, z3.d
   16040:	54fffe01 	b.ne	16000 <topic081_rust_runtime::enumerated+0xa0>  // b.any
   16044:	04e10060 	add	z0.d, z3.d, z1.d
   16048:	04c12000 	uaddv	d0, p0, z0.d
   1604c:	9e660000 	fmov	x0, d0
   16050:	b400052b 	cbz	x11, 160f4 <topic081_rust_runtime::enumerated+0x194>
   16054:	cb0a004b 	sub	x11, x2, x10
   16058:	8b0a0c2a 	add	x10, x1, x10, lsl #3
   1605c:	d503201f 	nop
   16060:	f840854c 	ldr	x12, [x10], #8
   16064:	f100056b 	subs	x11, x11, #0x1
   16068:	9b087d8c 	mul	x12, x12, x8
   1606c:	cacccd2c 	eor	x12, x9, x12, ror #51
   16070:	8b000180 	add	x0, x12, x0
   16074:	54ffff61 	b.ne	16060 <topic081_rust_runtime::enumerated+0x100>  // b.any
   16078:	1400001f 	b	160f4 <topic081_rust_runtime::enumerated+0x194>
   1607c:	d1000569 	sub	x9, x11, #0x1
   16080:	05e03901 	mov	z1.d, x8
   16084:	6f00e400 	movi	v0.2d, #0x0
   16088:	6f00e402 	movi	v2.2d, #0x0
   1608c:	aa0103ed 	mov	x13, x1
   16090:	8a09004a 	and	x10, x2, x9
   16094:	04bf504c 	rdvl	x12, #2
   16098:	cb0a0049 	sub	x9, x2, x10
   1609c:	aa0903ee 	mov	x14, x9
   160a0:	858041a3 	ldr	z3, [x13]
   160a4:	858045a4 	ldr	z4, [x13, #1, mul vl]
   160a8:	04e10000 	add	z0.d, z0.d, z1.d
   160ac:	04e10042 	add	z2.d, z2.d, z1.d
   160b0:	eb0b01ce 	subs	x14, x14, x11
   160b4:	8b0c01ad 	add	x13, x13, x12
   160b8:	04e30000 	add	z0.d, z0.d, z3.d
   160bc:	04e40042 	add	z2.d, z2.d, z4.d
   160c0:	54ffff01 	b.ne	160a0 <topic081_rust_runtime::enumerated+0x140>  // b.any
   160c4:	04e00040 	add	z0.d, z2.d, z0.d
   160c8:	25d8e3e0 	ptrue	p0.d
   160cc:	04c12000 	uaddv	d0, p0, z0.d
   160d0:	9e660000 	fmov	x0, d0
   160d4:	b400010a 	cbz	x10, 160f4 <topic081_rust_runtime::enumerated+0x194>
   160d8:	cb09004a 	sub	x10, x2, x9
   160dc:	8b090c29 	add	x9, x1, x9, lsl #3
   160e0:	f840852b 	ldr	x11, [x9], #8
   160e4:	8b08000c 	add	x12, x0, x8
   160e8:	f100054a 	subs	x10, x10, #0x1
   160ec:	8b0b0180 	add	x0, x12, x11
   160f0:	54ffff81 	b.ne	160e0 <topic081_rust_runtime::enumerated+0x180>  // b.any
   160f4:	d65f03c0 	ret
   160f8:	d503201f 	nop
   160fc:	d503201f 	nop


0000000000016100 <topic081_rust_runtime::data>:
   16100:	a9bc7bfd 	stp	x29, x30, [sp, #-64]!
   16104:	f9000bf7 	str	x23, [sp, #16]
   16108:	a90257f6 	stp	x22, x21, [sp, #32]
   1610c:	a9034ff4 	stp	x20, x19, [sp, #48]
   16110:	910003fd 	mov	x29, sp
   16114:	aa1f03f4 	mov	x20, xzr
   16118:	d37df013 	lsl	x19, x0, #3
   1611c:	d37dfc09 	lsr	x9, x0, #61
   16120:	b50002a9 	cbnz	x9, 16174 <topic081_rust_runtime::data+0x74>
   16124:	b27defe9 	mov	x9, #0x7ffffffffffffff8    	// #9223372036854775800
   16128:	eb09027f 	cmp	x19, x9
   1612c:	54000248 	b.hi	16174 <topic081_rust_runtime::data+0x74>  // b.pmore
   16130:	b4000293 	cbz	x19, 16180 <topic081_rust_runtime::data+0x80>
   16134:	aa0003f5 	mov	x21, x0
   16138:	aa0803f6 	mov	x22, x8
   1613c:	aa0103f7 	mov	x23, x1
   16140:	97ffff84 	bl	15f50 <__rustc::__rust_no_alloc_shim_is_unstable_v2>
   16144:	aa1303e0 	mov	x0, x19
   16148:	52800101 	mov	w1, #0x8                   	// #8
   1614c:	52800114 	mov	w20, #0x8                   	// #8
   16150:	97ffff6c 	bl	15f00 <__rustc::__rust_alloc>
   16154:	aa0003e9 	mov	x9, x0
   16158:	b40000e0 	cbz	x0, 16174 <topic081_rust_runtime::data+0x74>
   1615c:	aa1703e1 	mov	x1, x23
   16160:	aa1603e8 	mov	x8, x22
   16164:	aa1503e0 	mov	x0, x21
   16168:	aa1503ea 	mov	x10, x21
   1616c:	b5000115 	cbnz	x21, 1618c <topic081_rust_runtime::data+0x8c>
   16170:	14000033 	b	1623c <topic081_rust_runtime::data+0x13c>
   16174:	aa1403e0 	mov	x0, x20
   16178:	aa1303e1 	mov	x1, x19
   1617c:	97fff91a 	bl	145e4 <alloc::raw_vec::handle_error>
   16180:	aa1f03ea 	mov	x10, xzr
   16184:	52800109 	mov	w9, #0x8                   	// #8
   16188:	b40005a0 	cbz	x0, 1623c <topic081_rust_runtime::data+0x13c>
   1618c:	d28f82ab 	mov	x11, #0x7c15                	// #31765
   16190:	04a0e3ed 	cntw	x13
   16194:	f2afe94b 	movk	x11, #0x7f4a, lsl #16
   16198:	f2cf372b 	movk	x11, #0x79b9, lsl #32
   1619c:	eb0d001f 	cmp	x0, x13
   161a0:	f2f3c6eb 	movk	x11, #0x9e37, lsl #48
   161a4:	54000062 	b.cs	161b0 <topic081_rust_runtime::data+0xb0>  // b.hs, b.nlast
   161a8:	aa1f03ec 	mov	x12, xzr
   161ac:	14000019 	b	16210 <topic081_rust_runtime::data+0x110>
   161b0:	04e0e3ef 	cntd	x15
   161b4:	04e14001 	index	z1.d, #0, #1
   161b8:	d10005ac 	sub	x12, x13, #0x1
   161bc:	05e03820 	mov	z0.d, x1
   161c0:	05e039a3 	mov	z3.d, x13
   161c4:	8a0c000e 	and	x14, x0, x12
   161c8:	cb0e000c 	sub	x12, x0, x14
   161cc:	aa0c03f0 	mov	x16, x12
   161d0:	05e039e2 	mov	z2.d, x15
   161d4:	aa0903ef 	mov	x15, x9
   161d8:	05e03964 	mov	z4.d, x11
   161dc:	25d8e3e0 	ptrue	p0.d
   161e0:	04bf5051 	rdvl	x17, #2
   161e4:	04e20025 	add	z5.d, z1.d, z2.d
   161e8:	0420bc06 	movprfx	z6, z0
   161ec:	04c44026 	mla	z6.d, p0/m, z1.d, z4.d
   161f0:	04e30021 	add	z1.d, z1.d, z3.d
   161f4:	eb0d0210 	subs	x16, x16, x13
   161f8:	e58041e6 	str	z6, [x15]
   161fc:	04c4c005 	mad	z5.d, p0/m, z4.d, z0.d
   16200:	e58045e5 	str	z5, [x15, #1, mul vl]
   16204:	8b1101ef 	add	x15, x15, x17
   16208:	54fffee1 	b.ne	161e4 <topic081_rust_runtime::data+0xe4>  // b.any
   1620c:	b400018e 	cbz	x14, 1623c <topic081_rust_runtime::data+0x13c>
   16210:	d2907d6d 	mov	x13, #0x83eb                	// #33771
   16214:	cb0c000e 	sub	x14, x0, x12
   16218:	f2b016ad 	movk	x13, #0x80b5, lsl #16
   1621c:	f2d0c8cd 	movk	x13, #0x8646, lsl #32
   16220:	f2ec390d 	movk	x13, #0x61c8, lsl #48
   16224:	9b0d858d 	msub	x13, x12, x13, x1
   16228:	8b0c0d2c 	add	x12, x9, x12, lsl #3
   1622c:	f800858d 	str	x13, [x12], #8
   16230:	8b0b01ad 	add	x13, x13, x11
   16234:	f10005ce 	subs	x14, x14, #0x1
   16238:	54ffffa1 	b.ne	1622c <topic081_rust_runtime::data+0x12c>  // b.any
   1623c:	a900250a 	stp	x10, x9, [x8]
   16240:	f9000900 	str	x0, [x8, #16]
   16244:	a9434ff4 	ldp	x20, x19, [sp, #48]
   16248:	a94257f6 	ldp	x22, x21, [sp, #32]
   1624c:	f9400bf7 	ldr	x23, [sp, #16]
   16250:	a8c47bfd 	ldp	x29, x30, [sp], #64
   16254:	d65f03c0 	ret
   16258:	d503201f 	nop
   1625c:	d503201f 	nop


0000000000016260 <topic081_rust_runtime::dot_zip>:
   16260:	d10083ff 	sub	sp, sp, #0x20
   16264:	a9017bfd 	stp	x29, x30, [sp, #16]
   16268:	910043fd 	add	x29, sp, #0x10
   1626c:	eb03003f 	cmp	x1, x3
   16270:	a9000fe1 	stp	x1, x3, [sp]
   16274:	540006a1 	b.ne	16348 <topic081_rust_runtime::dot_zip+0xe8>  // b.any
   16278:	b40000e1 	cbz	x1, 16294 <topic081_rust_runtime::dot_zip+0x34>
   1627c:	04a0e3e8 	cntw	x8
   16280:	eb08003f 	cmp	x1, x8
   16284:	54000122 	b.cs	162a8 <topic081_rust_runtime::dot_zip+0x48>  // b.hs, b.nlast
   16288:	aa1f03e8 	mov	x8, xzr
   1628c:	aa1f03e9 	mov	x9, xzr
   16290:	14000022 	b	16318 <topic081_rust_runtime::dot_zip+0xb8>
   16294:	aa1f03e8 	mov	x8, xzr
   16298:	aa0803e0 	mov	x0, x8
   1629c:	a9417bfd 	ldp	x29, x30, [sp, #16]
   162a0:	910083ff 	add	sp, sp, #0x20
   162a4:	d65f03c0 	ret
   162a8:	d1000509 	sub	x9, x8, #0x1
   162ac:	6f00e400 	movi	v0.2d, #0x0
   162b0:	25d8e3e0 	ptrue	p0.d
   162b4:	6f00e401 	movi	v1.2d, #0x0
   162b8:	aa0003ec 	mov	x12, x0
   162bc:	aa0203ed 	mov	x13, x2
   162c0:	8a09002a 	and	x10, x1, x9
   162c4:	04bf504b 	rdvl	x11, #2
   162c8:	cb0a0029 	sub	x9, x1, x10
   162cc:	aa0903ee 	mov	x14, x9
   162d0:	d503201f 	nop
   162d4:	d503201f 	nop
   162d8:	d503201f 	nop
   162dc:	d503201f 	nop
   162e0:	85804182 	ldr	z2, [x12]
   162e4:	85804583 	ldr	z3, [x12, #1, mul vl]
   162e8:	eb0801ce 	subs	x14, x14, x8
   162ec:	8b0b018c 	add	x12, x12, x11
   162f0:	858041a4 	ldr	z4, [x13]
   162f4:	04c24080 	mla	z0.d, p0/m, z4.d, z2.d
   162f8:	858045a5 	ldr	z5, [x13, #1, mul vl]
   162fc:	04c340a1 	mla	z1.d, p0/m, z5.d, z3.d
   16300:	8b0b01ad 	add	x13, x13, x11
   16304:	54fffee1 	b.ne	162e0 <topic081_rust_runtime::dot_zip+0x80>  // b.any
   16308:	04e00020 	add	z0.d, z1.d, z0.d
   1630c:	04c12000 	uaddv	d0, p0, z0.d
   16310:	9e660008 	fmov	x8, d0
   16314:	b400012a 	cbz	x10, 16338 <topic081_rust_runtime::dot_zip+0xd8>
   16318:	8b090c0a 	add	x10, x0, x9, lsl #3
   1631c:	8b090c4b 	add	x11, x2, x9, lsl #3
   16320:	cb090029 	sub	x9, x1, x9
   16324:	f840854c 	ldr	x12, [x10], #8
   16328:	f840856d 	ldr	x13, [x11], #8
   1632c:	f1000529 	subs	x9, x9, #0x1
   16330:	9b0c21a8 	madd	x8, x13, x12, x8
   16334:	54ffff81 	b.ne	16324 <topic081_rust_runtime::dot_zip+0xc4>  // b.any
   16338:	aa0803e0 	mov	x0, x8
   1633c:	a9417bfd 	ldp	x29, x30, [sp, #16]
   16340:	910083ff 	add	sp, sp, #0x20
   16344:	d65f03c0 	ret
   16348:	f00002a5 	adrp	x5, 6d000 <GCC_except_table0+0xd10c>
   1634c:	913220a5 	add	x5, x5, #0xc88
   16350:	910003e1 	mov	x1, sp
   16354:	910023e2 	add	x2, sp, #0x8
   16358:	2a1f03e0 	mov	w0, wzr
   1635c:	aa1f03e3 	mov	x3, xzr
   16360:	97fff993 	bl	149ac <core::panicking::assert_failed>
   16364:	d503201f 	nop
   16368:	d503201f 	nop
   1636c:	d503201f 	nop
   16370:	d503201f 	nop
   16374:	d503201f 	nop
   16378:	d503201f 	nop
   1637c:	d503201f 	nop


0000000000016380 <topic081_rust_runtime::dyn_item>:
   16380:	a9bc7bfd 	stp	x29, x30, [sp, #-64]!
   16384:	f9000bf7 	str	x23, [sp, #16]
   16388:	a90257f6 	stp	x22, x21, [sp, #32]
   1638c:	a9034ff4 	stp	x20, x19, [sp, #48]
   16390:	910003fd 	mov	x29, sp
   16394:	b4000243 	cbz	x3, 163dc <topic081_rust_runtime::dyn_item+0x5c>
   16398:	f9400c37 	ldr	x23, [x1, #24]
   1639c:	aa0303f3 	mov	x19, x3
   163a0:	aa0203f4 	mov	x20, x2
   163a4:	aa0003f6 	mov	x22, x0
   163a8:	aa1f03f5 	mov	x21, xzr
   163ac:	f8408681 	ldr	x1, [x20], #8
   163b0:	aa1603e0 	mov	x0, x22
   163b4:	d63f02e0 	blr	x23
   163b8:	8b150015 	add	x21, x0, x21
   163bc:	f1000673 	subs	x19, x19, #0x1
   163c0:	54ffff61 	b.ne	163ac <topic081_rust_runtime::dyn_item+0x2c>  // b.any
   163c4:	aa1503e0 	mov	x0, x21
   163c8:	a9434ff4 	ldp	x20, x19, [sp, #48]
   163cc:	a94257f6 	ldp	x22, x21, [sp, #32]
   163d0:	f9400bf7 	ldr	x23, [sp, #16]
   163d4:	a8c47bfd 	ldp	x29, x30, [sp], #64
   163d8:	d65f03c0 	ret
   163dc:	aa1f03f5 	mov	x21, xzr
   163e0:	aa1503e0 	mov	x0, x21
   163e4:	a9434ff4 	ldp	x20, x19, [sp, #48]
   163e8:	a94257f6 	ldp	x22, x21, [sp, #32]
   163ec:	f9400bf7 	ldr	x23, [sp, #16]
   163f0:	a8c47bfd 	ldp	x29, x30, [sp], #64
   163f4:	d65f03c0 	ret
   163f8:	d503201f 	nop
   163fc:	d503201f 	nop


0000000000016400 <topic081_rust_runtime::dot_index>:
   16400:	d10083ff 	sub	sp, sp, #0x20
   16404:	a9017bfd 	stp	x29, x30, [sp, #16]
   16408:	910043fd 	add	x29, sp, #0x10
   1640c:	eb03003f 	cmp	x1, x3
   16410:	a9000fe1 	stp	x1, x3, [sp]
   16414:	540006a1 	b.ne	164e8 <topic081_rust_runtime::dot_index+0xe8>  // b.any
   16418:	b40000e1 	cbz	x1, 16434 <topic081_rust_runtime::dot_index+0x34>
   1641c:	04a0e3e8 	cntw	x8
   16420:	eb08003f 	cmp	x1, x8
   16424:	54000122 	b.cs	16448 <topic081_rust_runtime::dot_index+0x48>  // b.hs, b.nlast
   16428:	aa1f03e8 	mov	x8, xzr
   1642c:	aa1f03e9 	mov	x9, xzr
   16430:	14000022 	b	164b8 <topic081_rust_runtime::dot_index+0xb8>
   16434:	aa1f03e8 	mov	x8, xzr
   16438:	aa0803e0 	mov	x0, x8
   1643c:	a9417bfd 	ldp	x29, x30, [sp, #16]
   16440:	910083ff 	add	sp, sp, #0x20
   16444:	d65f03c0 	ret
   16448:	d1000509 	sub	x9, x8, #0x1
   1644c:	6f00e400 	movi	v0.2d, #0x0
   16450:	25d8e3e0 	ptrue	p0.d
   16454:	6f00e401 	movi	v1.2d, #0x0
   16458:	aa0003ec 	mov	x12, x0
   1645c:	aa0203ed 	mov	x13, x2
   16460:	8a09002a 	and	x10, x1, x9
   16464:	04bf504b 	rdvl	x11, #2
   16468:	cb0a0029 	sub	x9, x1, x10
   1646c:	aa0903ee 	mov	x14, x9
   16470:	d503201f 	nop
   16474:	d503201f 	nop
   16478:	d503201f 	nop
   1647c:	d503201f 	nop
   16480:	85804182 	ldr	z2, [x12]
   16484:	85804583 	ldr	z3, [x12, #1, mul vl]
   16488:	eb0801ce 	subs	x14, x14, x8
   1648c:	8b0b018c 	add	x12, x12, x11
   16490:	858041a4 	ldr	z4, [x13]
   16494:	04c24080 	mla	z0.d, p0/m, z4.d, z2.d
   16498:	858045a5 	ldr	z5, [x13, #1, mul vl]
   1649c:	04c340a1 	mla	z1.d, p0/m, z5.d, z3.d
   164a0:	8b0b01ad 	add	x13, x13, x11
   164a4:	54fffee1 	b.ne	16480 <topic081_rust_runtime::dot_index+0x80>  // b.any
   164a8:	04e00020 	add	z0.d, z1.d, z0.d
   164ac:	04c12000 	uaddv	d0, p0, z0.d
   164b0:	9e660008 	fmov	x8, d0
   164b4:	b400012a 	cbz	x10, 164d8 <topic081_rust_runtime::dot_index+0xd8>
   164b8:	8b090c0a 	add	x10, x0, x9, lsl #3
   164bc:	cb09002b 	sub	x11, x1, x9
   164c0:	8b090c49 	add	x9, x2, x9, lsl #3
   164c4:	f840854c 	ldr	x12, [x10], #8
   164c8:	f840852d 	ldr	x13, [x9], #8
   164cc:	f100056b 	subs	x11, x11, #0x1
   164d0:	9b0c21a8 	madd	x8, x13, x12, x8
   164d4:	54ffff81 	b.ne	164c4 <topic081_rust_runtime::dot_index+0xc4>  // b.any
   164d8:	aa0803e0 	mov	x0, x8
   164dc:	a9417bfd 	ldp	x29, x30, [sp, #16]
   164e0:	910083ff 	add	sp, sp, #0x20
   164e4:	d65f03c0 	ret
   164e8:	f00002a5 	adrp	x5, 6d000 <GCC_except_table0+0xd10c>
   164ec:	913280a5 	add	x5, x5, #0xca0
   164f0:	910003e1 	mov	x1, sp
   164f4:	910023e2 	add	x2, sp, #0x8
   164f8:	2a1f03e0 	mov	w0, wzr
   164fc:	aa1f03e3 	mov	x3, xzr
   16500:	97fff92b 	bl	149ac <core::panicking::assert_failed>
   16504:	d503201f 	nop
   16508:	d503201f 	nop
   1650c:	d503201f 	nop


0000000000016510 <topic081_rust_runtime::dyn_batch>:
   16510:	f9401024 	ldr	x4, [x1, #32]
   16514:	aa0203e1 	mov	x1, x2
   16518:	aa0303e2 	mov	x2, x3
   1651c:	d61f0080 	br	x4

