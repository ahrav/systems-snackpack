00000000000156a0 <topic081_rust_runtime::Policy::batch>:
   156a0:	48 85 d2             	test   %rdx,%rdx
   156a3:	74 12                	je     156b7 <topic081_rust_runtime::Policy::batch+0x17>
   156a5:	48 8b 0f             	mov    (%rdi),%rcx
   156a8:	48 83 fa 04          	cmp    $0x4,%rdx
   156ac:	73 0c                	jae    156ba <topic081_rust_runtime::Policy::batch+0x1a>
   156ae:	31 ff                	xor    %edi,%edi
   156b0:	31 c0                	xor    %eax,%eax
   156b2:	e9 f6 00 00 00       	jmp    157ad <topic081_rust_runtime::Policy::batch+0x10d>
   156b7:	31 c0                	xor    %eax,%eax
   156b9:	c3                   	ret
   156ba:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   156c1:	ff ff 0f 
   156c4:	62 f2 fd 28 7c c1    	vpbroadcastq %rcx,%ymm0
   156ca:	48 83 fa 10          	cmp    $0x10,%rdx
   156ce:	73 09                	jae    156d9 <topic081_rust_runtime::Policy::batch+0x39>
   156d0:	31 ff                	xor    %edi,%edi
   156d2:	31 c0                	xor    %eax,%eax
   156d4:	e9 89 00 00 00       	jmp    15762 <topic081_rust_runtime::Policy::batch+0xc2>
   156d9:	48 89 d7             	mov    %rdx,%rdi
   156dc:	4c 21 c7             	and    %r8,%rdi
   156df:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   156e6:	00 
   156e7:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   156eb:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   156ef:	45 31 c9             	xor    %r9d,%r9d
   156f2:	c5 e9 ef d2          	vpxor  %xmm2,%xmm2,%xmm2
   156f6:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   156fa:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   156fe:	66 90                	xchg   %ax,%ax
   15700:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   15704:	c5 ed d4 d0          	vpaddq %ymm0,%ymm2,%ymm2
   15708:	c5 e5 d4 d8          	vpaddq %ymm0,%ymm3,%ymm3
   1570c:	c5 dd d4 e0          	vpaddq %ymm0,%ymm4,%ymm4
   15710:	c4 a1 75 d4 0c 0e    	vpaddq (%rsi,%r9,1),%ymm1,%ymm1
   15716:	c4 a1 6d d4 54 0e 20 	vpaddq 0x20(%rsi,%r9,1),%ymm2,%ymm2
   1571d:	c4 a1 65 d4 5c 0e 40 	vpaddq 0x40(%rsi,%r9,1),%ymm3,%ymm3
   15724:	c4 a1 5d d4 64 0e 60 	vpaddq 0x60(%rsi,%r9,1),%ymm4,%ymm4
   1572b:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   1572f:	4c 39 c8             	cmp    %r9,%rax
   15732:	75 cc                	jne    15700 <topic081_rust_runtime::Policy::batch+0x60>
   15734:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   15738:	c5 dd d4 d3          	vpaddq %ymm3,%ymm4,%ymm2
   1573c:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   15740:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   15746:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   1574a:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   1574f:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   15753:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   15758:	48 39 fa             	cmp    %rdi,%rdx
   1575b:	74 5f                	je     157bc <topic081_rust_runtime::Policy::batch+0x11c>
   1575d:	f6 c2 0c             	test   $0xc,%dl
   15760:	74 4b                	je     157ad <topic081_rust_runtime::Policy::batch+0x10d>
   15762:	49 89 f9             	mov    %rdi,%r9
   15765:	49 83 c0 0c          	add    $0xc,%r8
   15769:	4c 89 c7             	mov    %r8,%rdi
   1576c:	48 21 d7             	and    %rdx,%rdi
   1576f:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   15774:	66 66 66 2e 0f 1f 84 	data16 data16 cs nopw 0x0(%rax,%rax,1)
   1577b:	00 00 00 00 00 
   15780:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   15784:	c4 a1 75 d4 0c ce    	vpaddq (%rsi,%r9,8),%ymm1,%ymm1
   1578a:	49 83 c1 04          	add    $0x4,%r9
   1578e:	4c 39 cf             	cmp    %r9,%rdi
   15791:	75 ed                	jne    15780 <topic081_rust_runtime::Policy::batch+0xe0>
   15793:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   15799:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   1579d:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   157a2:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   157a6:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   157ab:	eb 0a                	jmp    157b7 <topic081_rust_runtime::Policy::batch+0x117>
   157ad:	48 01 c8             	add    %rcx,%rax
   157b0:	48 03 04 fe          	add    (%rsi,%rdi,8),%rax
   157b4:	48 ff c7             	inc    %rdi
   157b7:	48 39 fa             	cmp    %rdi,%rdx
   157ba:	75 f1                	jne    157ad <topic081_rust_runtime::Policy::batch+0x10d>
   157bc:	c5 f8 77             	vzeroupper
   157bf:	c3                   	ret


