0000000000014ee0 <probe::kernels::outlined::<probe::kernels::Format<1>>>:
   14ee0:	e9 9b 0b 00 00       	jmp    15a80 <probe::kernels::shared_core>
   14ee5:	cc                   	int3
   14ee6:	cc                   	int3
   14ee7:	cc                   	int3
   14ee8:	cc                   	int3
   14ee9:	cc                   	int3
   14eea:	cc                   	int3
   14eeb:	cc                   	int3
   14eec:	cc                   	int3
   14eed:	cc                   	int3
   14eee:	cc                   	int3
   14eef:	cc                   	int3

0000000000015a80 <probe::kernels::shared_core>:
   15a80:	48 85 f6             	test   %rsi,%rsi
   15a83:	74 1d                	je     15aa2 <probe::kernels::shared_core+0x22>
   15a85:	48 b9 b3 01 00 00 00 	movabs $0x100000001b3,%rcx
   15a8c:	01 00 00 
   15a8f:	89 f2                	mov    %esi,%edx
   15a91:	83 e2 03             	and    $0x3,%edx
   15a94:	48 83 fe 04          	cmp    $0x4,%rsi
   15a98:	73 0e                	jae    15aa8 <probe::kernels::shared_core+0x28>
   15a9a:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   15aa0:	eb 65                	jmp    15b07 <probe::kernels::shared_core+0x87>
   15aa2:	b8 01 00 00 00       	mov    $0x1,%eax
   15aa7:	c3                   	ret
   15aa8:	48 b8 fc ff ff ff ff 	movabs $0x7ffffffffffffffc,%rax
   15aaf:	ff ff 7f 
   15ab2:	48 21 c6             	and    %rax,%rsi
   15ab5:	41 b8 01 00 00 00    	mov    $0x1,%r8d
   15abb:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15ac0:	0f b6 07             	movzbl (%rdi),%eax
   15ac3:	4c 31 c0             	xor    %r8,%rax
   15ac6:	48 0f af c1          	imul   %rcx,%rax
   15aca:	48 c1 c0 07          	rol    $0x7,%rax
   15ace:	44 0f b6 47 01       	movzbl 0x1(%rdi),%r8d
   15ad3:	49 31 c0             	xor    %rax,%r8
   15ad6:	4c 0f af c1          	imul   %rcx,%r8
   15ada:	49 c1 c0 07          	rol    $0x7,%r8
   15ade:	0f b6 47 02          	movzbl 0x2(%rdi),%eax
   15ae2:	4c 31 c0             	xor    %r8,%rax
   15ae5:	48 0f af c1          	imul   %rcx,%rax
   15ae9:	48 c1 c0 07          	rol    $0x7,%rax
   15aed:	44 0f b6 47 03       	movzbl 0x3(%rdi),%r8d
   15af2:	48 83 c7 04          	add    $0x4,%rdi
   15af6:	49 31 c0             	xor    %rax,%r8
   15af9:	4c 0f af c1          	imul   %rcx,%r8
   15afd:	49 c1 c0 07          	rol    $0x7,%r8
   15b01:	48 83 c6 fc          	add    $0xfffffffffffffffc,%rsi
   15b05:	75 b9                	jne    15ac0 <probe::kernels::shared_core+0x40>
   15b07:	4c 89 c0             	mov    %r8,%rax
   15b0a:	48 85 d2             	test   %rdx,%rdx
   15b0d:	74 2b                	je     15b3a <probe::kernels::shared_core+0xba>
   15b0f:	31 f6                	xor    %esi,%esi
   15b11:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15b18:	0f 1f 84 00 00 00 00 
   15b1f:	00 
   15b20:	0f b6 04 37          	movzbl (%rdi,%rsi,1),%eax
   15b24:	4c 31 c0             	xor    %r8,%rax
   15b27:	48 0f af c1          	imul   %rcx,%rax
   15b2b:	48 c1 c0 07          	rol    $0x7,%rax
   15b2f:	48 ff c6             	inc    %rsi
   15b32:	49 89 c0             	mov    %rax,%r8
   15b35:	48 39 f2             	cmp    %rsi,%rdx
   15b38:	75 e6                	jne    15b20 <probe::kernels::shared_core+0xa0>
   15b3a:	c3                   	ret
   15b3b:	cc                   	int3
   15b3c:	cc                   	int3
   15b3d:	cc                   	int3
   15b3e:	cc                   	int3
   15b3f:	cc                   	int3
