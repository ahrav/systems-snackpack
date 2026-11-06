from collections import Counter

a = Counter({7: 2})
b = Counter({7: 3})
da = Counter({7: 1})
db = Counter({7: -1})
keys = set(da) | set(db)
delta = sum(da[k]*b[k] + a[k]*db[k] + da[k]*db[k] for k in keys)
before = sum(a[k]*b[k] for k in a)
a.update(da)
b.update(db)
assert all(v >= 0 for v in a.values())
assert all(v >= 0 for v in b.values())
after = sum(a[k]*b[k] for k in a)
assert before + delta == after == 6
print(before, delta, after)
