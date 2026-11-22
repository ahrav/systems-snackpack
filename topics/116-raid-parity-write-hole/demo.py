"""One member write reaches durable storage before power loss."""
old_a, b, new_a = 0x3c, 0x55, 0xa6
old_p = old_a ^ b
new_p = old_p ^ old_a ^ new_a
journal = (new_a, new_p)
a, p = new_a, old_p
print(f"stale rebuild: {a ^ p:02x}")
a, p = journal
print(f"after replay:  {a ^ p:02x}")
assert a ^ p == b
