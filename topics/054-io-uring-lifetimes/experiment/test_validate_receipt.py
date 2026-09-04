"""Unit tests for order-independent Topic 54 output validation."""

import unittest

from validate_receipt import semantic_output


PREFIX = """\
baseline_setup=ok sq_entries=8 cq_entries=16 features=0xffff
single_issuer owner_cqe={user_data=0x1001,res=0} other_task_enter=-17 (File exists)
defer_taskrun cqes_before_getevents=0 terminal={user_data=0x2001,res=-62}
"""


class SemanticOutputTests(unittest.TestCase):
    """Exercise completion ordering and fail-closed target correlation."""

    def test_accepts_cancel_before_target(self) -> None:
        text = (
            PREFIX
            + "cancel terminal_1={user_data=0x3002,res=0} "
            "terminal_2={user_data=0x3001,res=-125}\nresult=ok\n"
        )
        result = semantic_output(text)
        self.assertEqual(
            result["cancel_completions"],
            [("0x3001", "-125"), ("0x3002", "0")],
        )

    def test_accepts_target_before_cancel(self) -> None:
        text = (
            PREFIX
            + "cancel terminal_1={user_data=0x3001,res=-125} "
            "terminal_2={user_data=0x3002,res=0}\nresult=ok\n"
        )
        semantic_output(text)

    def test_rejects_missing_target_terminal(self) -> None:
        text = (
            PREFIX
            + "cancel terminal_1={user_data=0x3002,res=0} "
            "terminal_2={user_data=0x3002,res=0}\nresult=ok\n"
        )
        with self.assertRaisesRegex(ValueError, "cancel and target"):
            semantic_output(text)

    def test_rejects_contradictory_extra_output(self) -> None:
        text = (
            PREFIX
            + "cancel terminal_1={user_data=0x3002,res=0} "
            "terminal_2={user_data=0x3001,res=-125}\nresult=ok\nresult=fail\n"
        )
        with self.assertRaisesRegex(ValueError, "exactly five"):
            semantic_output(text)


if __name__ == "__main__":
    unittest.main()
