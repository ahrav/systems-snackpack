def recover(a, b, active, undo):
    if active:
        a, b = undo
    assert a >= 0 and b >= 0 and a + b == 100
    return a, b

states = [(60, 40, False), (60, 40, False), (60, 40, True),
          (50, 40, True), (50, 50, True), (50, 50, False)]
for point, state in enumerate(states):
    result = recover(*state, undo=(60, 40))
    expected = (50, 50) if point == 5 else (60, 40)
    assert result == expected
    print(point, result)
assert recover(60, 40, True, (60, 40)) == (60, 40)
print("PASS: six crash points and repeated recovery")
