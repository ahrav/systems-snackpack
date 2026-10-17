0000000000015060 <probe::kernels::generic::<probe::kernels::Format<16>>>:
   15060:	48 85 f6             	test   %rsi,%rsi
   15063:	74 1d                	je     15082 <probe::kernels::generic::<probe::kernels::Format<16>>+0x22>
   15065:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1506c:	01 00 00 
   1506f:	89 f2                	mov    %esi,%edx
   15071:	83 e2 03             	and    $0x3,%edx
   15074:	48 83 fe 04          	cmp    $0x4,%rsi
   15078:	73 0e                	jae    15088 <probe::kernels::generic::<probe::kernels::Format<16>>+0x28>
   1507a:	41 b8 10 00 00 00    	mov    $0x10,%r8d
   15080:	eb 65                	jmp    150e7 <probe::kernels::generic::<probe::kernels::Format<16>>+0x87>
   15082:	b8 10 00 00 00       	mov    $0x10,%eax
   15087:	c3                   	ret
   15088:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1508f:	ff ff 7f 
   15092:	48 21 c6             	and    %rax,%rsi
   15095:	41 b8 10 00 00 00    	mov    $0x10,%r8d
   1509b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   150a0:	0f b6 07             	movzbl (%rdi),%eax
   150a3:	4c 31 c0             	xor    %r8,%rax
   150a6:	48 0f af c1          	imul   %rcx,%rax
   150aa:	48 c1 c0 07          	rol    $0x7,%rax
   150ae:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   150b3:	49 31 c0             	xor    %rax,%r8
   150b6:	4c 0f af c1          	imul   %rcx,%r8
   150ba:	49 c1 c0 07          	rol    $0x7,%r8
   150be:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   150c2:	4c 31 c0             	xor    %r8,%rax
   150c5:	48 0f af c1          	imul   %rcx,%rax
   150c9:	48 c1 c0 07          	rol    $0x7,%rax
   150cd:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   150d2:	48 83 c7 04          	add    $0x4,%rdi
   150d6:	49 31 c0             	xor    %rax,%r8
   150d9:	4c 0f af c1          	imul   %rcx,%r8
   150dd:	49 c1 c0 07          	rol    $0x7,%r8
   150e1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   150e5:	75 b9                	jne    150a0 <probe::kernels::generic::<probe::kernels::Format<16>>+0x40>
   150e7:	4c 89 c0             	mov    %r8,%rax
   150ea:	48 85 d2             	test   %rdx,%rdx
   150ed:	74 2b                	je     1511a <probe::kernels::generic::<probe::kernels::Format<16>>+0xba>
   150ef:	31 f6                	xor    %esi,%esi
   150f1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   150f8:	0f 1f 84 00 00 00 00 
   150ff:	00 
   15100:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15104:	4c 31 c0             	xor    %r8,%rax
   15107:	48 0f af c1          	imul   %rcx,%rax
   1510b:	48 c1 c0 07          	rol    $0x7,%rax
   1510f:	48 ff c6             	inc    %rsi
   15112:	49 89 c0             	mov    %rax,%r8
   15115:	48 39 f2             	cmp    %rsi,%rdx
   15118:	75 e6                	jne    15100 <probe::kernels::generic::<probe::kernels::Format<16>>+0xa0>
   1511a:	c3                   	ret
   1511b:	cc                   	int3
   1511c:	cc                   	int3
   1511d:	cc                   	int3
   1511e:	cc                   	int3
   1511f:	cc                   	int3

0000000000015120 <probe::kernels::generic::<probe::kernels::Format<1>>>:
   15120:	48 85 f6             	test   %rsi,%rsi
   15123:	74 1d                	je     15142 <probe::kernels::generic::<probe::kernels::Format<1>>+0x22>
   15125:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1512c:	01 00 00 
   1512f:	89 f2                	mov    %esi,%edx
   15131:	83 e2 03             	and    $0x3,%edx
   15134:	48 83 fe 04          	cmp    $0x4,%rsi
   15138:	73 0e                	jae    15148 <probe::kernels::generic::<probe::kernels::Format<1>>+0x28>
   1513a:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   15140:	eb 65                	jmp    151a7 <probe::kernels::generic::<probe::kernels::Format<1>>+0x87>
   15142:	b8 01 00 00 00       	mov    $0x1,%eax
   15147:	c3                   	ret
   15148:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1514f:	ff ff 7f 
   15152:	48 21 c6             	and    %rax,%rsi
   15155:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   1515b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15160:	0f b6 07             	movzbl (%rdi),%eax
   15163:	4c 31 c0             	xor    %r8,%rax
   15166:	48 0f af c1          	imul   %rcx,%rax
   1516a:	48 c1 c0 07          	rol    $0x7,%rax
   1516e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15173:	49 31 c0             	xor    %rax,%r8
   15176:	4c 0f af c1          	imul   %rcx,%r8
   1517a:	49 c1 c0 07          	rol    $0x7,%r8
   1517e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15182:	4c 31 c0             	xor    %r8,%rax
   15185:	48 0f af c1          	imul   %rcx,%rax
   15189:	48 c1 c0 07          	rol    $0x7,%rax
   1518d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15192:	48 83 c7 04          	add    $0x4,%rdi
   15196:	49 31 c0             	xor    %rax,%r8
   15199:	4c 0f af c1          	imul   %rcx,%r8
   1519d:	49 c1 c0 07          	rol    $0x7,%r8
   151a1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   151a5:	75 b9                	jne    15160 <probe::kernels::generic::<probe::kernels::Format<1>>+0x40>
   151a7:	4c 89 c0             	mov    %r8,%rax
   151aa:	48 85 d2             	test   %rdx,%rdx
   151ad:	74 2b                	je     151da <probe::kernels::generic::<probe::kernels::Format<1>>+0xba>
   151af:	31 f6                	xor    %esi,%esi
   151b1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   151b8:	0f 1f 84 00 00 00 00 
   151bf:	00 
   151c0:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   151c4:	4c 31 c0             	xor    %r8,%rax
   151c7:	48 0f af c1          	imul   %rcx,%rax
   151cb:	48 c1 c0 07          	rol    $0x7,%rax
   151cf:	48 ff c6             	inc    %rsi
   151d2:	49 89 c0             	mov    %rax,%r8
   151d5:	48 39 f2             	cmp    %rsi,%rdx
   151d8:	75 e6                	jne    151c0 <probe::kernels::generic::<probe::kernels::Format<1>>+0xa0>
   151da:	c3                   	ret
   151db:	cc                   	int3
   151dc:	cc                   	int3
   151dd:	cc                   	int3
   151de:	cc                   	int3
   151df:	cc                   	int3

