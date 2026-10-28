EMPTY, DELETED = object(), object()
slots = [EMPTY] * 8

def find(key):
    for step in range(len(slots)):
        i = (key + step) % len(slots)
        item = slots[i]
        if item is EMPTY:
            return None
        if item is not DELETED and item[0] == key:
            return item[1]
    return None

def put(key, value):
    first_deleted = None
    for step in range(len(slots)):
        i = (key + step) % len(slots)
        item = slots[i]
        if item is DELETED:
            if first_deleted is None:
                first_deleted = i
        elif item is EMPTY:
            target = i if first_deleted is None else first_deleted
            slots[target] = (key, value)
            return
        elif item[0] == key:
            slots[i] = (key, value)
            return
    if first_deleted is not None:
        slots[first_deleted] = (key, value)
        return
    raise OverflowError("table full")

for key in (1, 9, 17):
    put(key, key * 10)
slots[1] = DELETED
assert find(17) == 170
put(17, 999)
assert sum(isinstance(x, tuple) and x[0] == 17 for x in slots) == 1
assert find(17) == 999
print("tombstone: found 999; duplicate count: 1")
slots[1] = EMPTY
assert find(17) is None
print("incorrect empty deletion: false miss reproduced")
