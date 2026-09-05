#!/usr/bin/env python3
"""Focused tests for the Topic 55 receipt validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


EXPERIMENT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("topic55_validator", EXPERIMENT / "validate_receipt.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load validate_receipt.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ValidatorUnitTests(unittest.TestCase):
    """Exercise strict parsing and the fixed semantic oracle."""

    def test_fixed_plan_has_balanced_campaign_and_control(self) -> None:
        """The plan keeps ABBA/BAAB balance and an identical many-flow control."""
        rows = VALIDATOR.expected_plan()
        self.assertEqual(len(rows), 24)
        self.assertEqual("".join(row[3] for row in rows[:16]), "ABBABAABABBABAAB")
        self.assertEqual("".join(row[3] for row in rows[16:]), "XYYXYXXY")
        self.assertTrue(all(row[4:] == ("many", 128, 2) for row in rows[16:]))

    def test_key_value_parser_rejects_duplicates(self) -> None:
        """A later field cannot silently replace a signed observation."""
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            VALIDATOR.parse_key_values("status=ok status=bad", "test")

    def test_client_summary_requires_positive_napi_evidence(self) -> None:
        """Stable zero is not accepted as usable NAPI placement evidence."""
        digest = "a" * 64
        summary = {
            "status": "ok",
            "role": "client",
            "placement_scope": "connected_flow_socket",
            "flows": "1",
            "packets_per_flow": "256",
            "observations": "256",
            "peer_stable": "1/1",
            "cpu_stable": "1/1",
            "napi_stable": "1/1",
            "pair_stable": "1/1",
            "known_cpu_flows": "1/1",
            "positive_napi_flows": "0/1",
            "unique_cpus": "1",
            "positive_napi_ids": "0",
            "source_sha256": digest,
        }
        with self.assertRaisesRegex(ValueError, "positive_napi_flows"):
            VALIDATOR.validate_summary(summary, digest)

    def test_server_summary_uses_shared_socket_scope(self) -> None:
        """The validator never treats a wildcard server socket as per-flow placement."""
        digest = "b" * 64
        summary = {
            "status": "ok",
            "role": "server",
            "placement_scope": "shared_socket_only",
            "flows": "128",
            "packets_per_flow": "2",
            "observations": "256",
            "peer_stable": "128/128",
            "unique_source_endpoints": "128/128",
            "shared_socket_cpu": "-1",
            "shared_socket_napi": "7",
            "source_sha256": digest,
        }
        role, flows, _, _ = VALIDATOR.validate_summary(summary, digest)
        self.assertEqual((role, flows), ("server", 128))


if __name__ == "__main__":
    unittest.main()