00000000000151e0 <probe::kernels::generic::<probe::kernels::Format<2>>>:
   151e0:	48 85 f6             	test   %rsi,%rsi
   151e3:	74 1d                	je     15202 <probe::kernels::generic::<probe::kernels::Format<2>>+0x22>
   151e5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   151ec:	01 00 00 
   151ef:	89 f2                	mov    %esi,%edx
   151f1:	83 e2 03             	and    $0x3,%edx
   151f4:	48 83 fe 04          	cmp    $0x4,%rsi
   151f8:	73 0e                	jae    15208 <probe::kernels::generic::<probe::kernels::Format<2>>+0x28>
   151fa:	41 b8 02 00 00 00    	mov    $0x2,%r8d
   15200:	eb 65                	jmp    15267 <probe::kernels::generic::<probe::kernels::Format<2>>+0x87>
   15202:	b8 02 00 00 00       	mov    $0x2,%eax
   15207:	c3                   	ret
   15208:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1520f:	ff ff 7f 
   15212:	48 21 c6             	and    %rax,%rsi
   15215:	41 b8 02 00 00 00    	mov    $0x2,%r8d
   1521b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15220:	0f b6 07             	movzbl (%rdi),%eax
   15223:	4c 31 c0             	xor    %r8,%rax
   15226:	48 0f af c1          	imul   %rcx,%rax
   1522a:	48 c1 c0 07          	rol    $0x7,%rax
   1522e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15233:	49 31 c0             	xor    %rax,%r8
   15236:	4c 0f af c1          	imul   %rcx,%r8
   1523a:	49 c1 c0 07          	rol    $0x7,%r8
   1523e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15242:	4c 31 c0             	xor    %r8,%rax
   15245:	48 0f af c1          	imul   %rcx,%rax
   15249:	48 c1 c0 07          	rol    $0x7,%rax
   1524d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15252:	48 83 c7 04          	add    $0x4,%rdi
   15256:	49 31 c0             	xor    %rax,%r8
   15259:	4c 0f af c1          	imul   %rcx,%r8
   1525d:	49 c1 c0 07          	rol    $0x7,%r8
   15261:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15265:	75 b9                	jne    15220 <probe::kernels::generic::<probe::kernels::Format<2>>+0x40>
   15267:	4c 89 c0             	mov    %r8,%rax
   1526a:	48 85 d2             	test   %rdx,%rdx
   1526d:	74 2b                	je     1529a <probe::kernels::generic::<probe::kernels::Format<2>>+0xba>
   1526f:	31 f6                	xor    %esi,%esi
   15271:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15278:	0f 1f 84 00 00 00 00 
   1527f:	00 
   15280:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15284:	4c 31 c0             	xor    %r8,%rax
   15287:	48 0f af c1          	imul   %rcx,%rax
   1528b:	48 c1 c0 07          	rol    $0x7,%rax
   1528f:	48 ff c6             	inc    %rsi
   15292:	49 89 c0             	mov    %rax,%r8
   15295:	48 39 f2             	cmp    %rsi,%rdx
   15298:	75 e6                	jne    15280 <probe::kernels::generic::<probe::kernels::Format<2>>+0xa0>
   1529a:	c3                   	ret
   1529b:	cc                   	int3
   1529c:	cc                   	int3
   1529d:	cc                   	int3
   1529e:	cc                   	int3
   1529f:	cc                   	int3

00000000000152a0 <probe::kernels::generic::<probe::kernels::Format<3>>>:
   152a0:	48 85 f6             	test   %rsi,%rsi
   152a3:	74 1d                	je     152c2 <probe::kernels::generic::<probe::kernels::Format<3>>+0x22>
   152a5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   152ac:	01 00 00 
   152af:	89 f2                	mov    %esi,%edx
   152b1:	83 e2 03             	and    $0x3,%edx
   152b4:	48 83 fe 04          	cmp    $0x4,%rsi
   152b8:	73 0e                	jae    152c8 <probe::kernels::generic::<probe::kernels::Format<3>>+0x28>
   152ba:	41 b8 03 00 00 00    	mov    $0x3,%r8d
   152c0:	eb 65                	jmp    15327 <probe::kernels::generic::<probe::kernels::Format<3>>+0x87>
   152c2:	b8 03 00 00 00       	mov    $0x3,%eax
   152c7:	c3                   	ret
   152c8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   152cf:	ff ff 7f 
   152d2:	48 21 c6             	and    %rax,%rsi
   152d5:	41 b8 03 00 00 00    	mov    $0x3,%r8d
   152db:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   152e0:	0f b6 07             	movzbl (%rdi),%eax
   152e3:	4c 31 c0             	xor    %r8,%rax
   152e6:	48 0f af c1          	imul   %rcx,%rax
   152ea:	48 c1 c0 07          	rol    $0x7,%rax
   152ee:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   152f3:	49 31 c0             	xor    %rax,%r8
   152f6:	4c 0f af c1          	imul   %rcx,%r8
   152fa:	49 c1 c0 07          	rol    $0x7,%r8
   152fe:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15302:	4c 31 c0             	xor    %r8,%rax
   15305:	48 0f af c1          	imul   %rcx,%rax
   15309:	48 c1 c0 07          	rol    $0x7,%rax
   1530d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15312:	48 83 c7 04          	add    $0x4,%rdi
   15316:	49 31 c0             	xor    %rax,%r8
   15319:	4c 0f af c1          	imul   %rcx,%r8
   1531d:	49 c1 c0 07          	rol    $0x7,%r8
   15321:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15325:	75 b9                	jne    152e0 <probe::kernels::generic::<probe::kernels::Format<3>>+0x40>
   15327:	4c 89 c0             	mov    %r8,%rax
   1532a:	48 85 d2             	test   %rdx,%rdx
   1532d:	74 2b                	je     1535a <probe::kernels::generic::<probe::kernels::Format<3>>+0xba>
   1532f:	31 f6                	xor    %esi,%esi
   15331:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15338:	0f 1f 84 00 00 00 00 
   1533f:	00 
   15340:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15344:	4c 31 c0             	xor    %r8,%rax
   15347:	48 0f af c1          	imul   %rcx,%rax
   1534b:	48 c1 c0 07          	rol    $0x7,%rax
   1534f:	48 ff c6             	inc    %rsi
   15352:	49 89 c0             	mov    %rax,%r8
   15355:	48 39 f2             	cmp    %rsi,%rdx
   15358:	75 e6                	jne    15340 <probe::kernels::generic::<probe::kernels::Format<3>>+0xa0>
   1535a:	c3                   	ret
   1535b:	cc                   	int3
   1535c:	cc                   	int3
   1535d:	cc                   	int3
   1535e:	cc                   	int3
   1535f:	cc                   	int3

