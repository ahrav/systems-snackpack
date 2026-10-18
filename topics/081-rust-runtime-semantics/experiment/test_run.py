"""Focused tests for the Topic 81 runner's metadata helpers."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run


class SourceHashes(unittest.TestCase):
    def test_output_tree_inside_topic_is_not_a_source(self):
        out = run.P / 'out-under-test'
        out.mkdir()
        try:
            (out / 'runtime').write_bytes(b'not a source file')
            recorded = run.source_hashes(out)
        finally:
            (out / 'runtime').unlink()
            out.rmdir()
        self.assertNotIn('out-under-test/runtime', recorded)
        self.assertNotIn('measurements/SHA256SUMS', recorded)
        self.assertFalse([p for p in recorded if '__pycache__' in p], recorded)
        self.assertIn('src/lib.rs', recorded)
        self.assertIn('experiment/run.py', recorded)


if __name__ == '__main__':
    unittest.main()
