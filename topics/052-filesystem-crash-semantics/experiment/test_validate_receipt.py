#!/usr/bin/env python3
"""Focused tests for Topic 52 receipt semantic controls."""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from validate_receipt import validate_complete_and_reflink_controls


COMPLETE = "verify current=NEW temp=absent magic=valid checksum=valid generation=42\n"


class CompleteAndReflinkControlsTest(unittest.TestCase):
    """Reject receipts that satisfy only proxy A/A or reflink checks."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        results = self.root / "results"
        results.mkdir()
        self.write("complete-1-oracle.txt", COMPLETE)
        self.write("complete-2-oracle.txt", COMPLETE)
        self.write("aa-control.txt", "aa_control=pass complete verifier outputs match\n")
        self.write(
            "reflink.txt",
            "reflink_copy=success\n"
            "reflink_clone_verify_exit=3 expected_exit=3\n"
            "reflink_post_write_cmp_exit=1 expected_nonzero=yes\n",
        )
        self.write(
            "reflink-clone-verify.txt",
            "verify current=INVALID temp=absent magic=valid checksum=invalid generation=42\n",
        )
        self.write("reflink-source-verify.txt", COMPLETE)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, content: str) -> None:
        """Replace one result file in the temporary receipt."""
        (self.root / "results" / name).write_text(content, encoding="utf-8")

    def assert_rejected(self) -> None:
        """Assert that the semantic controls reject the current fixture."""
        with self.assertRaises(ValueError):
            validate_complete_and_reflink_controls(self.root)

    def test_accepts_complete_controls(self) -> None:
        validate_complete_and_reflink_controls(self.root)

    def test_rejects_two_identical_invalid_complete_outputs(self) -> None:
        invalid = "verify current=OLD temp=absent magic=valid checksum=valid generation=41\n"
        self.write("complete-1-oracle.txt", invalid)
        self.write("complete-2-oracle.txt", invalid)
        self.assert_rejected()

    def test_rejects_complete_outputs_with_an_extra_observation(self) -> None:
        extra = COMPLETE + "verify current=INVALID temp=absent magic=valid checksum=invalid generation=42\n"
        self.write("complete-1-oracle.txt", extra)
        self.write("complete-2-oracle.txt", extra)
        self.assert_rejected()

    def test_rejects_successful_clone_verification(self) -> None:
        self.write(
            "reflink.txt",
            "reflink_copy=success\n"
            "reflink_clone_verify_exit=0 expected_exit=3\n"
            "reflink_post_write_cmp_exit=1 expected_nonzero=yes\n",
        )
        self.assert_rejected()

    def test_rejects_valid_clone_after_mutation(self) -> None:
        self.write("reflink-clone-verify.txt", COMPLETE)
        self.assert_rejected()

    def test_rejects_invalid_source_after_clone_mutation(self) -> None:
        self.write(
            "reflink-source-verify.txt",
            "verify current=INVALID temp=absent magic=valid checksum=invalid generation=42\n",
        )
        self.assert_rejected()

    def test_rejects_equal_source_and_clone_after_mutation(self) -> None:
        self.write(
            "reflink.txt",
            "reflink_copy=success\n"
            "reflink_clone_verify_exit=3 expected_exit=3\n"
            "reflink_post_write_cmp_exit=0 expected_nonzero=yes\n",
        )
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
