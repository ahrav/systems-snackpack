"""Known answers from fsverity-utils and read outcomes from an independent range oracle."""
import unittest
from verity import BLOCK, FANOUT, Reader, build, file_digest

# programs/test_compute_digest.c, revision 36660d79c9ddbc4d560d9a496b6b67c1c25dcd13.
VECTORS = {
    0: "3d248ca542a24fc62d1c43b916eae5016878e2533c88238480b26128a1f1af95",
    1: "b803429503d95915829b29fdbc8bbad142f3abfd11b1cadf5526582e685c0551",
    4096: "6ac39979016e3ddf3d39fff6cb984f7c118acdf1852919f5c100c4b142c1818e",
    100000: "f2096a36c5cdca4fa33ee8852833150bb324992e5417a9d571f1bffff73b9efc",
    1000000: "48df0c462329cd879661bd05b39aa81b05cc16afd27a7196a559da83531d39d9",
}


def flip(data, offset=0):
    return data[:offset] + bytes([data[offset] ^ 1]) + data[offset + 1:]


class Integrity(unittest.TestCase):
    def test_upstream_answers(self):
        data = bytes((i % 11 + i % 439 + i % 1103) % 256 for i in range(max(VECTORS)))
        for size, expected in VECTORS.items():
            levels, root = build(data[:size])
            reader = Reader(data[:size], levels, root, bytes.fromhex(expected))
            for start in range(0, size, BLOCK):
                self.assertEqual(reader.read(start // BLOCK), data[start:min(start + BLOCK, size)])
            with self.assertRaises(IndexError):
                reader.read((size + BLOCK - 1) // BLOCK)

    def test_hash_block_fault_domains(self):
        # Four leaf groups, the last partial. The range oracle predicts which reads fail.
        count = 3 * FANOUT + 7
        data = b"".join(i.to_bytes(4, "little") + bytes(BLOCK - 4) for i in range(count))
        levels, root = build(data)
        trusted = file_digest(len(data), root)
        for level, blocks in enumerate(levels):
            for bad in range(len(blocks)):
                changed = list(levels)
                changed[level] = blocks[:bad] + (flip(blocks[bad]),) + blocks[bad + 1:]
                reader = Reader(data, changed, root, trusted)
                width = FANOUT ** (level + 1)
                for index in range(count):
                    if bad * width <= index < (bad + 1) * width:
                        with self.assertRaisesRegex(ValueError, "hash block mismatch"):
                            reader.read(index)
                    else:
                        self.assertEqual(reader.read(index), data[index * BLOCK:(index + 1) * BLOCK])

    def test_requested_data_and_file_identity(self):
        data = b"A" * BLOCK + b"tail"
        levels, root = build(data)
        trusted = file_digest(len(data), root)
        reader = Reader(flip(data, BLOCK), levels, root, trusted)
        self.assertEqual(reader.read(0), data[:BLOCK])
        with self.assertRaisesRegex(ValueError, "data block mismatch"):
            reader.read(1)
        for changed in (data + b"\0", b"B" * len(data)):
            replacement, other_root = build(changed)
            with self.assertRaisesRegex(ValueError, "file digest mismatch"):
                Reader(changed, replacement, other_root, trusted)
        with self.assertRaises(IndexError):
            reader.read(-1)
        self.assertEqual(build(data + b"\0")[1], root)


if __name__ == "__main__":
    unittest.main()