0000000000015360 <probe::kernels::generic::<probe::kernels::Format<4>>>:
   15360:	48 85 f6             	test   %rsi,%rsi
   15363:	74 1d                	je     15382 <probe::kernels::generic::<probe::kernels::Format<4>>+0x22>
   15365:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1536c:	01 00 00 
   1536f:	89 f2                	mov    %esi,%edx
   15371:	83 e2 03             	and    $0x3,%edx
   15374:	48 83 fe 04          	cmp    $0x4,%rsi
   15378:	73 0e                	jae    15388 <probe::kernels::generic::<probe::kernels::Format<4>>+0x28>
   1537a:	41 b8 04 00 00 00    	mov    $0x4,%r8d
   15380:	eb 65                	jmp    153e7 <probe::kernels::generic::<probe::kernels::Format<4>>+0x87>
   15382:	b8 04 00 00 00       	mov    $0x4,%eax
   15387:	c3                   	ret
   15388:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1538f:	ff ff 7f 
   15392:	48 21 c6             	and    %rax,%rsi
   15395:	41 b8 04 00 00 00    	mov    $0x4,%r8d
   1539b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   153a0:	0f b6 07             	movzbl (%rdi),%eax
   153a3:	4c 31 c0             	xor    %r8,%rax
   153a6:	48 0f af c1          	imul   %rcx,%rax
   153aa:	48 c1 c0 07          	rol    $0x7,%rax
   153ae:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   153b3:	49 31 c0             	xor    %rax,%r8
   153b6:	4c 0f af c1          	imul   %rcx,%r8
   153ba:	49 c1 c0 07          	rol    $0x7,%r8
   153be:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   153c2:	4c 31 c0             	xor    %r8,%rax
   153c5:	48 0f af c1          	imul   %rcx,%rax
   153c9:	48 c1 c0 07          	rol    $0x7,%rax
   153cd:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   153d2:	48 83 c7 04          	add    $0x4,%rdi
   153d6:	49 31 c0             	xor    %rax,%r8
   153d9:	4c 0f af c1          	imul   %rcx,%r8
   153dd:	49 c1 c0 07          	rol    $0x7,%r8
   153e1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   153e5:	75 b9                	jne    153a0 <probe::kernels::generic::<probe::kernels::Format<4>>+0x40>
   153e7:	4c 89 c0             	mov    %r8,%rax
   153ea:	48 85 d2             	test   %rdx,%rdx
   153ed:	74 2b                	je     1541a <probe::kernels::generic::<probe::kernels::Format<4>>+0xba>
   153ef:	31 f6                	xor    %esi,%esi
   153f1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   153f8:	0f 1f 84 00 00 00 00 
   153ff:	00 
   15400:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15404:	4c 31 c0             	xor    %r8,%rax
   15407:	48 0f af c1          	imul   %rcx,%rax
   1540b:	48 c1 c0 07          	rol    $0x7,%rax
   1540f:	48 ff c6             	inc    %rsi
   15412:	49 89 c0             	mov    %rax,%r8
   15415:	48 39 f2             	cmp    %rsi,%rdx
   15418:	75 e6                	jne    15400 <probe::kernels::generic::<probe::kernels::Format<4>>+0xa0>
   1541a:	c3                   	ret
   1541b:	cc                   	int3
   1541c:	cc                   	int3
   1541d:	cc                   	int3
   1541e:	cc                   	int3
   1541f:	cc                   	int3

0000000000015420 <probe::kernels::generic::<probe::kernels::Format<5>>>:
   15420:	48 85 f6             	test   %rsi,%rsi
   15423:	74 1d                	je     15442 <probe::kernels::generic::<probe::kernels::Format<5>>+0x22>
   15425:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1542c:	01 00 00 
   1542f:	89 f2                	mov    %esi,%edx
   15431:	83 e2 03             	and    $0x3,%edx
   15434:	48 83 fe 04          	cmp    $0x4,%rsi
   15438:	73 0e                	jae    15448 <probe::kernels::generic::<probe::kernels::Format<5>>+0x28>
   1543a:	41 b8 05 00 00 00    	mov    $0x5,%r8d
   15440:	eb 65                	jmp    154a7 <probe::kernels::generic::<probe::kernels::Format<5>>+0x87>
   15442:	b8 05 00 00 00       	mov    $0x5,%eax
   15447:	c3                   	ret
   15448:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1544f:	ff ff 7f 
   15452:	48 21 c6             	and    %rax,%rsi
   15455:	41 b8 05 00 00 00    	mov    $0x5,%r8d
   1545b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15460:	0f b6 07             	movzbl (%rdi),%eax
   15463:	4c 31 c0             	xor    %r8,%rax
   15466:	48 0f af c1          	imul   %rcx,%rax
   1546a:	48 c1 c0 07          	rol    $0x7,%rax
   1546e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15473:	49 31 c0             	xor    %rax,%r8
   15476:	4c 0f af c1          	imul   %rcx,%r8
   1547a:	49 c1 c0 07          	rol    $0x7,%r8
   1547e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15482:	4c 31 c0             	xor    %r8,%rax
   15485:	48 0f af c1          	imul   %rcx,%rax
   15489:	48 c1 c0 07          	rol    $0x7,%rax
   1548d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15492:	48 83 c7 04          	add    $0x4,%rdi
   15496:	49 31 c0             	xor    %rax,%r8
   15499:	4c 0f af c1          	imul   %rcx,%r8
   1549d:	49 c1 c0 07          	rol    $0x7,%r8
   154a1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   154a5:	75 b9                	jne    15460 <probe::kernels::generic::<probe::kernels::Format<5>>+0x40>
   154a7:	4c 89 c0             	mov    %r8,%rax
   154aa:	48 85 d2             	test   %rdx,%rdx
   154ad:	74 2b                	je     154da <probe::kernels::generic::<probe::kernels::Format<5>>+0xba>
   154af:	31 f6                	xor    %esi,%esi
   154b1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   154b8:	0f 1f 84 00 00 00 00 
   154bf:	00 
   154c0:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   154c4:	4c 31 c0             	xor    %r8,%rax
   154c7:	48 0f af c1          	imul   %rcx,%rax
   154cb:	48 c1 c0 07          	rol    $0x7,%rax
   154cf:	48 ff c6             	inc    %rsi
   154d2:	49 89 c0             	mov    %rax,%r8
   154d5:	48 39 f2             	cmp    %rsi,%rdx
   154d8:	75 e6                	jne    154c0 <probe::kernels::generic::<probe::kernels::Format<5>>+0xa0>
   154da:	c3                   	ret
   154db:	cc                   	int3
   154dc:	cc                   	int3
   154dd:	cc                   	int3
   154de:	cc                   	int3
   154df:	cc                   	int3

