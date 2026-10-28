from collections import OrderedDict, Counter


def replay(trace, policy, capacity=3):
    cache, count, hits = OrderedDict(), Counter(), 0
    for key in trace:
        count[key] += 1  # Include misses and rejected candidates.
        if key in cache:
            hits += 1
            if policy != 'fifo':
                cache.move_to_end(key)
        elif capacity:
            if len(cache) == capacity:
                victim = next(iter(cache))
                if policy == 'frequency' and count[key] <= count[victim]:
                    continue  # Retain the resident on a frequency tie.
                cache.popitem(last=False)
            cache[key] = None
    return hits, ''.join(cache)


if __name__ == '__main__':
    scan = list('ABC' * 4 + 'xyzuv' + 'ABC' * 2)
    shift = scan + list('DEF' * 3)
    for name, trace in [('scan', scan), ('shift', shift)]:
        for policy in ['fifo', 'lru', 'frequency']:
            print(name, policy, len(trace), *replay(trace, policy))
