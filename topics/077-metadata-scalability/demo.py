"""Single epoch, dense sequence; a tiny executable model, not an etcd client."""
def apply(cache, cursor, start, end, changes):
    if end < start or end - start != len(changes):
        raise ValueError('malformed batch')
    if any(not 0 <= key < len(cache) for key, _ in changes):
        raise ValueError('invalid key')
    if start > cursor:
        raise ValueError('gap: fetch missing history or a snapshot')
    if end <= cursor:
        return cursor
    for key, value in changes[cursor - start:]:
        cache[key] = value  # None deletes the route.
    return end

cache, cursor = [10, 20], 0
cursor = apply(cache, cursor, 0, 2, [(0, 11), (1, None)])
assert (cache, cursor) == ([11, None], 2)
cursor = apply(cache, cursor, 0, 1, [(0, 11)])  # Old replay.
assert (cache, cursor) == ([11, None], 2)
before = cache.copy()
try:
    apply(cache, cursor, 3, 4, [(1, 99)])
except ValueError:
    pass
else:
    raise AssertionError('gap accepted')
assert cache == before
# A complete snapshot replaces the cache, including absent keys.
cache, cursor = [None, 99], 4
cursor = apply(cache, cursor, 4, 5, [(0, 12)])
assert (cache, cursor) == ([12, 99], 5)
print('replay, deletion, gap rejection, and resnapshot: OK')