00000000000154e0 <probe::kernels::generic::<probe::kernels::Format<6>>>:
   154e0:	48 85 f6             	test   %rsi,%rsi
   154e3:	74 1d                	je     15502 <probe::kernels::generic::<probe::kernels::Format<6>>+0x22>
   154e5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   154ec:	01 00 00 
   154ef:	89 f2                	mov    %esi,%edx
   154f1:	83 e2 03             	and    $0x3,%edx
   154f4:	48 83 fe 04          	cmp    $0x4,%rsi
   154f8:	73 0e                	jae    15508 <probe::kernels::generic::<probe::kernels::Format<6>>+0x28>
   154fa:	41 b8 06 00 00 00    	mov    $0x6,%r8d
   15500:	eb 65                	jmp    15567 <probe::kernels::generic::<probe::kernels::Format<6>>+0x87>
   15502:	b8 06 00 00 00       	mov    $0x6,%eax
   15507:	c3                   	ret
   15508:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1550f:	ff ff 7f 
   15512:	48 21 c6             	and    %rax,%rsi
   15515:	41 b8 06 00 00 00    	mov    $0x6,%r8d
   1551b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15520:	0f b6 07             	movzbl (%rdi),%eax
   15523:	4c 31 c0             	xor    %r8,%rax
   15526:	48 0f af c1          	imul   %rcx,%rax
   1552a:	48 c1 c0 07          	rol    $0x7,%rax
   1552e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15533:	49 31 c0             	xor    %rax,%r8
   15536:	4c 0f af c1          	imul   %rcx,%r8
   1553a:	49 c1 c0 07          	rol    $0x7,%r8
   1553e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15542:	4c 31 c0             	xor    %r8,%rax
   15545:	48 0f af c1          	imul   %rcx,%rax
   15549:	48 c1 c0 07          	rol    $0x7,%rax
   1554d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15552:	48 83 c7 04          	add    $0x4,%rdi
   15556:	49 31 c0             	xor    %rax,%r8
   15559:	4c 0f af c1          	imul   %rcx,%r8
   1555d:	49 c1 c0 07          	rol    $0x7,%r8
   15561:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15565:	75 b9                	jne    15520 <probe::kernels::generic::<probe::kernels::Format<6>>+0x40>
   15567:	4c 89 c0             	mov    %r8,%rax
   1556a:	48 85 d2             	test   %rdx,%rdx
   1556d:	74 2b                	je     1559a <probe::kernels::generic::<probe::kernels::Format<6>>+0xba>
   1556f:	31 f6                	xor    %esi,%esi
   15571:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15578:	0f 1f 84 00 00 00 00 
   1557f:	00 
   15580:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15584:	4c 31 c0             	xor    %r8,%rax
   15587:	48 0f af c1          	imul   %rcx,%rax
   1558b:	48 c1 c0 07          	rol    $0x7,%rax
   1558f:	48 ff c6             	inc    %rsi
   15592:	49 89 c0             	mov    %rax,%r8
   15595:	48 39 f2             	cmp    %rsi,%rdx
   15598:	75 e6                	jne    15580 <probe::kernels::generic::<probe::kernels::Format<6>>+0xa0>
   1559a:	c3                   	ret
   1559b:	cc                   	int3
   1559c:	cc                   	int3
   1559d:	cc                   	int3
   1559e:	cc                   	int3
   1559f:	cc                   	int3

00000000000155a0 <probe::kernels::generic::<probe::kernels::Format<7>>>:
   155a0:	48 85 f6             	test   %rsi,%rsi
   155a3:	74 1d                	je     155c2 <probe::kernels::generic::<probe::kernels::Format<7>>+0x22>
   155a5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   155ac:	01 00 00 
   155af:	89 f2                	mov    %esi,%edx
   155b1:	83 e2 03             	and    $0x3,%edx
   155b4:	48 83 fe 04          	cmp    $0x4,%rsi
   155b8:	73 0e                	jae    155c8 <probe::kernels::generic::<probe::kernels::Format<7>>+0x28>
   155ba:	41 b8 07 00 00 00    	mov    $0x7,%r8d
   155c0:	eb 65                	jmp    15627 <probe::kernels::generic::<probe::kernels::Format<7>>+0x87>
   155c2:	b8 07 00 00 00       	mov    $0x7,%eax
   155c7:	c3                   	ret
   155c8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   155cf:	ff ff 7f 
   155d2:	48 21 c6             	and    %rax,%rsi
   155d5:	41 b8 07 00 00 00    	mov    $0x7,%r8d
   155db:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   155e0:	0f b6 07             	movzbl (%rdi),%eax
   155e3:	4c 31 c0             	xor    %r8,%rax
   155e6:	48 0f af c1          	imul   %rcx,%rax
   155ea:	48 c1 c0 07          	rol    $0x7,%rax
   155ee:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   155f3:	49 31 c0             	xor    %rax,%r8
   155f6:	4c 0f af c1          	imul   %rcx,%r8
   155fa:	49 c1 c0 07          	rol    $0x7,%r8
   155fe:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15602:	4c 31 c0             	xor    %r8,%rax
   15605:	48 0f af c1          	imul   %rcx,%rax
   15609:	48 c1 c0 07          	rol    $0x7,%rax
   1560d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15612:	48 83 c7 04          	add    $0x4,%rdi
   15616:	49 31 c0             	xor    %rax,%r8
   15619:	4c 0f af c1          	imul   %rcx,%r8
   1561d:	49 c1 c0 07          	rol    $0x7,%r8
   15621:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15625:	75 b9                	jne    155e0 <probe::kernels::generic::<probe::kernels::Format<7>>+0x40>
   15627:	4c 89 c0             	mov    %r8,%rax
   1562a:	48 85 d2             	test   %rdx,%rdx
   1562d:	74 2b                	je     1565a <probe::kernels::generic::<probe::kernels::Format<7>>+0xba>
   1562f:	31 f6                	xor    %esi,%esi
   15631:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15638:	0f 1f 84 00 00 00 00 
   1563f:	00 
   15640:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15644:	4c 31 c0             	xor    %r8,%rax
   15647:	48 0f af c1          	imul   %rcx,%rax
   1564b:	48 c1 c0 07          	rol    $0x7,%rax
   1564f:	48 ff c6             	inc    %rsi
   15652:	49 89 c0             	mov    %rax,%r8
   15655:	48 39 f2             	cmp    %rsi,%rdx
   15658:	75 e6                	jne    15640 <probe::kernels::generic::<probe::kernels::Format<7>>+0xa0>
   1565a:	c3                   	ret
   1565b:	cc                   	int3
   1565c:	cc                   	int3
   1565d:	cc                   	int3
   1565e:	cc                   	int3
   1565f:	cc                   	int3

