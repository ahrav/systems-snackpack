end, lateness = 10, 5
frontier = -1
total = 0
present = False
fired = False


def event(timestamp, amount):
    global total, present, fired
    assert 0 <= timestamp < end
    if frontier >= end + lateness:
        print("late", timestamp, amount)
        return
    total += amount
    present = True
    if frontier >= end:
        fired = True
        print("upsert", total)


def advance(value):
    global frontier, total, present, fired
    assert value >= frontier
    frontier = value
    if present and not fired and frontier >= end:
        fired = True
        print("upsert", total)
    if frontier >= end + lateness:
        total, present, fired = 0, False, False


event(2, 5)
event(7, 7)
advance(10)
event(8, 3)
advance(15)
event(9, 4)
