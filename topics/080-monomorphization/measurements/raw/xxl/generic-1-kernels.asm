0000000000014ec0 <probe::kernels::generic::<probe::kernels::Format<1>>>:
   14ec0:	48 85 f6             	test   %rsi,%rsi
   14ec3:	74 1d                	je     14ee2 <probe::kernels::generic::<probe::kernels::Format<1>>+0x22>
   14ec5:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   14ecc:	01 00 00 
   14ecf:	89 f2                	mov    %esi,%edx
   14ed1:	83 e2 03             	and    $0x3,%edx
   14ed4:	48 83 fe 04          	cmp    $0x4,%rsi
   14ed8:	73 0e                	jae    14ee8 <probe::kernels::generic::<probe::kernels::Format<1>>+0x28>
   14eda:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   14ee0:	eb 65                	jmp    14f47 <probe::kernels::generic::<probe::kernels::Format<1>>+0x87>
   14ee2:	b8 01 00 00 00       	mov    $0x1,%eax
   14ee7:	c3                   	ret
   14ee8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   14eef:	ff ff 7f 
   14ef2:	48 21 c6             	and    %rax,%rsi
   14ef5:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   14efb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   14f00:	0f b6 07             	movzbl (%rdi),%eax
   14f03:	4c 31 c0             	xor    %r8,%rax
   14f06:	48 0f af c1          	imul   %rcx,%rax
   14f0a:	48 c1 c0 07          	rol    $0x7,%rax
   14f0e:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   14f13:	49 31 c0             	xor    %rax,%r8
   14f16:	4c 0f af c1          	imul   %rcx,%r8
   14f1a:	49 c1 c0 07          	rol    $0x7,%r8
   14f1e:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   14f22:	4c 31 c0             	xor    %r8,%rax
   14f25:	48 0f af c1          	imul   %rcx,%rax
   14f29:	48 c1 c0 07          	rol    $0x7,%rax
   14f2d:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   14f32:	48 83 c7 04          	add    $0x4,%rdi
   14f36:	49 31 c0             	xor    %rax,%r8
   14f39:	4c 0f af c1          	imul   %rcx,%r8
   14f3d:	49 c1 c0 07          	rol    $0x7,%r8
   14f41:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   14f45:	75 b9                	jne    14f00 <probe::kernels::generic::<probe::kernels::Format<1>>+0x40>
   14f47:	4c 89 c0             	mov    %r8,%rax
   14f4a:	48 85 d2             	test   %rdx,%rdx
   14f4d:	74 2b                	je     14f7a <probe::kernels::generic::<probe::kernels::Format<1>>+0xba>
   14f4f:	31 f6                	xor    %esi,%esi
   14f51:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   14f58:	0f 1f 84 00 00 00 00 
   14f5f:	00 
   14f60:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   14f64:	4c 31 c0             	xor    %r8,%rax
   14f67:	48 0f af c1          	imul   %rcx,%rax
   14f6b:	48 c1 c0 07          	rol    $0x7,%rax
   14f6f:	48 ff c6             	inc    %rsi
   14f72:	49 89 c0             	mov    %rax,%r8
   14f75:	48 39 f2             	cmp    %rsi,%rdx
   14f78:	75 e6                	jne    14f60 <probe::kernels::generic::<probe::kernels::Format<1>>+0xa0>
   14f7a:	c3                   	ret
   14f7b:	cc                   	int3
   14f7c:	cc                   	int3
   14f7d:	cc                   	int3
   14f7e:	cc                   	int3
   14f7f:	cc                   	int3