0000000000015660 <probe::kernels::generic::<probe::kernels::Format<8>>>:
   15660:	48 85 f6             	test   %rsi,%rsi
   15663:	74 1d                	je     15682 <probe::kernels::generic::<probe::kernels::Format<8>>+0x22>
   15665:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1566c:	01 00 00 
   1566f:	89 f2                	mov    %esi,%edx
   15671:	83 e2 03             	and    $0x3,%edx
   15674:	48 83 fe 04          	cmp    $0x4,%rsi
   15678:	73 0e                	jae    15688 <probe::kernels::generic::<probe::kernels::Format<8>>+0x28>
   1567a:	41 b8 08 00 00 00    	mov    $0x8,%r8d
   15680:	eb 65                	jmp    156e7 <probe::kernels::generic::<probe::kernels::Format<8>>+0x87>
   15682:	b8 08 00 00 00       	mov    $0x8,%eax
   15687:	c3                   	ret
   15688:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1568f:	ff ff 7f 
   15692:	48 21 c6             	and    %rax,%rsi
   15695:	41 b8 08 00 00 00    	mov    $0x8,%r8d
   1569b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   156a0:	0f b6 07             	movzbl (%rdi),%eax
   156a3:	4c 31 c0             	xor    %r8,%rax
   156a6:	48 0f af c1          	imul   %rcx,%rax
   156aa:	48 c1 c0 07          	rol    $0x7,%rax
   156ae:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   156b3:	49 31 c0             	xor    %rax,%r8
   156b6:	4c 0f af c1          	imul   %rcx,%r8
   156ba:	49 c1 c0 07          	rol    $0x7,%r8
   156be:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   156c2:	4c 31 c0             	xor    %r8,%rax
   156c5:	48 0f af c1          	imul   %rcx,%rax
   156c9:	48 c1 c0 07          	rol    $0x7,%rax
   156cd:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   156d2:	48 83 c7 04          	add    $0x4,%rdi
   156d6:	49 31 c0             	xor    %rax,%r8
   156d9:	4c 0f af c1          	imul   %rcx,%r8
   156dd:	49 c1 c0 07          	rol    $0x7,%r8
   156e1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   156e5:	75 b9                	jne    156a0 <probe::kernels::generic::<probe::kernels::Format<8>>+0x40>
   156e7:	4c 89 c0             	mov    %r8,%rax
   156ea:	48 85 d2             	test   %rdx,%rdx
   156ed:	74 2b                	je     1571a <probe::kernels::generic::<probe::kernels::Format<8>>+0xba>
   156ef:	31 f6                	xor    %esi,%esi
   156f1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   156f8:	0f 1f 84 00 00 00 00 
   156ff:	00 
   15700:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15704:	4c 31 c0             	xor    %r8,%rax
   15707:	48 0f af c1          	imul   %rcx,%rax
   1570b:	48 c1 c0 07          	rol    $0x7,%rax
   1570f:	48 ff c6             	inc    %rsi
   15712:	49 89 c0             	mov    %rax,%r8
   15715:	48 39 f2             	cmp    %rsi,%rdx
   15718:	75 e6                	jne    15700 <probe::kernels::generic::<probe::kernels::Format<8>>+0xa0>
   1571a:	c3                   	ret
   1571b:	cc                   	int3
   1571c:	cc                   	int3
   1571d:	cc                   	int3
   1571e:	cc                   	int3
   1571f:	cc                   	int3

0000000000015720 <probe::kernels::generic::<probe::kernels::Format<9>>>:
   15720:	48 85 f6             	test   %rsi,%rsi
   15723:	74 1d                	je     15742 <probe::kernels::generic::<probe::kernels::Format<9>>+0x22>
   15725:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1572c:	01 00 00 
   1572f:	89 f2                	mov    %esi,%edx
   15731:	83 e2 03             	and    $0x3,%edx
   15734:	48 83 fe 04          	cmp    $0x4,%rsi
   15738:	73 0e                	jae    15748 <probe::kernels::generic::<probe::kernels::Format<9>>+0x28>
   1573a:	41 b8 09 00 00 00    	mov    $0x9,%r8d
   15740:	eb 65                	jmp    157a7 <probe::kernels::generic::<probe::kernels::Format<9>>+0x87>
   15742:	b8 09 00 00 00       	mov    $0x9,%eax
   15747:	c3                   	ret
   15748:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1574f:	ff ff 7f 
   15752:	48 21 c6             	and    %rax,%rsi
   15755:	41 b8 09 00 00 00    	mov    $0x9,%r8d
   1575b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15760:	0f b6 07             	movzbl (%rdi),%eax
   15763:	4c 31 c0             	xor    %r8,%rax
   15766:	48 0f af c1          	imul   %rcx,%rax
   1576a:	48 c1 c0 07          	rol    $0x7,%rax
   1576e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15773:	49 31 c0             	xor    %rax,%r8
   15776:	4c 0f af c1          	imul   %rcx,%r8
   1577a:	49 c1 c0 07          	rol    $0x7,%r8
   1577e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15782:	4c 31 c0             	xor    %r8,%rax
   15785:	48 0f af c1          	imul   %rcx,%rax
   15789:	48 c1 c0 07          	rol    $0x7,%rax
   1578d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15792:	48 83 c7 04          	add    $0x4,%rdi
   15796:	49 31 c0             	xor    %rax,%r8
   15799:	4c 0f af c1          	imul   %rcx,%r8
   1579d:	49 c1 c0 07          	rol    $0x7,%r8
   157a1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   157a5:	75 b9                	jne    15760 <probe::kernels::generic::<probe::kernels::Format<9>>+0x40>
   157a7:	4c 89 c0             	mov    %r8,%rax
   157aa:	48 85 d2             	test   %rdx,%rdx
   157ad:	74 2b                	je     157da <probe::kernels::generic::<probe::kernels::Format<9>>+0xba>
   157af:	31 f6                	xor    %esi,%esi
   157b1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   157b8:	0f 1f 84 00 00 00 00 
   157bf:	00 
   157c0:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   157c4:	4c 31 c0             	xor    %r8,%rax
   157c7:	48 0f af c1          	imul   %rcx,%rax
   157cb:	48 c1 c0 07          	rol    $0x7,%rax
   157cf:	48 ff c6             	inc    %rsi
   157d2:	49 89 c0             	mov    %rax,%r8
   157d5:	48 39 f2             	cmp    %rsi,%rdx
   157d8:	75 e6                	jne    157c0 <probe::kernels::generic::<probe::kernels::Format<9>>+0xa0>
   157da:	c3                   	ret
   157db:	cc                   	int3
   157dc:	cc                   	int3
   157dd:	cc                   	int3
   157de:	cc                   	int3
   157df:	cc                   	int3

