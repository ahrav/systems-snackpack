"""Single-process in-memory CAS with quiescent mark/sweep."""
from hashlib import sha256
import struct
import subprocess
import sys
if sys.flags.optimize:
    raise SystemExit('validation uses assert: run without python -O or PYTHONOPTIMIZE')


def digest(data):
    return sha256(data).digest()


class Store:
    def __init__(self, hasher=digest):
        self.objects = {}
        self.roots = {}
        self.hasher = hasher

    def put(self, kind, data):
        encoded = kind + b"\0" + data
        key = self.hasher(encoded)
        if key in self.objects and self.objects[key] != encoded:
            raise ValueError("collision")
        self.objects[key] = encoded
        return key

    def get(self, kind, key):
        encoded = self.objects[key]
        prefix = kind + b"\0"
        if self.hasher(encoded) != key or not encoded.startswith(prefix):
            raise ValueError("corruption or wrong object type")
        return encoded[len(prefix):]

    def publish(self, name, chunks):
        ids = [self.put(b"chunk-v1", chunk) for chunk in chunks]
        manifest = struct.pack("<Q", len(ids)) + b"".join(ids)
        root = self.put(b"manifest-v1", manifest)
        self.roots[name] = root
        return root

    def refs(self, root):
        manifest = self.get(b"manifest-v1", root)
        if len(manifest) < 8:
            raise ValueError("short manifest")
        count, = struct.unpack("<Q", manifest[:8])
        if len(manifest) != 8 + 32 * count:
            raise ValueError("manifest length")
        return [manifest[i:i+32] for i in range(8, len(manifest), 32)]

    def restore(self, root):
        return b"".join(self.get(b"chunk-v1", key) for key in self.refs(root))

    def collect(self):
        live = set(self.roots.values())
        for root in self.roots.values():
            live.update(self.refs(root))
        self.objects = {k: v for k, v in self.objects.items() if k in live}


def chunks(binary, mode, data):
    text = subprocess.check_output([binary, mode], input=data).decode().strip()
    ends = list(map(int, text.split(","))) if text else []
    assert (ends[-1] if ends else 0) == len(data)
    assert all(a < b for a, b in zip([0] + ends, ends))
    return [data[a:b] for a, b in zip([0] + ends, ends)]
