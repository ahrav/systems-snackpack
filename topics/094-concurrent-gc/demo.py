def collect(mode):
    heap = [None, 2, None]  # roots A=0, B=1; B points to C=2
    marked, pending = {0, 1}, [1, 0]
    def shade(obj):
        if obj is not None and obj not in marked:
            marked.add(obj)
            pending.append(obj)
    def scan():
        shade(heap[pending.pop()])
    def store(owner, new):
        if mode == 'satb':
            shade(heap[owner])  # preserve overwritten edge
        if mode == 'insertion':
            shade(new)          # preserve inserted edge
        heap[owner] = new
    scan()                      # A is now fully scanned
    store(0, 2)                 # attach C to A
    store(1, None)              # detach C from B
    while pending:
        scan()
    return sorted(marked)

for mode in ('none', 'insertion', 'satb'):
    print(mode, collect(mode))
assert collect('none') == [0, 1]
assert collect('insertion') == collect('satb') == [0, 1, 2]