00000000000157e0 <probe::kernels::generic::<probe::kernels::Format<10>>>:
   157e0:	48 85 f6             	test   %rsi,%rsi
   157e3:	74 1d                	je     15802 <probe::kernels::generic::<probe::kernels::Format<10>>+0x22>
   157e5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   157ec:	01 00 00 
   157ef:	89 f2                	mov    %esi,%edx
   157f1:	83 e2 03             	and    $0x3,%edx
   157f4:	48 83 fe 04          	cmp    $0x4,%rsi
   157f8:	73 0e                	jae    15808 <probe::kernels::generic::<probe::kernels::Format<10>>+0x28>
   157fa:	41 b8 0a 00 00 00    	mov    $0xa,%r8d
   15800:	eb 65                	jmp    15867 <probe::kernels::generic::<probe::kernels::Format<10>>+0x87>
   15802:	b8 0a 00 00 00       	mov    $0xa,%eax
   15807:	c3                   	ret
   15808:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1580f:	ff ff 7f 
   15812:	48 21 c6             	and    %rax,%rsi
   15815:	41 b8 0a 00 00 00    	mov    $0xa,%r8d
   1581b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15820:	0f b6 07             	movzbl (%rdi),%eax
   15823:	4c 31 c0             	xor    %r8,%rax
   15826:	48 0f af c1          	imul   %rcx,%rax
   1582a:	48 c1 c0 07          	rol    $0x7,%rax
   1582e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15833:	49 31 c0             	xor    %rax,%r8
   15836:	4c 0f af c1          	imul   %rcx,%r8
   1583a:	49 c1 c0 07          	rol    $0x7,%r8
   1583e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15842:	4c 31 c0             	xor    %r8,%rax
   15845:	48 0f af c1          	imul   %rcx,%rax
   15849:	48 c1 c0 07          	rol    $0x7,%rax
   1584d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15852:	48 83 c7 04          	add    $0x4,%rdi
   15856:	49 31 c0             	xor    %rax,%r8
   15859:	4c 0f af c1          	imul   %rcx,%r8
   1585d:	49 c1 c0 07          	rol    $0x7,%r8
   15861:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15865:	75 b9                	jne    15820 <probe::kernels::generic::<probe::kernels::Format<10>>+0x40>
   15867:	4c 89 c0             	mov    %r8,%rax
   1586a:	48 85 d2             	test   %rdx,%rdx
   1586d:	74 2b                	je     1589a <probe::kernels::generic::<probe::kernels::Format<10>>+0xba>
   1586f:	31 f6                	xor    %esi,%esi
   15871:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15878:	0f 1f 84 00 00 00 00 
   1587f:	00 
   15880:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15884:	4c 31 c0             	xor    %r8,%rax
   15887:	48 0f af c1          	imul   %rcx,%rax
   1588b:	48 c1 c0 07          	rol    $0x7,%rax
   1588f:	48 ff c6             	inc    %rsi
   15892:	49 89 c0             	mov    %rax,%r8
   15895:	48 39 f2             	cmp    %rsi,%rdx
   15898:	75 e6                	jne    15880 <probe::kernels::generic::<probe::kernels::Format<10>>+0xa0>
   1589a:	c3                   	ret
   1589b:	cc                   	int3
   1589c:	cc                   	int3
   1589d:	cc                   	int3
   1589e:	cc                   	int3
   1589f:	cc                   	int3

00000000000158a0 <probe::kernels::generic::<probe::kernels::Format<11>>>:
   158a0:	48 85 f6             	test   %rsi,%rsi
   158a3:	74 1d                	je     158c2 <probe::kernels::generic::<probe::kernels::Format<11>>+0x22>
   158a5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   158ac:	01 00 00 
   158af:	89 f2                	mov    %esi,%edx
   158b1:	83 e2 03             	and    $0x3,%edx
   158b4:	48 83 fe 04          	cmp    $0x4,%rsi
   158b8:	73 0e                	jae    158c8 <probe::kernels::generic::<probe::kernels::Format<11>>+0x28>
   158ba:	41 b8 0b 00 00 00    	mov    $0xb,%r8d
   158c0:	eb 65                	jmp    15927 <probe::kernels::generic::<probe::kernels::Format<11>>+0x87>
   158c2:	b8 0b 00 00 00       	mov    $0xb,%eax
   158c7:	c3                   	ret
   158c8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   158cf:	ff ff 7f 
   158d2:	48 21 c6             	and    %rax,%rsi
   158d5:	41 b8 0b 00 00 00    	mov    $0xb,%r8d
   158db:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   158e0:	0f b6 07             	movzbl (%rdi),%eax
   158e3:	4c 31 c0             	xor    %r8,%rax
   158e6:	48 0f af c1          	imul   %rcx,%rax
   158ea:	48 c1 c0 07          	rol    $0x7,%rax
   158ee:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   158f3:	49 31 c0             	xor    %rax,%r8
   158f6:	4c 0f af c1          	imul   %rcx,%r8
   158fa:	49 c1 c0 07          	rol    $0x7,%r8
   158fe:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15902:	4c 31 c0             	xor    %r8,%rax
   15905:	48 0f af c1          	imul   %rcx,%rax
   15909:	48 c1 c0 07          	rol    $0x7,%rax
   1590d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15912:	48 83 c7 04          	add    $0x4,%rdi
   15916:	49 31 c0             	xor    %rax,%r8
   15919:	4c 0f af c1          	imul   %rcx,%r8
   1591d:	49 c1 c0 07          	rol    $0x7,%r8
   15921:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15925:	75 b9                	jne    158e0 <probe::kernels::generic::<probe::kernels::Format<11>>+0x40>
   15927:	4c 89 c0             	mov    %r8,%rax
   1592a:	48 85 d2             	test   %rdx,%rdx
   1592d:	74 2b                	je     1595a <probe::kernels::generic::<probe::kernels::Format<11>>+0xba>
   1592f:	31 f6                	xor    %esi,%esi
   15931:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15938:	0f 1f 84 00 00 00 00 
   1593f:	00 
   15940:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15944:	4c 31 c0             	xor    %r8,%rax
   15947:	48 0f af c1          	imul   %rcx,%rax
   1594b:	48 c1 c0 07          	rol    $0x7,%rax
   1594f:	48 ff c6             	inc    %rsi
   15952:	49 89 c0             	mov    %rax,%r8
   15955:	48 39 f2             	cmp    %rsi,%rdx
   15958:	75 e6                	jne    15940 <probe::kernels::generic::<probe::kernels::Format<11>>+0xa0>
   1595a:	c3                   	ret
   1595b:	cc                   	int3
   1595c:	cc                   	int3
   1595d:	cc                   	int3
   1595e:	cc                   	int3
   1595f:	cc                   	int3

