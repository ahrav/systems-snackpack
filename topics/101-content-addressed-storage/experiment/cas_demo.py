from hashlib import sha256

objects = {}

def put(data):
    key = sha256(b"chunk-v1\0" + data).digest()
    if key in objects and objects[key] != data:
        raise ValueError("content collision")
    objects[key] = data
    return key

def snapshot(data):
    return [put(data[i:i+4]) for i in range(0, len(data), 4)]

def restore(manifest):
    chunks = []
    for key in manifest:
        data = objects[key]
        if sha256(b"chunk-v1\0" + data).digest() != key:
            raise ValueError("corrupt chunk")
        chunks.append(data)
    return b"".join(chunks)

a = snapshot(b"AAAABBBBCCCC")
b = snapshot(b"AAAAXXXXBBBBCCCC")
assert restore(a) == b"AAAABBBBCCCC"
assert restore(b) == b"AAAAXXXXBBBBCCCC"
print("logical bytes:", 12 + 16)
print("unique payload bytes:", sum(map(len, objects.values())))
print("manifest references:", len(a) + len(b))