00000000000157c0 <topic081_rust_runtime::Policy::batch>:
   157c0:	48 85 d2             	test   %rdx,%rdx
   157c3:	74 12                	je     157d7 <topic081_rust_runtime::Policy::batch+0x17>
   157c5:	48 8b 0f             	mov    (%rdi),%rcx
   157c8:	48 83 fa 04          	cmp    $0x4,%rdx
   157cc:	73 0c                	jae    157da <topic081_rust_runtime::Policy::batch+0x1a>
   157ce:	31 ff                	xor    %edi,%edi
   157d0:	31 c0                	xor    %eax,%eax
   157d2:	e9 69 01 00 00       	jmp    15940 <topic081_rust_runtime::Policy::batch+0x180>
   157d7:	31 c0                	xor    %eax,%eax
   157d9:	c3                   	ret
   157da:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   157e1:	ff ff 0f 
   157e4:	62 f2 fd 28 7c c1    	vpbroadcastq %rcx,%ymm0
   157ea:	48 83 fa 10          	cmp    $0x10,%rdx
   157ee:	73 09                	jae    157f9 <topic081_rust_runtime::Policy::batch+0x39>
   157f0:	31 ff                	xor    %edi,%edi
   157f2:	31 c0                	xor    %eax,%eax
   157f4:	e9 df 00 00 00       	jmp    158d8 <topic081_rust_runtime::Policy::batch+0x118>
   157f9:	48 89 d7             	mov    %rdx,%rdi
   157fc:	4c 21 c7             	and    %r8,%rdi
   157ff:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   15806:	00 
   15807:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   1580b:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   1580f:	45 31 c9             	xor    %r9d,%r9d
   15812:	c4 e2 7d 59 15 e5 fc 	vpbroadcastq -0x1031b(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   15819:	fe ff 
   1581b:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   1581f:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   15823:	c5 d1 ef ed          	vpxor  %xmm5,%xmm5,%xmm5
   15827:	66 0f 1f 84 00 00 00 	nopw   0x0(%rax,%rax,1)
   1582e:	00 00 
   15830:	c5 c8 57 f6          	vxorps %xmm6,%xmm6,%xmm6
   15834:	62 b2 fd 28 40 34 0e 	vpmullq (%rsi,%r9,1),%ymm0,%ymm6
   1583b:	c5 c0 57 ff          	vxorps %xmm7,%xmm7,%xmm7
   1583f:	62 b2 fd 28 40 7c 0e 	vpmullq 0x20(%rsi,%r9,1),%ymm0,%ymm7
   15846:	01 
   15847:	c4 41 38 57 c0       	vxorps %xmm8,%xmm8,%xmm8
   1584c:	62 32 fd 28 40 44 0e 	vpmullq 0x40(%rsi,%r9,1),%ymm0,%ymm8
   15853:	02 
   15854:	c4 41 30 57 c9       	vxorps %xmm9,%xmm9,%xmm9
   15859:	62 32 fd 28 40 4c 0e 	vpmullq 0x60(%rsi,%r9,1),%ymm0,%ymm9
   15860:	03 
   15861:	62 f1 cd 28 72 ce 0d 	vprolq $0xd,%ymm6,%ymm6
   15868:	62 f1 c5 28 72 cf 0d 	vprolq $0xd,%ymm7,%ymm7
   1586f:	62 d1 bd 28 72 c8 0d 	vprolq $0xd,%ymm8,%ymm8
   15876:	62 d1 b5 28 72 c9 0d 	vprolq $0xd,%ymm9,%ymm9
   1587d:	c5 cd ef f2          	vpxor  %ymm2,%ymm6,%ymm6
   15881:	c5 cd d4 c9          	vpaddq %ymm1,%ymm6,%ymm1
   15885:	c5 c5 ef f2          	vpxor  %ymm2,%ymm7,%ymm6
   15889:	c5 cd d4 db          	vpaddq %ymm3,%ymm6,%ymm3
   1588d:	c5 bd ef f2          	vpxor  %ymm2,%ymm8,%ymm6
   15891:	c5 cd d4 e4          	vpaddq %ymm4,%ymm6,%ymm4
   15895:	c5 b5 ef f2          	vpxor  %ymm2,%ymm9,%ymm6
   15899:	c5 cd d4 ed          	vpaddq %ymm5,%ymm6,%ymm5
   1589d:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   158a1:	4c 39 c8             	cmp    %r9,%rax
   158a4:	75 8a                	jne    15830 <topic081_rust_runtime::Policy::batch+0x70>
   158a6:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   158aa:	c5 dd d4 c9          	vpaddq %ymm1,%ymm4,%ymm1
   158ae:	c5 d5 d4 c9          	vpaddq %ymm1,%ymm5,%ymm1
   158b2:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   158b8:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   158bc:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   158c1:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   158c5:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   158ca:	48 39 fa             	cmp    %rdi,%rdx
   158cd:	0f 84 99 00 00 00    	je     1596c <topic081_rust_runtime::Policy::batch+0x1ac>
   158d3:	f6 c2 0c             	test   $0xc,%dl
   158d6:	74 68                	je     15940 <topic081_rust_runtime::Policy::batch+0x180>
   158d8:	49 89 f9             	mov    %rdi,%r9
   158db:	49 83 c0 0c          	add    $0xc,%r8
   158df:	4c 89 c7             	mov    %r8,%rdi
   158e2:	48 21 d7             	and    %rdx,%rdi
   158e5:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   158ea:	c4 e2 7d 59 15 0d fc 	vpbroadcastq -0x103f3(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   158f1:	fe ff 
   158f3:	66 66 66 66 2e 0f 1f 	data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   158fa:	84 00 00 00 00 00 
   15900:	c5 e0 57 db          	vxorps %xmm3,%xmm3,%xmm3
   15904:	62 b2 fd 28 40 1c ce 	vpmullq (%rsi,%r9,8),%ymm0,%ymm3
   1590b:	62 f1 e5 28 72 cb 0d 	vprolq $0xd,%ymm3,%ymm3
   15912:	c5 e5 ef da          	vpxor  %ymm2,%ymm3,%ymm3
   15916:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   1591a:	49 83 c1 04          	add    $0x4,%r9
   1591e:	4c 39 cf             	cmp    %r9,%rdi
   15921:	75 dd                	jne    15900 <topic081_rust_runtime::Policy::batch+0x140>
   15923:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   15929:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   1592d:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   15932:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   15936:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   1593b:	48 39 fa             	cmp    %rdi,%rdx
   1593e:	74 2c                	je     1596c <topic081_rust_runtime::Policy::batch+0x1ac>
   15940:	49 b8 03 ed 92 d1 32 	movabs $0xd1b54a32d192ed03,%r8
   15947:	4a b5 d1 
   1594a:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   15950:	4c 8b 0c fe          	mov    (%rsi,%rdi,8),%r9
   15954:	4c 0f af c9          	imul   %rcx,%r9
   15958:	c4 43 fb f0 c9 33    	rorx   $0x33,%r9,%r9
   1595e:	4d 31 c1             	xor    %r8,%r9
   15961:	4c 01 c8             	add    %r9,%rax
   15964:	48 ff c7             	inc    %rdi
   15967:	48 39 fa             	cmp    %rdi,%rdx
   1596a:	75 e4                	jne    15950 <topic081_rust_runtime::Policy::batch+0x190>
   1596c:	c5 f8 77             	vzeroupper
   1596f:	c3                   	ret


0000000000015970 <topic081_rust_runtime::generic>:
   15970:	48 85 d2             	test   %rdx,%rdx
   15973:	74 0f                	je     15984 <topic081_rust_runtime::generic+0x14>
   15975:	48 83 fa 04          	cmp    $0x4,%rdx
   15979:	73 0c                	jae    15987 <topic081_rust_runtime::generic+0x17>
   1597b:	31 c9                	xor    %ecx,%ecx
   1597d:	31 c0                	xor    %eax,%eax
   1597f:	e9 6c 01 00 00       	jmp    15af0 <topic081_rust_runtime::generic+0x180>
   15984:	31 c0                	xor    %eax,%eax
   15986:	c3                   	ret
   15987:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   1598e:	ff ff 0f 
   15991:	62 f2 fd 28 7c c7    	vpbroadcastq %rdi,%ymm0
   15997:	48 83 fa 10          	cmp    $0x10,%rdx
   1599b:	73 09                	jae    159a6 <topic081_rust_runtime::generic+0x36>
   1599d:	31 c9                	xor    %ecx,%ecx
   1599f:	31 c0                	xor    %eax,%eax
   159a1:	e9 e2 00 00 00       	jmp    15a88 <topic081_rust_runtime::generic+0x118>
   159a6:	48 89 d1             	mov    %rdx,%rcx
   159a9:	4c 21 c1             	and    %r8,%rcx
   159ac:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   159b3:	00 
   159b4:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   159b8:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   159bc:	45 31 c9             	xor    %r9d,%r9d
   159bf:	c4 e2 7d 59 15 38 fb 	vpbroadcastq -0x104c8(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   159c6:	fe ff 
   159c8:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   159cc:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   159d0:	c5 d1 ef ed          	vpxor  %xmm5,%xmm5,%xmm5
   159d4:	66 66 66 2e 0f 1f 84 	data16 data16 cs nopw 0x0(%rax,%rax,1)
   159db:	00 00 00 00 00 
   159e0:	c5 c8 57 f6          	vxorps %xmm6,%xmm6,%xmm6
   159e4:	62 b2 fd 28 40 34 0e 	vpmullq (%rsi,%r9,1),%ymm0,%ymm6
   159eb:	c5 c0 57 ff          	vxorps %xmm7,%xmm7,%xmm7
   159ef:	62 b2 fd 28 40 7c 0e 	vpmullq 0x20(%rsi,%r9,1),%ymm0,%ymm7
   159f6:	01 
   159f7:	c4 41 38 57 c0       	vxorps %xmm8,%xmm8,%xmm8
   159fc:	62 32 fd 28 40 44 0e 	vpmullq 0x40(%rsi,%r9,1),%ymm0,%ymm8
   15a03:	02 
   15a04:	c4 41 30 57 c9       	vxorps %xmm9,%xmm9,%xmm9
   15a09:	62 32 fd 28 40 4c 0e 	vpmullq 0x60(%rsi,%r9,1),%ymm0,%ymm9
   15a10:	03 
   15a11:	62 f1 cd 28 72 ce 0d 	vprolq $0xd,%ymm6,%ymm6
   15a18:	62 f1 c5 28 72 cf 0d 	vprolq $0xd,%ymm7,%ymm7
   15a1f:	62 d1 bd 28 72 c8 0d 	vprolq $0xd,%ymm8,%ymm8
   15a26:	62 d1 b5 28 72 c9 0d 	vprolq $0xd,%ymm9,%ymm9
   15a2d:	c5 cd ef f2          	vpxor  %ymm2,%ymm6,%ymm6
   15a31:	c5 cd d4 c9          	vpaddq %ymm1,%ymm6,%ymm1
   15a35:	c5 c5 ef f2          	vpxor  %ymm2,%ymm7,%ymm6
   15a39:	c5 cd d4 db          	vpaddq %ymm3,%ymm6,%ymm3
   15a3d:	c5 bd ef f2          	vpxor  %ymm2,%ymm8,%ymm6
   15a41:	c5 cd d4 e4          	vpaddq %ymm4,%ymm6,%ymm4
   15a45:	c5 b5 ef f2          	vpxor  %ymm2,%ymm9,%ymm6
   15a49:	c5 cd d4 ed          	vpaddq %ymm5,%ymm6,%ymm5
   15a4d:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   15a51:	4c 39 c8             	cmp    %r9,%rax
   15a54:	75 8a                	jne    159e0 <topic081_rust_runtime::generic+0x70>
   15a56:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   15a5a:	c5 dd d4 c9          	vpaddq %ymm1,%ymm4,%ymm1
   15a5e:	c5 d5 d4 c9          	vpaddq %ymm1,%ymm5,%ymm1
   15a62:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   15a68:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   15a6c:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   15a71:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   15a75:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   15a7a:	48 39 ca             	cmp    %rcx,%rdx
   15a7d:	0f 84 99 00 00 00    	je     15b1c <topic081_rust_runtime::generic+0x1ac>
   15a83:	f6 c2 0c             	test   $0xc,%dl
   15a86:	74 68                	je     15af0 <topic081_rust_runtime::generic+0x180>
   15a88:	49 89 c9             	mov    %rcx,%r9
   15a8b:	49 83 c0 0c          	add    $0xc,%r8
   15a8f:	4c 89 c1             	mov    %r8,%rcx
   15a92:	48 21 d1             	and    %rdx,%rcx
   15a95:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   15a9a:	c4 e2 7d 59 15 5d fa 	vpbroadcastq -0x105a3(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   15aa1:	fe ff 
   15aa3:	66 66 66 66 2e 0f 1f 	data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   15aaa:	84 00 00 00 00 00 
   15ab0:	c5 e0 57 db          	vxorps %xmm3,%xmm3,%xmm3
   15ab4:	62 b2 fd 28 40 1c ce 	vpmullq (%rsi,%r9,8),%ymm0,%ymm3
   15abb:	62 f1 e5 28 72 cb 0d 	vprolq $0xd,%ymm3,%ymm3
   15ac2:	c5 e5 ef da          	vpxor  %ymm2,%ymm3,%ymm3
   15ac6:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   15aca:	49 83 c1 04          	add    $0x4,%r9
   15ace:	4c 39 c9             	cmp    %r9,%rcx
   15ad1:	75 dd                	jne    15ab0 <topic081_rust_runtime::generic+0x140>
   15ad3:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   15ad9:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   15add:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   15ae2:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   15ae6:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   15aeb:	48 39 ca             	cmp    %rcx,%rdx
   15aee:	74 2c                	je     15b1c <topic081_rust_runtime::generic+0x1ac>
   15af0:	49 b8 03 ed 92 d1 32 	movabs $0xd1b54a32d192ed03,%r8
   15af7:	4a b5 d1 
   15afa:	66 0f 1f 44 00 00    	nopw   0x0(%rax,%rax,1)
   15b00:	4c 8b 0c ce          	mov    (%rsi,%rcx,8),%r9
   15b04:	4c 0f af cf          	imul   %rdi,%r9
   15b08:	c4 43 fb f0 c9 33    	rorx   $0x33,%r9,%r9
   15b0e:	4d 31 c1             	xor    %r8,%r9
   15b11:	4c 01 c8             	add    %r9,%rax
   15b14:	48 ff c1             	inc    %rcx
   15b17:	48 39 ca             	cmp    %rcx,%rdx
   15b1a:	75 e4                	jne    15b00 <topic081_rust_runtime::generic+0x190>
   15b1c:	c5 f8 77             	vzeroupper
   15b1f:	c3                   	ret


0000000000015b20 <topic081_rust_runtime::generic>:
   15b20:	48 85 d2             	test   %rdx,%rdx
   15b23:	74 0f                	je     15b34 <topic081_rust_runtime::generic+0x14>
   15b25:	48 83 fa 04          	cmp    $0x4,%rdx
   15b29:	73 0c                	jae    15b37 <topic081_rust_runtime::generic+0x17>
   15b2b:	31 c9                	xor    %ecx,%ecx
   15b2d:	31 c0                	xor    %eax,%eax
   15b2f:	e9 f9 00 00 00       	jmp    15c2d <topic081_rust_runtime::generic+0x10d>
   15b34:	31 c0                	xor    %eax,%eax
   15b36:	c3                   	ret
   15b37:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   15b3e:	ff ff 0f 
   15b41:	62 f2 fd 28 7c c7    	vpbroadcastq %rdi,%ymm0
   15b47:	48 83 fa 10          	cmp    $0x10,%rdx
   15b4b:	73 09                	jae    15b56 <topic081_rust_runtime::generic+0x36>
   15b4d:	31 c9                	xor    %ecx,%ecx
   15b4f:	31 c0                	xor    %eax,%eax
   15b51:	e9 8c 00 00 00       	jmp    15be2 <topic081_rust_runtime::generic+0xc2>
   15b56:	48 89 d1             	mov    %rdx,%rcx
   15b59:	4c 21 c1             	and    %r8,%rcx
   15b5c:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   15b63:	00 
   15b64:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   15b68:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   15b6c:	45 31 c9             	xor    %r9d,%r9d
   15b6f:	c5 e9 ef d2          	vpxor  %xmm2,%xmm2,%xmm2
   15b73:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   15b77:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   15b7b:	0f 1f 44 00 00       	nopl   0x0(%rax,%rax,1)
   15b80:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   15b84:	c5 ed d4 d0          	vpaddq %ymm0,%ymm2,%ymm2
   15b88:	c5 e5 d4 d8          	vpaddq %ymm0,%ymm3,%ymm3
   15b8c:	c5 dd d4 e0          	vpaddq %ymm0,%ymm4,%ymm4
   15b90:	c4 a1 75 d4 0c 0e    	vpaddq (%rsi,%r9,1),%ymm1,%ymm1
   15b96:	c4 a1 6d d4 54 0e 20 	vpaddq 0x20(%rsi,%r9,1),%ymm2,%ymm2
   15b9d:	c4 a1 65 d4 5c 0e 40 	vpaddq 0x40(%rsi,%r9,1),%ymm3,%ymm3
   15ba4:	c4 a1 5d d4 64 0e 60 	vpaddq 0x60(%rsi,%r9,1),%ymm4,%ymm4
   15bab:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   15baf:	4c 39 c8             	cmp    %r9,%rax
   15bb2:	75 cc                	jne    15b80 <topic081_rust_runtime::generic+0x60>
   15bb4:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   15bb8:	c5 dd d4 d3          	vpaddq %ymm3,%ymm4,%ymm2
   15bbc:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   15bc0:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   15bc6:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   15bca:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   15bcf:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   15bd3:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   15bd8:	48 39 ca             	cmp    %rcx,%rdx
   15bdb:	74 5f                	je     15c3c <topic081_rust_runtime::generic+0x11c>
   15bdd:	f6 c2 0c             	test   $0xc,%dl
   15be0:	74 4b                	je     15c2d <topic081_rust_runtime::generic+0x10d>
   15be2:	49 89 c9             	mov    %rcx,%r9
   15be5:	49 83 c0 0c          	add    $0xc,%r8
   15be9:	4c 89 c1             	mov    %r8,%rcx
   15bec:	48 21 d1             	and    %rdx,%rcx
   15bef:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   15bf4:	66 66 66 2e 0f 1f 84 	data16 data16 cs nopw 0x0(%rax,%rax,1)
   15bfb:	00 00 00 00 00 
   15c00:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   15c04:	c4 a1 75 d4 0c ce    	vpaddq (%rsi,%r9,8),%ymm1,%ymm1
   15c0a:	49 83 c1 04          	add    $0x4,%r9
   15c0e:	4c 39 c9             	cmp    %r9,%rcx
   15c11:	75 ed                	jne    15c00 <topic081_rust_runtime::generic+0xe0>
   15c13:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   15c19:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   15c1d:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   15c22:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   15c26:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   15c2b:	eb 0a                	jmp    15c37 <topic081_rust_runtime::generic+0x117>
   15c2d:	48 01 f8             	add    %rdi,%rax
   15c30:	48 03 04 ce          	add    (%rsi,%rcx,8),%rax
   15c34:	48 ff c1             	inc    %rcx
   15c37:	48 39 ca             	cmp    %rcx,%rdx
   15c3a:	75 f1                	jne    15c2d <topic081_rust_runtime::generic+0x10d>
   15c3c:	c5 f8 77             	vzeroupper
   15c3f:	c3                   	ret


0000000000016ee0 <<topic081_rust_runtime::Add as topic081_rust_runtime::Policy>::apply>:
   16ee0:	48 89 f0             	mov    %rsi,%rax
   16ee3:	48 03 07             	add    (%rdi),%rax
   16ee6:	c3                   	ret
   16ee7:	cc                   	int3
   16ee8:	cc                   	int3
   16ee9:	cc                   	int3
   16eea:	cc                   	int3
   16eeb:	cc                   	int3
   16eec:	cc                   	int3
   16eed:	cc                   	int3
   16eee:	cc                   	int3
   16eef:	cc                   	int3


0000000000016ef0 <<topic081_rust_runtime::Mix as topic081_rust_runtime::Policy>::apply>:
   16ef0:	48 0f af 37          	imul   (%rdi),%rsi
   16ef4:	c4 e3 fb f0 ce 33    	rorx   $0x33,%rsi,%rcx
   16efa:	48 b8 03 ed 92 d1 32 	movabs $0xd1b54a32d192ed03,%rax
   16f01:	4a b5 d1 
   16f04:	48 31 c8             	xor    %rcx,%rax
   16f07:	c3                   	ret
   16f08:	cc                   	int3
   16f09:	cc                   	int3
   16f0a:	cc                   	int3
   16f0b:	cc                   	int3
   16f0c:	cc                   	int3
   16f0d:	cc                   	int3
   16f0e:	cc                   	int3
   16f0f:	cc                   	int3


0000000000016fa0 <topic081_rust_runtime::enumerated>:
   16fa0:	83 3f 01             	cmpl   $0x1,(%rdi)
   16fa3:	75 18                	jne    16fbd <topic081_rust_runtime::enumerated+0x1d>
   16fa5:	48 85 d2             	test   %rdx,%rdx
   16fa8:	74 2b                	je     16fd5 <topic081_rust_runtime::enumerated+0x35>
   16faa:	48 8b 4f 08          	mov    0x8(%rdi),%rcx
   16fae:	48 83 fa 04          	cmp    $0x4,%rdx
   16fb2:	73 24                	jae    16fd8 <topic081_rust_runtime::enumerated+0x38>
   16fb4:	31 ff                	xor    %edi,%edi
   16fb6:	31 c0                	xor    %eax,%eax
   16fb8:	e9 a7 01 00 00       	jmp    17164 <topic081_rust_runtime::enumerated+0x1c4>
   16fbd:	48 85 d2             	test   %rdx,%rdx
   16fc0:	74 13                	je     16fd5 <topic081_rust_runtime::enumerated+0x35>
   16fc2:	48 8b 4f 08          	mov    0x8(%rdi),%rcx
   16fc6:	48 83 fa 04          	cmp    $0x4,%rdx
   16fca:	73 2b                	jae    16ff7 <topic081_rust_runtime::enumerated+0x57>
   16fcc:	31 ff                	xor    %edi,%edi
   16fce:	31 c0                	xor    %eax,%eax
   16fd0:	e9 98 02 00 00       	jmp    1726d <topic081_rust_runtime::enumerated+0x2cd>
   16fd5:	31 c0                	xor    %eax,%eax
   16fd7:	c3                   	ret
   16fd8:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   16fdf:	ff ff 0f 
   16fe2:	62 f2 fd 28 7c c1    	vpbroadcastq %rcx,%ymm0
   16fe8:	48 83 fa 10          	cmp    $0x10,%rdx
   16fec:	73 2c                	jae    1701a <topic081_rust_runtime::enumerated+0x7a>
   16fee:	31 ff                	xor    %edi,%edi
   16ff0:	31 c0                	xor    %eax,%eax
   16ff2:	e9 01 01 00 00       	jmp    170f8 <topic081_rust_runtime::enumerated+0x158>
   16ff7:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   16ffe:	ff ff 0f 
   17001:	62 f2 fd 28 7c c1    	vpbroadcastq %rcx,%ymm0
   17007:	48 83 fa 10          	cmp    $0x10,%rdx
   1700b:	0f 83 80 01 00 00    	jae    17191 <topic081_rust_runtime::enumerated+0x1f1>
   17011:	31 ff                	xor    %edi,%edi
   17013:	31 c0                	xor    %eax,%eax
   17015:	e9 08 02 00 00       	jmp    17222 <topic081_rust_runtime::enumerated+0x282>
   1701a:	48 89 d7             	mov    %rdx,%rdi
   1701d:	4c 21 c7             	and    %r8,%rdi
   17020:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   17027:	00 
   17028:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   1702c:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   17030:	45 31 c9             	xor    %r9d,%r9d
   17033:	c4 e2 7d 59 15 c4 e4 	vpbroadcastq -0x11b3c(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   1703a:	fe ff 
   1703c:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   17040:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   17044:	c5 d1 ef ed          	vpxor  %xmm5,%xmm5,%xmm5
   17048:	0f 1f 84 00 00 00 00 	nopl   0x0(%rax,%rax,1)
   1704f:	00 
   17050:	c5 c8 57 f6          	vxorps %xmm6,%xmm6,%xmm6
   17054:	62 b2 fd 28 40 34 0e 	vpmullq (%rsi,%r9,1),%ymm0,%ymm6
   1705b:	c5 c0 57 ff          	vxorps %xmm7,%xmm7,%xmm7
   1705f:	62 b2 fd 28 40 7c 0e 	vpmullq 0x20(%rsi,%r9,1),%ymm0,%ymm7
   17066:	01 
   17067:	c4 41 38 57 c0       	vxorps %xmm8,%xmm8,%xmm8
   1706c:	62 32 fd 28 40 44 0e 	vpmullq 0x40(%rsi,%r9,1),%ymm0,%ymm8
   17073:	02 
   17074:	c4 41 30 57 c9       	vxorps %xmm9,%xmm9,%xmm9
   17079:	62 32 fd 28 40 4c 0e 	vpmullq 0x60(%rsi,%r9,1),%ymm0,%ymm9
   17080:	03 
   17081:	62 f1 cd 28 72 ce 0d 	vprolq $0xd,%ymm6,%ymm6
   17088:	62 f1 c5 28 72 cf 0d 	vprolq $0xd,%ymm7,%ymm7
   1708f:	62 d1 bd 28 72 c8 0d 	vprolq $0xd,%ymm8,%ymm8
   17096:	62 d1 b5 28 72 c9 0d 	vprolq $0xd,%ymm9,%ymm9
   1709d:	c5 cd ef f2          	vpxor  %ymm2,%ymm6,%ymm6
   170a1:	c5 cd d4 c9          	vpaddq %ymm1,%ymm6,%ymm1
   170a5:	c5 c5 ef f2          	vpxor  %ymm2,%ymm7,%ymm6
   170a9:	c5 cd d4 db          	vpaddq %ymm3,%ymm6,%ymm3
   170ad:	c5 bd ef f2          	vpxor  %ymm2,%ymm8,%ymm6
   170b1:	c5 cd d4 e4          	vpaddq %ymm4,%ymm6,%ymm4
   170b5:	c5 b5 ef f2          	vpxor  %ymm2,%ymm9,%ymm6
   170b9:	c5 cd d4 ed          	vpaddq %ymm5,%ymm6,%ymm5
   170bd:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   170c1:	4c 39 c8             	cmp    %r9,%rax
   170c4:	75 8a                	jne    17050 <topic081_rust_runtime::enumerated+0xb0>
   170c6:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   170ca:	c5 dd d4 c9          	vpaddq %ymm1,%ymm4,%ymm1
   170ce:	c5 d5 d4 c9          	vpaddq %ymm1,%ymm5,%ymm1
   170d2:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   170d8:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   170dc:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   170e1:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   170e5:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   170ea:	48 39 fa             	cmp    %rdi,%rdx
   170ed:	0f 84 89 01 00 00    	je     1727c <topic081_rust_runtime::enumerated+0x2dc>
   170f3:	f6 c2 0c             	test   $0xc,%dl
   170f6:	74 6c                	je     17164 <topic081_rust_runtime::enumerated+0x1c4>
   170f8:	49 89 f9             	mov    %rdi,%r9
   170fb:	49 83 c0 0c          	add    $0xc,%r8
   170ff:	4c 89 c7             	mov    %r8,%rdi
   17102:	48 21 d7             	and    %rdx,%rdi
   17105:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   1710a:	c4 e2 7d 59 15 ed e3 	vpbroadcastq -0x11c13(%rip),%ymm2        # 5500 <__abi_tag+0x5204>
   17111:	fe ff 
   17113:	66 66 66 66 2e 0f 1f 	data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   1711a:	84 00 00 00 00 00 
   17120:	c5 e0 57 db          	vxorps %xmm3,%xmm3,%xmm3
   17124:	62 b2 fd 28 40 1c ce 	vpmullq (%rsi,%r9,8),%ymm0,%ymm3
   1712b:	62 f1 e5 28 72 cb 0d 	vprolq $0xd,%ymm3,%ymm3
   17132:	c5 e5 ef da          	vpxor  %ymm2,%ymm3,%ymm3
   17136:	c5 e5 d4 c9          	vpaddq %ymm1,%ymm3,%ymm1
   1713a:	49 83 c1 04          	add    $0x4,%r9
   1713e:	4c 39 cf             	cmp    %r9,%rdi
   17141:	75 dd                	jne    17120 <topic081_rust_runtime::enumerated+0x180>
   17143:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   17149:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   1714d:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   17152:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17156:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   1715b:	48 39 fa             	cmp    %rdi,%rdx
   1715e:	0f 84 18 01 00 00    	je     1727c <topic081_rust_runtime::enumerated+0x2dc>
   17164:	49 b8 03 ed 92 d1 32 	movabs $0xd1b54a32d192ed03,%r8
   1716b:	4a b5 d1 
   1716e:	66 90                	xchg   %ax,%ax
   17170:	4c 8b 0c fe          	mov    (%rsi,%rdi,8),%r9
   17174:	4c 0f af c9          	imul   %rcx,%r9
   17178:	c4 43 fb f0 c9 33    	rorx   $0x33,%r9,%r9
   1717e:	4d 31 c1             	xor    %r8,%r9
   17181:	4c 01 c8             	add    %r9,%rax
   17184:	48 ff c7             	inc    %rdi
   17187:	48 39 fa             	cmp    %rdi,%rdx
   1718a:	75 e4                	jne    17170 <topic081_rust_runtime::enumerated+0x1d0>
   1718c:	e9 eb 00 00 00       	jmp    1727c <topic081_rust_runtime::enumerated+0x2dc>
   17191:	48 89 d7             	mov    %rdx,%rdi
   17194:	4c 21 c7             	and    %r8,%rdi
   17197:	48 8d 04 d5 00 00 00 	lea    0x0(,%rdx,8),%rax
   1719e:	00 
   1719f:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   171a3:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   171a7:	45 31 c9             	xor    %r9d,%r9d
   171aa:	c5 e9 ef d2          	vpxor  %xmm2,%xmm2,%xmm2
   171ae:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   171b2:	c5 d9 ef e4          	vpxor  %xmm4,%xmm4,%xmm4
   171b6:	66 2e 0f 1f 84 00 00 	cs nopw 0x0(%rax,%rax,1)
   171bd:	00 00 00 
   171c0:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   171c4:	c5 ed d4 d0          	vpaddq %ymm0,%ymm2,%ymm2
   171c8:	c5 e5 d4 d8          	vpaddq %ymm0,%ymm3,%ymm3
   171cc:	c5 dd d4 e0          	vpaddq %ymm0,%ymm4,%ymm4
   171d0:	c4 a1 75 d4 0c 0e    	vpaddq (%rsi,%r9,1),%ymm1,%ymm1
   171d6:	c4 a1 6d d4 54 0e 20 	vpaddq 0x20(%rsi,%r9,1),%ymm2,%ymm2
   171dd:	c4 a1 65 d4 5c 0e 40 	vpaddq 0x40(%rsi,%r9,1),%ymm3,%ymm3
   171e4:	c4 a1 5d d4 64 0e 60 	vpaddq 0x60(%rsi,%r9,1),%ymm4,%ymm4
   171eb:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   171ef:	4c 39 c8             	cmp    %r9,%rax
   171f2:	75 cc                	jne    171c0 <topic081_rust_runtime::enumerated+0x220>
   171f4:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   171f8:	c5 dd d4 d3          	vpaddq %ymm3,%ymm4,%ymm2
   171fc:	c5 ed d4 c9          	vpaddq %ymm1,%ymm2,%ymm1
   17200:	c4 e3 7d 39 ca 01    	vextracti128 $0x1,%ymm1,%xmm2
   17206:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   1720a:	c5 f9 70 d1 ee       	vpshufd $0xee,%xmm1,%xmm2
   1720f:	c5 f1 d4 ca          	vpaddq %xmm2,%xmm1,%xmm1
   17213:	c4 e1 f9 7e c8       	vmovq  %xmm1,%rax
   17218:	48 39 fa             	cmp    %rdi,%rdx
   1721b:	74 5f                	je     1727c <topic081_rust_runtime::enumerated+0x2dc>
   1721d:	f6 c2 0c             	test   $0xc,%dl
   17220:	74 4b                	je     1726d <topic081_rust_runtime::enumerated+0x2cd>
   17222:	49 89 f9             	mov    %rdi,%r9
   17225:	49 83 c0 0c          	add    $0xc,%r8
   17229:	4c 89 c7             	mov    %r8,%rdi
   1722c:	48 21 d7             	and    %rdx,%rdi
   1722f:	c4 e1 f9 6e c8       	vmovq  %rax,%xmm1
   17234:	66 66 66 2e 0f 1f 84 	data16 data16 cs nopw 0x0(%rax,%rax,1)
   1723b:	00 00 00 00 00 
   17240:	c5 f5 d4 c8          	vpaddq %ymm0,%ymm1,%ymm1
   17244:	c4 a1 75 d4 0c ce    	vpaddq (%rsi,%r9,8),%ymm1,%ymm1
   1724a:	49 83 c1 04          	add    $0x4,%r9
   1724e:	4c 39 cf             	cmp    %r9,%rdi
   17251:	75 ed                	jne    17240 <topic081_rust_runtime::enumerated+0x2a0>
   17253:	c4 e3 7d 39 c8 01    	vextracti128 $0x1,%ymm1,%xmm0
   17259:	c5 f1 d4 c0          	vpaddq %xmm0,%xmm1,%xmm0
   1725d:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   17262:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17266:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   1726b:	eb 0a                	jmp    17277 <topic081_rust_runtime::enumerated+0x2d7>
   1726d:	48 01 c8             	add    %rcx,%rax
   17270:	48 03 04 fe          	add    (%rsi,%rdi,8),%rax
   17274:	48 ff c7             	inc    %rdi
   17277:	48 39 fa             	cmp    %rdi,%rdx
   1727a:	75 f1                	jne    1726d <topic081_rust_runtime::enumerated+0x2cd>
   1727c:	c5 f8 77             	vzeroupper
   1727f:	c3                   	ret


0000000000017280 <topic081_rust_runtime::data>:
   17280:	55                   	push   %rbp
   17281:	41 57                	push   %r15
   17283:	41 56                	push   %r14
   17285:	41 55                	push   %r13
   17287:	41 54                	push   %r12
   17289:	53                   	push   %rbx
   1728a:	50                   	push   %rax
   1728b:	49 bf f0 ff ff ff ff 	movabs $0x1ffffffffffffff0,%r15
   17292:	ff ff 1f 
   17295:	49 8d 47 0f          	lea    0xf(%r15),%rax
   17299:	48 39 c6             	cmp    %rax,%rsi
   1729c:	0f 97 c0             	seta   %al
   1729f:	48 8d 1c f5 00 00 00 	lea    0x0(,%rsi,8),%rbx
   172a6:	00 
   172a7:	48 b9 f8 ff ff ff ff 	movabs $0x7ffffffffffffff8,%rcx
   172ae:	ff ff 7f 
   172b1:	48 39 cb             	cmp    %rcx,%rbx
   172b4:	0f 97 c1             	seta   %cl
   172b7:	08 c1                	or     %al,%cl
   172b9:	74 0f                	je     172ca <topic081_rust_runtime::data+0x4a>
   172bb:	45 31 f6             	xor    %r14d,%r14d
   172be:	4c 89 f7             	mov    %r14,%rdi
   172c1:	48 89 de             	mov    %rbx,%rsi
   172c4:	ff 15 76 33 04 00    	call   *0x43376(%rip)        # 5a640 <_DYNAMIC+0x260>
   172ca:	48 85 db             	test   %rbx,%rbx
   172cd:	74 3e                	je     1730d <topic081_rust_runtime::data+0x8d>
   172cf:	49 89 d4             	mov    %rdx,%r12
   172d2:	48 89 f5             	mov    %rsi,%rbp
   172d5:	49 89 fd             	mov    %rdi,%r13
   172d8:	ff 15 6a 33 04 00    	call   *0x4336a(%rip)        # 5a648 <_DYNAMIC+0x268>
   172de:	41 be 08 00 00 00    	mov    $0x8,%r14d
   172e4:	be 08 00 00 00       	mov    $0x8,%esi
   172e9:	48 89 df             	mov    %rbx,%rdi
   172ec:	ff 15 5e 33 04 00    	call   *0x4335e(%rip)        # 5a650 <_DYNAMIC+0x270>
   172f2:	48 85 c0             	test   %rax,%rax
   172f5:	74 c7                	je     172be <topic081_rust_runtime::data+0x3e>
   172f7:	48 89 ee             	mov    %rbp,%rsi
   172fa:	48 89 e9             	mov    %rbp,%rcx
   172fd:	4c 89 ef             	mov    %r13,%rdi
   17300:	4c 89 e2             	mov    %r12,%rdx
   17303:	48 85 f6             	test   %rsi,%rsi
   17306:	75 15                	jne    1731d <topic081_rust_runtime::data+0x9d>
   17308:	e9 52 01 00 00       	jmp    1745f <topic081_rust_runtime::data+0x1df>
   1730d:	b8 08 00 00 00       	mov    $0x8,%eax
   17312:	31 c9                	xor    %ecx,%ecx
   17314:	48 85 f6             	test   %rsi,%rsi
   17317:	0f 84 42 01 00 00    	je     1745f <topic081_rust_runtime::data+0x1df>
   1731d:	48 83 fe 04          	cmp    $0x4,%rsi
   17321:	73 08                	jae    1732b <topic081_rust_runtime::data+0xab>
   17323:	45 31 c0             	xor    %r8d,%r8d
   17326:	e9 fb 00 00 00       	jmp    17426 <topic081_rust_runtime::data+0x1a6>
   1732b:	62 f2 fd 28 7c c2    	vpbroadcastq %rdx,%ymm0
   17331:	48 83 fe 10          	cmp    $0x10,%rsi
   17335:	73 08                	jae    1733f <topic081_rust_runtime::data+0xbf>
   17337:	45 31 c0             	xor    %r8d,%r8d
   1733a:	e9 92 00 00 00       	jmp    173d1 <topic081_rust_runtime::data+0x151>
   1733f:	49 89 f0             	mov    %rsi,%r8
   17342:	4d 21 f8             	and    %r15,%r8
   17345:	62 f1 fd 38 d4 0d c1 	vpaddq -0x11e3f(%rip){1to4},%ymm0,%ymm1        # 5510 <__abi_tag+0x5214>
   1734c:	e1 fe ff 
   1734f:	62 f1 fd 38 d4 15 57 	vpaddq -0x11ea9(%rip){1to4},%ymm0,%ymm2        # 54b0 <__abi_tag+0x51b4>
   17356:	e1 fe ff 
   17359:	62 f1 fd 38 d4 1d 8d 	vpaddq -0x11e73(%rip){1to4},%ymm0,%ymm3        # 54f0 <__abi_tag+0x51f4>
   17360:	e1 fe ff 
   17363:	c5 fd 6f 25 15 f4 fe 	vmovdqa -0x10beb(%rip),%ymm4        # 6780 <__abi_tag+0x6484>
   1736a:	ff 
   1736b:	45 31 c9             	xor    %r9d,%r9d
   1736e:	c4 e2 7d 59 2d 59 e1 	vpbroadcastq -0x11ea7(%rip),%ymm5        # 54d0 <__abi_tag+0x51d4>
   17375:	fe ff 
   17377:	c4 e2 7d 59 35 88 e1 	vpbroadcastq -0x11e78(%rip),%ymm6        # 5508 <__abi_tag+0x520c>
   1737e:	fe ff 
   17380:	c5 c0 57 ff          	vxorps %xmm7,%xmm7,%xmm7
   17384:	62 f2 dd 28 40 fd    	vpmullq %ymm5,%ymm4,%ymm7
   1738a:	c5 45 d4 c0          	vpaddq %ymm0,%ymm7,%ymm8
   1738e:	c5 45 d4 c9          	vpaddq %ymm1,%ymm7,%ymm9
   17392:	c5 45 d4 d2          	vpaddq %ymm2,%ymm7,%ymm10
   17396:	c4 21 7e 7f 04 c8    	vmovdqu %ymm8,(%rax,%r9,8)
   1739c:	c4 21 7e 7f 4c c8 20 	vmovdqu %ymm9,0x20(%rax,%r9,8)
   173a3:	c4 21 7e 7f 54 c8 40 	vmovdqu %ymm10,0x40(%rax,%r9,8)
   173aa:	c5 c5 d4 fb          	vpaddq %ymm3,%ymm7,%ymm7
   173ae:	c4 a1 7e 7f 7c c8 60 	vmovdqu %ymm7,0x60(%rax,%r9,8)
   173b5:	49 83 c1 10          	add    $0x10,%r9
   173b9:	c5 dd d4 e6          	vpaddq %ymm6,%ymm4,%ymm4
   173bd:	4d 39 c8             	cmp    %r9,%r8
   173c0:	75 be                	jne    17380 <topic081_rust_runtime::data+0x100>
   173c2:	4c 39 c6             	cmp    %r8,%rsi
   173c5:	0f 84 94 00 00 00    	je     1745f <topic081_rust_runtime::data+0x1df>
   173cb:	40 f6 c6 0c          	test   $0xc,%sil
   173cf:	74 55                	je     17426 <topic081_rust_runtime::data+0x1a6>
   173d1:	4d 89 c1             	mov    %r8,%r9
   173d4:	49 83 c7 0c          	add    $0xc,%r15
   173d8:	4d 89 f8             	mov    %r15,%r8
   173db:	49 21 f0             	and    %rsi,%r8
   173de:	62 d2 fd 28 7c c9    	vpbroadcastq %r9,%ymm1
   173e4:	c5 f5 eb 0d 94 f3 fe 	vpor   -0x10c6c(%rip),%ymm1,%ymm1        # 6780 <__abi_tag+0x6484>
   173eb:	ff 
   173ec:	c4 e2 7d 59 15 db e0 	vpbroadcastq -0x11f25(%rip),%ymm2        # 54d0 <__abi_tag+0x51d4>
   173f3:	fe ff 
   173f5:	c4 e2 7d 59 1d fa e0 	vpbroadcastq -0x11f06(%rip),%ymm3        # 54f8 <__abi_tag+0x51fc>
   173fc:	fe ff 
   173fe:	66 90                	xchg   %ax,%ax
   17400:	c5 d8 57 e4          	vxorps %xmm4,%xmm4,%xmm4
   17404:	62 f2 f5 28 40 e2    	vpmullq %ymm2,%ymm1,%ymm4
   1740a:	c5 dd d4 e0          	vpaddq %ymm0,%ymm4,%ymm4
   1740e:	c4 a1 7e 7f 24 c8    	vmovdqu %ymm4,(%rax,%r9,8)
   17414:	49 83 c1 04          	add    $0x4,%r9
   17418:	c5 f5 d4 cb          	vpaddq %ymm3,%ymm1,%ymm1
   1741c:	4d 39 c8             	cmp    %r9,%r8
   1741f:	75 df                	jne    17400 <topic081_rust_runtime::data+0x180>
   17421:	4c 39 c6             	cmp    %r8,%rsi
   17424:	74 39                	je     1745f <topic081_rust_runtime::data+0x1df>
   17426:	49 b9 eb 83 b5 80 46 	movabs $0x61c8864680b583eb,%r9
   1742d:	86 c8 61 
   17430:	4d 0f af c8          	imul   %r8,%r9
   17434:	4c 29 ca             	sub    %r9,%rdx
   17437:	49 b9 15 7c 4a 7f b9 	movabs $0x9e3779b97f4a7c15,%r9
   1743e:	79 37 9e 
   17441:	66 66 66 66 66 66 2e 	data16 data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   17448:	0f 1f 84 00 00 00 00 
   1744f:	00 
   17450:	4a 89 14 c0          	mov    %rdx,(%rax,%r8,8)
   17454:	49 ff c0             	inc    %r8
   17457:	4c 01 ca             	add    %r9,%rdx
   1745a:	4c 39 c6             	cmp    %r8,%rsi
   1745d:	75 f1                	jne    17450 <topic081_rust_runtime::data+0x1d0>
   1745f:	48 89 0f             	mov    %rcx,(%rdi)
   17462:	48 89 47 08          	mov    %rax,0x8(%rdi)
   17466:	48 89 77 10          	mov    %rsi,0x10(%rdi)
   1746a:	48 89 f8             	mov    %rdi,%rax
   1746d:	48 83 c4 08          	add    $0x8,%rsp
   17471:	5b                   	pop    %rbx
   17472:	41 5c                	pop    %r12
   17474:	41 5d                	pop    %r13
   17476:	41 5e                	pop    %r14
   17478:	41 5f                	pop    %r15
   1747a:	5d                   	pop    %rbp
   1747b:	c5 f8 77             	vzeroupper
   1747e:	c3                   	ret
   1747f:	cc                   	int3


0000000000017480 <topic081_rust_runtime::dot_zip>:
   17480:	48 83 ec 18          	sub    $0x18,%rsp
   17484:	48 89 74 24 08       	mov    %rsi,0x8(%rsp)
   17489:	48 89 4c 24 10       	mov    %rcx,0x10(%rsp)
   1748e:	48 39 ce             	cmp    %rcx,%rsi
   17491:	0f 85 2d 01 00 00    	jne    175c4 <topic081_rust_runtime::dot_zip+0x144>
   17497:	48 85 f6             	test   %rsi,%rsi
   1749a:	74 0f                	je     174ab <topic081_rust_runtime::dot_zip+0x2b>
   1749c:	48 83 fe 04          	cmp    $0x4,%rsi
   174a0:	73 10                	jae    174b2 <topic081_rust_runtime::dot_zip+0x32>
   174a2:	31 c0                	xor    %eax,%eax
   174a4:	31 c9                	xor    %ecx,%ecx
   174a6:	e9 34 01 00 00       	jmp    175df <topic081_rust_runtime::dot_zip+0x15f>
   174ab:	31 c0                	xor    %eax,%eax
   174ad:	48 83 c4 18          	add    $0x18,%rsp
   174b1:	c3                   	ret
   174b2:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   174b9:	ff ff 0f 
   174bc:	48 83 fe 10          	cmp    $0x10,%rsi
   174c0:	73 09                	jae    174cb <topic081_rust_runtime::dot_zip+0x4b>
   174c2:	31 c9                	xor    %ecx,%ecx
   174c4:	31 c0                	xor    %eax,%eax
   174c6:	e9 ab 00 00 00       	jmp    17576 <topic081_rust_runtime::dot_zip+0xf6>
   174cb:	48 89 f1             	mov    %rsi,%rcx
   174ce:	4c 21 c1             	and    %r8,%rcx
   174d1:	48 8d 04 f5 00 00 00 	lea    0x0(,%rsi,8),%rax
   174d8:	00 
   174d9:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   174dd:	c5 f9 ef c0          	vpxor  %xmm0,%xmm0,%xmm0
   174e1:	45 31 c9             	xor    %r9d,%r9d
   174e4:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   174e8:	c5 e9 ef d2          	vpxor  %xmm2,%xmm2,%xmm2
   174ec:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   174f0:	c4 a1 7e 6f 24 0a    	vmovdqu (%rdx,%r9,1),%ymm4
   174f6:	62 b2 dd 28 40 24 0f 	vpmullq (%rdi,%r9,1),%ymm4,%ymm4
   174fd:	c4 a1 7e 6f 6c 0a 20 	vmovdqu 0x20(%rdx,%r9,1),%ymm5
   17504:	62 b2 d5 28 40 6c 0f 	vpmullq 0x20(%rdi,%r9,1),%ymm5,%ymm5
   1750b:	01 
   1750c:	c4 a1 7e 6f 74 0a 40 	vmovdqu 0x40(%rdx,%r9,1),%ymm6
   17513:	62 b2 cd 28 40 74 0f 	vpmullq 0x40(%rdi,%r9,1),%ymm6,%ymm6
   1751a:	02 
   1751b:	c4 a1 7e 6f 7c 0a 60 	vmovdqu 0x60(%rdx,%r9,1),%ymm7
   17522:	62 b2 c5 28 40 7c 0f 	vpmullq 0x60(%rdi,%r9,1),%ymm7,%ymm7
   17529:	03 
   1752a:	c5 dd d4 c0          	vpaddq %ymm0,%ymm4,%ymm0
   1752e:	c5 d5 d4 c9          	vpaddq %ymm1,%ymm5,%ymm1
   17532:	c5 cd d4 d2          	vpaddq %ymm2,%ymm6,%ymm2
   17536:	c5 c5 d4 db          	vpaddq %ymm3,%ymm7,%ymm3
   1753a:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   1753e:	4c 39 c8             	cmp    %r9,%rax
   17541:	75 ad                	jne    174f0 <topic081_rust_runtime::dot_zip+0x70>
   17543:	c5 f5 d4 c0          	vpaddq %ymm0,%ymm1,%ymm0
   17547:	c5 ed d4 c0          	vpaddq %ymm0,%ymm2,%ymm0
   1754b:	c5 e5 d4 c0          	vpaddq %ymm0,%ymm3,%ymm0
   1754f:	c4 e3 7d 39 c1 01    	vextracti128 $0x1,%ymm0,%xmm1
   17555:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17559:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   1755e:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17562:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   17567:	48 39 ce             	cmp    %rcx,%rsi
   1756a:	0f 84 83 00 00 00    	je     175f3 <topic081_rust_runtime::dot_zip+0x173>
   17570:	40 f6 c6 0c          	test   $0xc,%sil
   17574:	74 69                	je     175df <topic081_rust_runtime::dot_zip+0x15f>
   17576:	49 89 c9             	mov    %rcx,%r9
   17579:	49 83 c0 0c          	add    $0xc,%r8
   1757d:	4c 89 c1             	mov    %r8,%rcx
   17580:	48 21 f1             	and    %rsi,%rcx
   17583:	c4 e1 f9 6e c0       	vmovq  %rax,%xmm0
   17588:	0f 1f 84 00 00 00 00 	nopl   0x0(%rax,%rax,1)
   1758f:	00 
   17590:	c4 a1 7e 6f 0c ca    	vmovdqu (%rdx,%r9,8),%ymm1
   17596:	62 b2 f5 28 40 0c cf 	vpmullq (%rdi,%r9,8),%ymm1,%ymm1
   1759d:	c5 f5 d4 c0          	vpaddq %ymm0,%ymm1,%ymm0
   175a1:	49 83 c1 04          	add    $0x4,%r9
   175a5:	4c 39 c9             	cmp    %r9,%rcx
   175a8:	75 e6                	jne    17590 <topic081_rust_runtime::dot_zip+0x110>
   175aa:	c4 e3 7d 39 c1 01    	vextracti128 $0x1,%ymm0,%xmm1
   175b0:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   175b4:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   175b9:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   175bd:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   175c2:	eb 2a                	jmp    175ee <topic081_rust_runtime::dot_zip+0x16e>
   175c4:	4c 8d 0d 15 0f 04 00 	lea    0x40f15(%rip),%r9        # 584e0 <__dso_handle+0x170>
   175cb:	48 8d 74 24 08       	lea    0x8(%rsp),%rsi
   175d0:	48 8d 54 24 10       	lea    0x10(%rsp),%rdx
   175d5:	31 ff                	xor    %edi,%edi
   175d7:	31 c9                	xor    %ecx,%ecx
   175d9:	ff 15 f1 30 04 00    	call   *0x430f1(%rip)        # 5a6d0 <_DYNAMIC+0x2f0>
   175df:	4c 8b 04 ca          	mov    (%rdx,%rcx,8),%r8
   175e3:	4c 0f af 04 cf       	imul   (%rdi,%rcx,8),%r8
   175e8:	48 ff c1             	inc    %rcx
   175eb:	4c 01 c0             	add    %r8,%rax
   175ee:	48 39 ce             	cmp    %rcx,%rsi
   175f1:	75 ec                	jne    175df <topic081_rust_runtime::dot_zip+0x15f>
   175f3:	48 83 c4 18          	add    $0x18,%rsp
   175f7:	c5 f8 77             	vzeroupper
   175fa:	c3                   	ret
   175fb:	cc                   	int3
   175fc:	cc                   	int3
   175fd:	cc                   	int3
   175fe:	cc                   	int3
   175ff:	cc                   	int3


0000000000017600 <topic081_rust_runtime::dyn_item>:
   17600:	55                   	push   %rbp
   17601:	41 57                	push   %r15
   17603:	41 56                	push   %r14
   17605:	41 55                	push   %r13
   17607:	41 54                	push   %r12
   17609:	53                   	push   %rbx
   1760a:	50                   	push   %rax
   1760b:	48 85 c9             	test   %rcx,%rcx
   1760e:	74 37                	je     17647 <topic081_rust_runtime::dyn_item+0x47>
   17610:	48 89 cb             	mov    %rcx,%rbx
   17613:	49 89 d6             	mov    %rdx,%r14
   17616:	49 89 ff             	mov    %rdi,%r15
   17619:	4c 8b 6e 18          	mov    0x18(%rsi),%r13
   1761d:	31 ed                	xor    %ebp,%ebp
   1761f:	45 31 e4             	xor    %r12d,%r12d
   17622:	66 66 66 66 66 2e 0f 	data16 data16 data16 data16 cs nopw 0x0(%rax,%rax,1)
   17629:	1f 84 00 00 00 00 00 
   17630:	49 8b 34 ee          	mov    (%r14,%rbp,8),%rsi
   17634:	4c 89 ff             	mov    %r15,%rdi
   17637:	41 ff d5             	call   *%r13
   1763a:	49 01 c4             	add    %rax,%r12
   1763d:	48 ff c5             	inc    %rbp
   17640:	48 39 eb             	cmp    %rbp,%rbx
   17643:	75 eb                	jne    17630 <topic081_rust_runtime::dyn_item+0x30>
   17645:	eb 03                	jmp    1764a <topic081_rust_runtime::dyn_item+0x4a>
   17647:	45 31 e4             	xor    %r12d,%r12d
   1764a:	4c 89 e0             	mov    %r12,%rax
   1764d:	48 83 c4 08          	add    $0x8,%rsp
   17651:	5b                   	pop    %rbx
   17652:	41 5c                	pop    %r12
   17654:	41 5d                	pop    %r13
   17656:	41 5e                	pop    %r14
   17658:	41 5f                	pop    %r15
   1765a:	5d                   	pop    %rbp
   1765b:	c3                   	ret
   1765c:	cc                   	int3
   1765d:	cc                   	int3
   1765e:	cc                   	int3
   1765f:	cc                   	int3


0000000000017660 <topic081_rust_runtime::dot_index>:
   17660:	48 83 ec 18          	sub    $0x18,%rsp
   17664:	48 89 74 24 08       	mov    %rsi,0x8(%rsp)
   17669:	48 89 4c 24 10       	mov    %rcx,0x10(%rsp)
   1766e:	48 39 ce             	cmp    %rcx,%rsi
   17671:	0f 85 2d 01 00 00    	jne    177a4 <topic081_rust_runtime::dot_index+0x144>
   17677:	48 85 f6             	test   %rsi,%rsi
   1767a:	74 0f                	je     1768b <topic081_rust_runtime::dot_index+0x2b>
   1767c:	48 83 fe 03          	cmp    $0x3,%rsi
   17680:	77 10                	ja     17692 <topic081_rust_runtime::dot_index+0x32>
   17682:	31 c0                	xor    %eax,%eax
   17684:	31 c9                	xor    %ecx,%ecx
   17686:	e9 34 01 00 00       	jmp    177bf <topic081_rust_runtime::dot_index+0x15f>
   1768b:	31 c0                	xor    %eax,%eax
   1768d:	48 83 c4 18          	add    $0x18,%rsp
   17691:	c3                   	ret
   17692:	49 b8 f0 ff ff ff ff 	movabs $0xffffffffffffff0,%r8
   17699:	ff ff 0f 
   1769c:	48 83 fe 10          	cmp    $0x10,%rsi
   176a0:	73 09                	jae    176ab <topic081_rust_runtime::dot_index+0x4b>
   176a2:	31 c9                	xor    %ecx,%ecx
   176a4:	31 c0                	xor    %eax,%eax
   176a6:	e9 ab 00 00 00       	jmp    17756 <topic081_rust_runtime::dot_index+0xf6>
   176ab:	48 89 f1             	mov    %rsi,%rcx
   176ae:	4c 21 c1             	and    %r8,%rcx
   176b1:	48 8d 04 f5 00 00 00 	lea    0x0(,%rsi,8),%rax
   176b8:	00 
   176b9:	48 83 e0 80          	and    $0xffffffffffffff80,%rax
   176bd:	c5 f9 ef c0          	vpxor  %xmm0,%xmm0,%xmm0
   176c1:	45 31 c9             	xor    %r9d,%r9d
   176c4:	c5 f1 ef c9          	vpxor  %xmm1,%xmm1,%xmm1
   176c8:	c5 e9 ef d2          	vpxor  %xmm2,%xmm2,%xmm2
   176cc:	c5 e1 ef db          	vpxor  %xmm3,%xmm3,%xmm3
   176d0:	c4 a1 7e 6f 24 0a    	vmovdqu (%rdx,%r9,1),%ymm4
   176d6:	62 b2 dd 28 40 24 0f 	vpmullq (%rdi,%r9,1),%ymm4,%ymm4
   176dd:	c4 a1 7e 6f 6c 0a 20 	vmovdqu 0x20(%rdx,%r9,1),%ymm5
   176e4:	62 b2 d5 28 40 6c 0f 	vpmullq 0x20(%rdi,%r9,1),%ymm5,%ymm5
   176eb:	01 
   176ec:	c4 a1 7e 6f 74 0a 40 	vmovdqu 0x40(%rdx,%r9,1),%ymm6
   176f3:	62 b2 cd 28 40 74 0f 	vpmullq 0x40(%rdi,%r9,1),%ymm6,%ymm6
   176fa:	02 
   176fb:	c4 a1 7e 6f 7c 0a 60 	vmovdqu 0x60(%rdx,%r9,1),%ymm7
   17702:	62 b2 c5 28 40 7c 0f 	vpmullq 0x60(%rdi,%r9,1),%ymm7,%ymm7
   17709:	03 
   1770a:	c5 dd d4 c0          	vpaddq %ymm0,%ymm4,%ymm0
   1770e:	c5 d5 d4 c9          	vpaddq %ymm1,%ymm5,%ymm1
   17712:	c5 cd d4 d2          	vpaddq %ymm2,%ymm6,%ymm2
   17716:	c5 c5 d4 db          	vpaddq %ymm3,%ymm7,%ymm3
   1771a:	49 83 e9 80          	sub    $0xffffffffffffff80,%r9
   1771e:	4c 39 c8             	cmp    %r9,%rax
   17721:	75 ad                	jne    176d0 <topic081_rust_runtime::dot_index+0x70>
   17723:	c5 f5 d4 c0          	vpaddq %ymm0,%ymm1,%ymm0
   17727:	c5 ed d4 c0          	vpaddq %ymm0,%ymm2,%ymm0
   1772b:	c5 e5 d4 c0          	vpaddq %ymm0,%ymm3,%ymm0
   1772f:	c4 e3 7d 39 c1 01    	vextracti128 $0x1,%ymm0,%xmm1
   17735:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17739:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   1773e:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17742:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   17747:	48 39 ce             	cmp    %rcx,%rsi
   1774a:	0f 84 83 00 00 00    	je     177d3 <topic081_rust_runtime::dot_index+0x173>
   17750:	40 f6 c6 0c          	test   $0xc,%sil
   17754:	74 69                	je     177bf <topic081_rust_runtime::dot_index+0x15f>
   17756:	49 89 c9             	mov    %rcx,%r9
   17759:	49 83 c0 0c          	add    $0xc,%r8
   1775d:	4c 89 c1             	mov    %r8,%rcx
   17760:	48 21 f1             	and    %rsi,%rcx
   17763:	c4 e1 f9 6e c0       	vmovq  %rax,%xmm0
   17768:	0f 1f 84 00 00 00 00 	nopl   0x0(%rax,%rax,1)
   1776f:	00 
   17770:	c4 a1 7e 6f 0c ca    	vmovdqu (%rdx,%r9,8),%ymm1
   17776:	62 b2 f5 28 40 0c cf 	vpmullq (%rdi,%r9,8),%ymm1,%ymm1
   1777d:	c5 f5 d4 c0          	vpaddq %ymm0,%ymm1,%ymm0
   17781:	49 83 c1 04          	add    $0x4,%r9
   17785:	4c 39 c9             	cmp    %r9,%rcx
   17788:	75 e6                	jne    17770 <topic081_rust_runtime::dot_index+0x110>
   1778a:	c4 e3 7d 39 c1 01    	vextracti128 $0x1,%ymm0,%xmm1
   17790:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   17794:	c5 f9 70 c8 ee       	vpshufd $0xee,%xmm0,%xmm1
   17799:	c5 f9 d4 c1          	vpaddq %xmm1,%xmm0,%xmm0
   1779d:	c4 e1 f9 7e c0       	vmovq  %xmm0,%rax
   177a2:	eb 2a                	jmp    177ce <topic081_rust_runtime::dot_index+0x16e>
   177a4:	4c 8d 0d 4d 0d 04 00 	lea    0x40d4d(%rip),%r9        # 584f8 <__dso_handle+0x188>
   177ab:	48 8d 74 24 08       	lea    0x8(%rsp),%rsi
   177b0:	48 8d 54 24 10       	lea    0x10(%rsp),%rdx
   177b5:	31 ff                	xor    %edi,%edi
   177b7:	31 c9                	xor    %ecx,%ecx
   177b9:	ff 15 11 2f 04 00    	call   *0x42f11(%rip)        # 5a6d0 <_DYNAMIC+0x2f0>
   177bf:	4c 8b 04 ca          	mov    (%rdx,%rcx,8),%r8
   177c3:	4c 0f af 04 cf       	imul   (%rdi,%rcx,8),%r8
   177c8:	48 ff c1             	inc    %rcx
   177cb:	4c 01 c0             	add    %r8,%rax
   177ce:	48 39 ce             	cmp    %rcx,%rsi
   177d1:	75 ec                	jne    177bf <topic081_rust_runtime::dot_index+0x15f>
   177d3:	48 83 c4 18          	add    $0x18,%rsp
   177d7:	c5 f8 77             	vzeroupper
   177da:	c3                   	ret
   177db:	cc                   	int3
   177dc:	cc                   	int3
   177dd:	cc                   	int3
   177de:	cc                   	int3
   177df:	cc                   	int3


00000000000177e0 <topic081_rust_runtime::dyn_batch>:
   177e0:	48 8b 46 20          	mov    0x20(%rsi),%rax
   177e4:	48 89 d6             	mov    %rdx,%rsi
   177e7:	48 89 ca             	mov    %rcx,%rdx
   177ea:	ff e0                	jmp    *%rax
   177ec:	cc                   	int3
   177ed:	cc                   	int3
   177ee:	cc                   	int3
   177ef:	cc                   	int3