0000000000015960 <probe::kernels::generic::<probe::kernels::Format<12>>>:
   15960:	48 85 f6             	test   %rsi,%rsi
   15963:	74 1d                	je     15982 <probe::kernels::generic::<probe::kernels::Format<12>>+0x22>
   15965:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   1596c:	01 00 00 
   1596f:	89 f2                	mov    %esi,%edx
   15971:	83 e2 03             	and    $0x3,%edx
   15974:	48 83 fe 04          	cmp    $0x4,%rsi
   15978:	73 0e                	jae    15988 <probe::kernels::generic::<probe::kernels::Format<12>>+0x28>
   1597a:	41 b8 0c 00 00 00    	mov    $0xc,%r8d
   15980:	eb 65                	jmp    159e7 <probe::kernels::generic::<probe::kernels::Format<12>>+0x87>
   15982:	b8 0c 00 00 00       	mov    $0xc,%eax
   15987:	c3                   	ret
   15988:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   1598f:	ff ff 7f 
   15992:	48 21 c6             	and    %rax,%rsi
   15995:	41 b8 0c 00 00 00    	mov    $0xc,%r8d
   1599b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   159a0:	0f b6 07             	movzbl (%rdi),%eax
   159a3:	4c 31 c0             	xor    %r8,%rax
   159a6:	48 0f af c1          	imul   %rcx,%rax
   159aa:	48 c1 c0 07          	rol    $0x7,%rax
   159ae:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   159b3:	49 31 c0             	xor    %rax,%r8
   159b6:	4c 0f af c1          	imul   %rcx,%r8
   159ba:	49 c1 c0 07          	rol    $0x7,%r8
   159be:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   159c2:	4c 31 c0             	xor    %r8,%rax
   159c5:	48 0f af c1          	imul   %rcx,%rax
   159c9:	48 c1 c0 07          	rol    $0x7,%rax
   159cd:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   159d2:	48 83 c7 04          	add    $0x4,%rdi
   159d6:	49 31 c0             	xor    %rax,%r8
   159d9:	4c 0f af c1          	imul   %rcx,%r8
   159dd:	49 c1 c0 07          	rol    $0x7,%r8
   159e1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   159e5:	75 b9                	jne    159a0 <probe::kernels::generic::<probe::kernels::Format<12>>+0x40>
   159e7:	4c 89 c0             	mov    %r8,%rax
   159ea:	48 85 d2             	test   %rdx,%rdx
   159ed:	74 2b                	je     15a1a <probe::kernels::generic::<probe::kernels::Format<12>>+0xba>
   159ef:	31 f6                	xor    %esi,%esi
   159f1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   159f8:	0f 1f 84 00 00 00 00 
   159ff:	00 
   15a00:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15a04:	4c 31 c0             	xor    %r8,%rax
   15a07:	48 0f af c1          	imul   %rcx,%rax
   15a0b:	48 c1 c0 07          	rol    $0x7,%rax
   15a0f:	48 ff c6             	inc    %rsi
   15a12:	49 89 c0             	mov    %rax,%r8
   15a15:	48 39 f2             	cmp    %rsi,%rdx
   15a18:	75 e6                	jne    15a00 <probe::kernels::generic::<probe::kernels::Format<12>>+0xa0>
   15a1a:	c3                   	ret
   15a1b:	cc                   	int3
   15a1c:	cc                   	int3
   15a1d:	cc                   	int3
   15a1e:	cc                   	int3
   15a1f:	cc                   	int3

0000000000015a20 <probe::kernels::generic::<probe::kernels::Format<13>>>:
   15a20:	48 85 f6             	test   %rsi,%rsi
   15a23:	74 1d                	je     15a42 <probe::kernels::generic::<probe::kernels::Format<13>>+0x22>
   15a25:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   15a2c:	01 00 00 
   15a2f:	89 f2                	mov    %esi,%edx
   15a31:	83 e2 03             	and    $0x3,%edx
   15a34:	48 83 fe 04          	cmp    $0x4,%rsi
   15a38:	73 0e                	jae    15a48 <probe::kernels::generic::<probe::kernels::Format<13>>+0x28>
   15a3a:	41 b8 0d 00 00 00    	mov    $0xd,%r8d
   15a40:	eb 65                	jmp    15aa7 <probe::kernels::generic::<probe::kernels::Format<13>>+0x87>
   15a42:	b8 0d 00 00 00       	mov    $0xd,%eax
   15a47:	c3                   	ret
   15a48:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   15a4f:	ff ff 7f 
   15a52:	48 21 c6             	and    %rax,%rsi
   15a55:	41 b8 0d 00 00 00    	mov    $0xd,%r8d
   15a5b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15a60:	0f b6 07             	movzbl (%rdi),%eax
   15a63:	4c 31 c0             	xor    %r8,%rax
   15a66:	48 0f af c1          	imul   %rcx,%rax
   15a6a:	48 c1 c0 07          	rol    $0x7,%rax
   15a6e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15a73:	49 31 c0             	xor    %rax,%r8
   15a76:	4c 0f af c1          	imul   %rcx,%r8
   15a7a:	49 c1 c0 07          	rol    $0x7,%r8
   15a7e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15a82:	4c 31 c0             	xor    %r8,%rax
   15a85:	48 0f af c1          	imul   %rcx,%rax
   15a89:	48 c1 c0 07          	rol    $0x7,%rax
   15a8d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15a92:	48 83 c7 04          	add    $0x4,%rdi
   15a96:	49 31 c0             	xor    %rax,%r8
   15a99:	4c 0f af c1          	imul   %rcx,%r8
   15a9d:	49 c1 c0 07          	rol    $0x7,%r8
   15aa1:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15aa5:	75 b9                	jne    15a60 <probe::kernels::generic::<probe::kernels::Format<13>>+0x40>
   15aa7:	4c 89 c0             	mov    %r8,%rax
   15aaa:	48 85 d2             	test   %rdx,%rdx
   15aad:	74 2b                	je     15ada <probe::kernels::generic::<probe::kernels::Format<13>>+0xba>
   15aaf:	31 f6                	xor    %esi,%esi
   15ab1:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15ab8:	0f 1f 84 00 00 00 00 
   15abf:	00 
   15ac0:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15ac4:	4c 31 c0             	xor    %r8,%rax
   15ac7:	48 0f af c1          	imul   %rcx,%rax
   15acb:	48 c1 c0 07          	rol    $0x7,%rax
   15acf:	48 ff c6             	inc    %rsi
   15ad2:	49 89 c0             	mov    %rax,%r8
   15ad5:	48 39 f2             	cmp    %rsi,%rdx
   15ad8:	75 e6                	jne    15ac0 <probe::kernels::generic::<probe::kernels::Format<13>>+0xa0>
   15ada:	c3                   	ret
   15adb:	cc                   	int3
   15adc:	cc                   	int3
   15add:	cc                   	int3
   15ade:	cc                   	int3
   15adf:	cc                   	int3

