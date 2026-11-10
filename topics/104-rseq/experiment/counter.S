/* SPDX-License-Identifier: MIT
 * One aligned store commits. All tentative state stays in registers.
 * Arguments: registered ABI area, CPU slot, expected CPU, stress delay.
 */
#if defined(__x86_64__)
.text
.globl rseq_add
.type rseq_add,@function
rseq_add:
    leaq descriptor(%rip), %rax
    movq %rax, 8(%rdi)
start:
    cmpl %edx, 4(%rdi)
    jne abort
    movq (%rsi), %rax
    addq $1, %rax
    testl %ecx, %ecx
    jz commit
wait_loop:
    decl %ecx
    jnz wait_loop
commit:
    movq %rax, (%rsi)
post_commit:
    movq $0, 8(%rdi)
    xorl %eax, %eax
    ret
    .byte 0x0f, 0xb9, 0x3d
    .long 0x53053053
abort:
    movq $0, 8(%rdi)
    movl $-1, %eax
    ret
.size rseq_add, .-rseq_add
#elif defined(__aarch64__) && !defined(__AARCH64EB__)
.text
.globl rseq_add
.type rseq_add,%function
rseq_add:
    adrp x4, descriptor
    add x4, x4, :lo12:descriptor
    str x4, [x0, #8]
start:
    ldr w4, [x0, #4]
    cmp w4, w2
    b.ne abort
    ldr x4, [x1]
    add x4, x4, #1
    cbz w3, commit
wait_loop:
    subs w3, w3, #1
    b.ne wait_loop
commit:
    str x4, [x1]
post_commit:
    str xzr, [x0, #8]
    mov w0, #0
    ret
    .inst 0xd428bc00
abort:
    str xzr, [x0, #8]
    mov w0, #-1
    ret
.size rseq_add, .-rseq_add
#else
#error Supported targets: Linux x86-64 and little-endian AArch64
#endif
.pushsection __rseq_cs,"aw"
.balign 32
descriptor:
    .long 0, 0
    .quad start, post_commit-start, abort
.popsection
.section .note.GNU-stack,""