0000000000015ae0 <probe::kernels::generic::<probe::kernels::Format<14>>>:
   15ae0:	48 85 f6             	test   %rsi,%rsi
   15ae3:	74 1d                	je     15b02 <probe::kernels::generic::<probe::kernels::Format<14>>+0x22>
   15ae5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   15aec:	01 00 00 
   15aef:	89 f2                	mov    %esi,%edx
   15af1:	83 e2 03             	and    $0x3,%edx
   15af4:	48 83 fe 04          	cmp    $0x4,%rsi
   15af8:	73 0e                	jae    15b08 <probe::kernels::generic::<probe::kernels::Format<14>>+0x28>
   15afa:	41 b8 0e 00 00 00    	mov    $0xe,%r8d
   15b00:	eb 65                	jmp    15b67 <probe::kernels::generic::<probe::kernels::Format<14>>+0x87>
   15b02:	b8 0e 00 00 00       	mov    $0xe,%eax
   15b07:	c3                   	ret
   15b08:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   15b0f:	ff ff 7f 
   15b12:	48 21 c6             	and    %rax,%rsi
   15b15:	41 b8 0e 00 00 00    	mov    $0xe,%r8d
   15b1b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15b20:	0f b6 07             	movzbl (%rdi),%eax
   15b23:	4c 31 c0             	xor    %r8,%rax
   15b26:	48 0f af c1          	imul   %rcx,%rax
   15b2a:	48 c1 c0 07          	rol    $0x7,%rax
   15b2e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15b33:	49 31 c0             	xor    %rax,%r8
   15b36:	4c 0f af c1          	imul   %rcx,%r8
   15b3a:	49 c1 c0 07          	rol    $0x7,%r8
   15b3e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15b42:	4c 31 c0             	xor    %r8,%rax
   15b45:	48 0f af c1          	imul   %rcx,%rax
   15b49:	48 c1 c0 07          	rol    $0x7,%rax
   15b4d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15b52:	48 83 c7 04          	add    $0x4,%rdi
   15b56:	49 31 c0             	xor    %rax,%r8
   15b59:	4c 0f af c1          	imul   %rcx,%r8
   15b5d:	49 c1 c0 07          	rol    $0x7,%r8
   15b61:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15b65:	75 b9                	jne    15b20 <probe::kernels::generic::<probe::kernels::Format<14>>+0x40>
   15b67:	4c 89 c0             	mov    %r8,%rax
   15b6a:	48 85 d2             	test   %rdx,%rdx
   15b6d:	74 2b                	je     15b9a <probe::kernels::generic::<probe::kernels::Format<14>>+0xba>
   15b6f:	31 f6                	xor    %esi,%esi
   15b71:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15b78:	0f 1f 84 00 00 00 00 
   15b7f:	00 
   15b80:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15b84:	4c 31 c0             	xor    %r8,%rax
   15b87:	48 0f af c1          	imul   %rcx,%rax
   15b8b:	48 c1 c0 07          	rol    $0x7,%rax
   15b8f:	48 ff c6             	inc    %rsi
   15b92:	49 89 c0             	mov    %rax,%r8
   15b95:	48 39 f2             	cmp    %rsi,%rdx
   15b98:	75 e6                	jne    15b80 <probe::kernels::generic::<probe::kernels::Format<14>>+0xa0>
   15b9a:	c3                   	ret
   15b9b:	cc                   	int3
   15b9c:	cc                   	int3
   15b9d:	cc                   	int3
   15b9e:	cc                   	int3
   15b9f:	cc                   	int3

0000000000015ba0 <probe::kernels::generic::<probe::kernels::Format<15>>>:
   15ba0:	48 85 f6             	test   %rsi,%rsi
   15ba3:	74 1d                	je     15bc2 <probe::kernels::generic::<probe::kernels::Format<15>>+0x22>
   15ba5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   15bac:	01 00 00 
   15baf:	89 f2                	mov    %esi,%edx
   15bb1:	83 e2 03             	and    $0x3,%edx
   15bb4:	48 83 fe 04          	cmp    $0x4,%rsi
   15bb8:	73 0e                	jae    15bc8 <probe::kernels::generic::<probe::kernels::Format<15>>+0x28>
   15bba:	41 b8 0f 00 00 00    	mov    $0xf,%r8d
   15bc0:	eb 65                	jmp    15c27 <probe::kernels::generic::<probe::kernels::Format<15>>+0x87>
   15bc2:	b8 0f 00 00 00       	mov    $0xf,%eax
   15bc7:	c3                   	ret
   15bc8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   15bcf:	ff ff 7f 
   15bd2:	48 21 c6             	and    %rax,%rsi
   15bd5:	41 b8 0f 00 00 00    	mov    $0xf,%r8d
   15bdb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15be0:	0f b6 07             	movzbl (%rdi),%eax
   15be3:	4c 31 c0             	xor    %r8,%rax
   15be6:	48 0f af c1          	imul   %rcx,%rax
   15bea:	48 c1 c0 07          	rol    $0x7,%rax
   15bee:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15bf3:	49 31 c0             	xor    %rax,%r8
   15bf6:	4c 0f af c1          	imul   %rcx,%r8
   15bfa:	49 c1 c0 07          	rol    $0x7,%r8
   15bfe:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15c02:	4c 31 c0             	xor    %r8,%rax
   15c05:	48 0f af c1          	imul   %rcx,%rax
   15c09:	48 c1 c0 07          	rol    $0x7,%rax
   15c0d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15c12:	48 83 c7 04          	add    $0x4,%rdi
   15c16:	49 31 c0             	xor    %rax,%r8
   15c19:	4c 0f af c1          	imul   %rcx,%r8
   15c1d:	49 c1 c0 07          	rol    $0x7,%r8
   15c21:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15c25:	75 b9                	jne    15be0 <probe::kernels::generic::<probe::kernels::Format<15>>+0x40>
   15c27:	4c 89 c0             	mov    %r8,%rax
   15c2a:	48 85 d2             	test   %rdx,%rdx
   15c2d:	74 2b                	je     15c5a <probe::kernels::generic::<probe::kernels::Format<15>>+0xba>
   15c2f:	31 f6                	xor    %esi,%esi
   15c31:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15c38:	0f 1f 84 00 00 00 00 
   15c3f:	00 
   15c40:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15c44:	4c 31 c0             	xor    %r8,%rax
   15c47:	48 0f af c1          	imul   %rcx,%rax
   15c4b:	48 c1 c0 07          	rol    $0x7,%rax
   15c4f:	48 ff c6             	inc    %rsi
   15c52:	49 89 c0             	mov    %rax,%r8
   15c55:	48 39 f2             	cmp    %rsi,%rdx
   15c58:	75 e6                	jne    15c40 <probe::kernels::generic::<probe::kernels::Format<15>>+0xa0>
   15c5a:	c3                   	ret
   15c5b:	cc                   	int3
   15c5c:	cc                   	int3
   15c5d:	cc                   	int3
   15c5e:	cc                   	int3
   15c5f:	cc                   	int3
