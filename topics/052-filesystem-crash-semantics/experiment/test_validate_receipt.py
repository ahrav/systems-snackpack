#!/usr/bin/env python3
"""Focused tests for Topic 52 receipt semantic controls."""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import pathlib
import subprocess
import tarfile
import tempfile
import time
import unittest

from validate_receipt import validate, validate_complete_and_reflink_controls


COMPLETE = "verify current=NEW temp=absent magic=valid checksum=valid generation=42\n"
CORRUPT = "verify current=INVALID temp=absent magic=valid checksum=invalid generation=42\n"
OPEN_LINE = "syscall=open-directory result=3\n"
INIT_LOG = (
    OPEN_LINE
    + "syscall=openat name=current result=4\n"
    + "syscall=write name=current bytes=8192 result=success\n"
    + "syscall=fsync name=current result=success\n"
    + "syscall=fsync name=directory result=success\n"
    + "init=complete generation=OLD value=41\n"
)
UPDATE_PREFIX_LOG = (
    OPEN_LINE
    + "syscall=openat name=next.tmp result=4\n"
    + "syscall=write name=next.tmp bytes=8192 result=success\n"
)
FSYNC_TEMPORARY_LINE = "syscall=fsync name=next.tmp result=success\n"
RENAME_LINE = "syscall=renameat from=next.tmp to=current result=success\n"
FSYNC_DIRECTORY_LINE = "syscall=fsync name=directory result=success\n"
CUT_LOGS = {
    "after_write": UPDATE_PREFIX_LOG + "failpoint=after_write action=_exit code=101\n",
    "after_file_fsync": UPDATE_PREFIX_LOG
    + FSYNC_TEMPORARY_LINE
    + "failpoint=after_file_fsync action=_exit code=102\n",
    "after_rename": UPDATE_PREFIX_LOG
    + FSYNC_TEMPORARY_LINE
    + RENAME_LINE
    + "failpoint=after_rename action=_exit code=103\n",
    "after_dir_fsync": UPDATE_PREFIX_LOG
    + FSYNC_TEMPORARY_LINE
    + RENAME_LINE
    + FSYNC_DIRECTORY_LINE
    + "failpoint=after_dir_fsync action=_exit code=104\n",
}
COMPLETE_LOG = (
    UPDATE_PREFIX_LOG
    + FSYNC_TEMPORARY_LINE
    + RENAME_LINE
    + FSYNC_DIRECTORY_LINE
    + "acknowledgement=success generation=NEW value=42\n"
)
CORRUPTION_LOG = (
    OPEN_LINE
    + "syscall=fsync name=corruption-control result=success\n"
    + "corruption_control=applied offset=128\n"
)
FILESYSTEM = (
    "TARGET   SOURCE         FSTYPE OPTIONS\n"
    "/var/tmp /dev/nvme0n1p1 xfs    rw,noatime\n"
    "type=xfs block=4096 namelen=255\n"
    "Filesystem 1B-blocks Used Available Use% Mounted on\n"
    "meta-data=/dev/nvme0n1p1 isize=512 agcount=4\n"
)
COMMIT = "b" * 40
TOPIC = "topics/052-filesystem-crash-semantics/"
PROBE_SOURCE = TOPIC + "experiment/cow_crash_probe.c"
PROBE_BYTES = b"int main(void) { return 0; }\n"
RUNNER_SOURCE = TOPIC + "experiment/run_host.sh"
RUNNER_BYTES = b"#!/usr/bin/env bash\nset -euo pipefail\n"
NOTES_SOURCE = TOPIC + "README.md"
NOTES_BYTES = b"# Topic 52\n"
OBJDUMP = (
    "cow_crash_probe:     file format elf64-x86-64\n"
    "0000000000401070 <openat@plt>:\n"
    "  401070:\tff 25 aa 2f 00 00    \tjmp    *0x2faa(%rip)\n"
    "  401224:\te8 47 fe ff ff       \tcall   401070 <openat@plt>\n"
    "  4015dc:\te8 0f fb ff ff       \tcall   4010f0 <fsync@plt>\n"
    "  401ad0:\te8 5b f6 ff ff       \tcall   401130 <renameat@plt>\n"
)
# The runner's symbol index can name symbols from diagnostic strings and debug
# entries without a generated call site.
RETAINED_PATHS = (
    'cow_crash_probe.s:398:\t.string\t"openat current"\n'
    'cow_crash_probe.s:219:\t.string\t"fsync"\n'
    'cow_crash_probe.s:1059:\t.string\t"renameat"\n'
    'cow_crash_probe.s:8308:\t.string\t"fnv1a"\n'
)


class CompleteAndReflinkControlsTest(unittest.TestCase):
    """Reject receipts that satisfy only proxy A/A or reflink checks."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        results = self.root / "results"
        results.mkdir()
        self.write("complete-1-oracle.txt", COMPLETE)
        self.write("complete-2-oracle.txt", COMPLETE)
        for repetition in (1, 2):
            self.write(f"complete-{repetition}-init.txt", INIT_LOG)
            self.write(f"complete-{repetition}-update.txt", COMPLETE_LOG)
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

    def test_rejects_a_comparison_that_failed_instead_of_differing(self) -> None:
        self.write(
            "reflink.txt",
            "reflink_copy=success\n"
            "reflink_clone_verify_exit=3 expected_exit=3\n"
            "reflink_post_write_cmp_exit=2 expected_exit=1\n",
        )
        self.assert_rejected()

    def test_accepts_the_current_comparison_annotation(self) -> None:
        self.write(
            "reflink.txt",
            "reflink_copy=success\n"
            "reflink_clone_verify_exit=3 expected_exit=3\n"
            "reflink_post_write_cmp_exit=1 expected_exit=1\n",
        )
        validate_complete_and_reflink_controls(self.root)


def source_archive(commit: str = COMMIT, comment: str | None = COMMIT) -> bytes:
    """Return one gzip source archive holding the topic files under a commit prefix.

    `git archive` records the commit in the PAX global `comment` field, so the
    fixture carries it too. Passing `comment=None` builds an archive without one.
    """
    buffer = io.BytesIO()
    headers = {} if comment is None else {"comment": comment}
    with tarfile.open(
        fileobj=buffer, mode="w:gz", format=tarfile.PAX_FORMAT, pax_headers=headers
    ) as bundle:
        members = (
            (PROBE_SOURCE, PROBE_BYTES),
            (RUNNER_SOURCE, RUNNER_BYTES),
            (NOTES_SOURCE, NOTES_BYTES),
        )
        for relative, content in members:
            info = tarfile.TarInfo(f"systems-snackpack-{commit}/{relative}")
            info.size = len(content)
            info.mtime = int(time.time())
            bundle.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def identity_text(archive: bytes, runner: bytes = RUNNER_BYTES) -> bytes:
    """Return one receipt identity file for the given archive and launcher."""
    return (
        "target_label=fixture\n"
        "hostname=fixture.example\n"
        "architecture=x86_64\n"
        f"source_commit={COMMIT}\n"
        f"source_archive_sha256={hashlib.sha256(archive).hexdigest()}\n"
        f"runner_sha256={hashlib.sha256(runner).hexdigest()}\n"
    ).encode("utf-8")


def inventory(entries: dict[str, bytes]) -> str:
    """Return one `sha256sum` inventory for the given source contents."""
    return "".join(
        f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
        for relative, content in sorted(entries.items())
    )


class ValidateReceiptTest(unittest.TestCase):
    """Reject sealed receipts whose seal, manifest, source, or codegen claim fails."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name) / "receipt"
        self.archive = source_archive()
        self.sources = {
            PROBE_SOURCE: PROBE_BYTES,
            RUNNER_SOURCE: RUNNER_BYTES,
            NOTES_SOURCE: NOTES_BYTES,
        }
        listing = inventory(self.sources)
        cuts = {
            "after_write": (101, "OLD", "present", 41),
            "after_file_fsync": (102, "OLD", "present", 41),
            "after_rename": (103, "NEW", "absent", 42),
            "after_dir_fsync": (104, "NEW", "absent", 42),
        }
        self.files: dict[str, bytes] = {
            "source.tar.gz": self.archive,
            "cow_crash_probe.c": PROBE_BYTES,
            "source-files-before.sha256": listing.encode("utf-8"),
            "source-files-after.sha256": listing.encode("utf-8"),
            "identity.txt": identity_text(self.archive),
            "run-status.txt": (
                "run=pass\n"
                "process_crash_only=yes\n"
                "power_loss_tested=no\n"
                "filesystem_replay_tested=no\n"
                "timing_claim=no\n"
            ).encode("utf-8"),
            "codegen/objdump.txt": OBJDUMP.encode("utf-8"),
            "codegen/retained-paths.txt": RETAINED_PATHS.encode("utf-8"),
            "filesystem.txt": FILESYSTEM.encode("utf-8"),
            "results/aa-control.txt": b"aa_control=pass complete verifier outputs match\n",
            "results/complete-1-oracle.txt": COMPLETE.encode("utf-8"),
            "results/complete-2-oracle.txt": COMPLETE.encode("utf-8"),
            "results/complete-1-init.txt": INIT_LOG.encode("utf-8"),
            "results/complete-2-init.txt": INIT_LOG.encode("utf-8"),
            "results/complete-1-update.txt": COMPLETE_LOG.encode("utf-8"),
            "results/complete-2-update.txt": COMPLETE_LOG.encode("utf-8"),
            "results/corrupt-status.txt": b"corrupt_verify_exit=3 expected_exit=3\n",
            "results/corrupt-init.txt": INIT_LOG.encode("utf-8"),
            "results/corrupt-update.txt": COMPLETE_LOG.encode("utf-8"),
            "results/corrupt-action.txt": CORRUPTION_LOG.encode("utf-8"),
            "results/reflink-corrupt-clone.txt": CORRUPTION_LOG.encode("utf-8"),
            "results/corrupt-verify.txt": (OPEN_LINE + CORRUPT).encode("utf-8"),
            "results/reflink.txt": (
                "reflink_copy=success\n"
                "reflink_clone_verify_exit=3 expected_exit=3\n"
                "reflink_post_write_cmp_exit=1 expected_nonzero=yes\n"
            ).encode("utf-8"),
            "results/reflink-clone-verify.txt": (OPEN_LINE + CORRUPT).encode("utf-8"),
            "results/reflink-source-verify.txt": (OPEN_LINE + COMPLETE).encode("utf-8"),
        }
        for cut, (status, state, temporary, generation) in cuts.items():
            self.files[f"results/{cut}-init.txt"] = INIT_LOG.encode("utf-8")
            self.files[f"results/{cut}-update.txt"] = CUT_LOGS[cut].encode("utf-8")
            self.files[f"results/{cut}-status.txt"] = (
                f"cut={cut} update_exit={status} expected_exit={status}\n"
            ).encode("utf-8")
            self.files[f"results/{cut}-verify.txt"] = (
                OPEN_LINE
                + f"verify current={state} temp={temporary} magic=valid"
                + f" checksum=valid generation={generation}\n"
            ).encode("utf-8")
        self.unmanifested: dict[str, bytes] = {}

    def tearDown(self) -> None:
        subprocess.run(["chmod", "-R", "u+w", str(self.root)], check=False)
        self.temporary.cleanup()

    def use_archive(self, archive: bytes) -> None:
        """Replace the retained source archive and the identity digest that binds it."""
        self.archive = archive
        self.files["source.tar.gz"] = archive
        self.files["identity.txt"] = identity_text(archive)

    def seal(self) -> None:
        """Materialize the fixture, write its manifest, and remove every write bit."""
        for relative, content in self.files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        manifest = "".join(
            f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
            for relative, content in sorted(self.files.items())
        )
        (self.root / "MANIFEST.sha256").write_text(manifest, encoding="utf-8")
        (self.root / "SEALED").touch()
        for relative, content in self.unmanifested.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(["chmod", "-R", "a-w", str(self.root)], check=True)

    def run_validate(self) -> dict[str, object]:
        """Validate the sealed fixture against its expected identity."""
        return validate(
            argparse.Namespace(
                receipt=self.root,
                expected_target_label="fixture",
                expected_hostname="fixture.example",
                expected_architecture="x86_64",
                expected_source_commit=COMMIT,
                expected_source_archive_sha256=hashlib.sha256(self.archive).hexdigest(),
            )
        )

    def assert_rejected(self) -> None:
        """Assert that validation rejects the current sealed fixture."""
        self.seal()
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_accepts_a_complete_sealed_receipt(self) -> None:
        self.seal()
        result = self.run_validate()
        self.assertTrue(result["pass"])
        self.assertTrue(result["sealed"])
        self.assertEqual(result["files_verified"], len(self.files))

    def test_rejects_a_writable_receipt(self) -> None:
        self.seal()
        subprocess.run(
            ["chmod", "u+w", str(self.root / "MANIFEST.sha256")], check=True
        )
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_a_writable_receipt_root(self) -> None:
        self.seal()
        subprocess.run(["chmod", "u+w", str(self.root)], check=True)
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_an_unmanifested_nested_metadata_file(self) -> None:
        self.unmanifested["results/SEALED"] = b""
        self.assert_rejected()

    def test_rejects_an_unmanifested_nested_manifest_file(self) -> None:
        self.unmanifested["results/MANIFEST.sha256"] = b"pretend\n"
        self.assert_rejected()

    def test_rejects_a_symbolic_link_in_the_receipt(self) -> None:
        self.seal()
        subprocess.run(["chmod", "u+w", str(self.root / "results")], check=True)
        (self.root / "results" / "link.txt").symlink_to("corrupt-verify.txt")
        subprocess.run(["chmod", "a-w", str(self.root / "results")], check=True)
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_a_dangling_symbolic_link_in_the_receipt(self) -> None:
        self.seal()
        subprocess.run(["chmod", "u+w", str(self.root / "results")], check=True)
        (self.root / "results" / "link.txt").symlink_to("absent.txt")
        subprocess.run(["chmod", "a-w", str(self.root / "results")], check=True)
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_an_unmanifested_fifo_in_the_receipt(self) -> None:
        self.seal()
        subprocess.run(["chmod", "u+w", str(self.root / "results")], check=True)
        os.mkfifo(self.root / "results" / "pipe", 0o400)
        subprocess.run(["chmod", "a-w", str(self.root / "results")], check=True)
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_a_contradictory_second_cut_observation(self) -> None:
        self.files["results/after_write-verify.txt"] += COMPLETE.encode("utf-8")
        self.assert_rejected()

    def test_rejects_a_duplicated_cut_status_record(self) -> None:
        self.files["results/after_rename-status.txt"] += (
            b"cut=after_rename update_exit=0 expected_exit=0\n"
        )
        self.assert_rejected()

    def test_rejects_a_missing_replay_boundary(self) -> None:
        self.files["run-status.txt"] = (
            self.files["run-status.txt"].replace(b"filesystem_replay_tested=no\n", b"")
        )
        self.assert_rejected()

    def test_rejects_a_conflicting_replay_boundary(self) -> None:
        self.files["run-status.txt"] = self.files["run-status.txt"].replace(
            b"filesystem_replay_tested=no\n", b"filesystem_replay_tested=yes\n"
        )
        self.assert_rejected()

    def test_rejects_an_inventory_missing_an_archived_file(self) -> None:
        self.files["source-files-before.sha256"] = inventory(
            {PROBE_SOURCE: PROBE_BYTES}
        ).encode("utf-8")
        self.files["source-files-after.sha256"] = self.files[
            "source-files-before.sha256"
        ]
        self.assert_rejected()

    def test_rejects_an_empty_inventory_pair(self) -> None:
        self.files["source-files-before.sha256"] = b""
        self.files["source-files-after.sha256"] = b""
        self.assert_rejected()

    def test_rejects_an_inventory_digest_that_disagrees_with_the_archive(self) -> None:
        self.files["source-files-before.sha256"] = inventory(
            {PROBE_SOURCE: PROBE_BYTES, NOTES_SOURCE: b"# rewritten\n"}
        ).encode("utf-8")
        self.files["source-files-after.sha256"] = self.files[
            "source-files-before.sha256"
        ]
        self.assert_rejected()

    def test_rejects_a_retained_probe_copy_that_left_the_archive(self) -> None:
        self.files["cow_crash_probe.c"] = b"int main(void) { return 1; }\n"
        self.assert_rejected()

    def test_rejects_an_archive_without_an_embedded_commit(self) -> None:
        self.use_archive(source_archive(comment=None))
        self.assert_rejected()

    def test_rejects_an_archive_that_names_another_commit(self) -> None:
        self.use_archive(source_archive(comment="c" * 40))
        self.assert_rejected()

    def test_rejects_a_contradictory_run_declaration(self) -> None:
        self.files["run-status.txt"] += b"run=fail\n"
        self.assert_rejected()

    def test_rejects_a_contradictory_power_loss_declaration(self) -> None:
        self.files["run-status.txt"] += b"power_loss_tested=yes\n"
        self.assert_rejected()

    def test_rejects_a_contradictory_timing_declaration(self) -> None:
        self.files["run-status.txt"] += b"timing_claim=yes\n"
        self.assert_rejected()

    def test_rejects_an_appended_replay_declaration(self) -> None:
        self.files["run-status.txt"] += b"filesystem_replay_tested=yes\n"
        self.assert_rejected()

    def test_rejects_a_duplicated_aa_control_record(self) -> None:
        self.files["results/aa-control.txt"] += b"aa_control=fail outputs differ\n"
        self.assert_rejected()

    def test_rejects_a_duplicated_reflink_copy_record(self) -> None:
        self.files["results/reflink.txt"] += b"reflink_copy=failure\n"
        self.assert_rejected()

    def test_rejects_a_cut_that_skipped_the_temporary_fsync(self) -> None:
        self.files["results/after_file_fsync-update.txt"] = (
            UPDATE_PREFIX_LOG + "failpoint=after_file_fsync action=_exit code=102\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_a_cut_that_skipped_the_directory_fsync(self) -> None:
        self.files["results/after_dir_fsync-update.txt"] = (
            UPDATE_PREFIX_LOG
            + FSYNC_TEMPORARY_LINE
            + RENAME_LINE
            + "failpoint=after_dir_fsync action=_exit code=104\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_a_cut_whose_steps_are_out_of_order(self) -> None:
        self.files["results/after_rename-update.txt"] = (
            UPDATE_PREFIX_LOG
            + RENAME_LINE
            + FSYNC_TEMPORARY_LINE
            + "failpoint=after_rename action=_exit code=103\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_an_extra_step_before_the_failpoint(self) -> None:
        self.files["results/after_write-update.txt"] = (
            UPDATE_PREFIX_LOG
            + FSYNC_TEMPORARY_LINE
            + "failpoint=after_write action=_exit code=101\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_an_initialization_that_skipped_the_directory_fsync(self) -> None:
        self.files["results/after_write-init.txt"] = (
            INIT_LOG.replace(FSYNC_DIRECTORY_LINE, "").encode("utf-8")
        )
        self.assert_rejected()

    def test_rejects_a_complete_run_without_an_acknowledgement(self) -> None:
        self.files["results/complete-1-update.txt"] = (
            COMPLETE_LOG.replace(
                "acknowledgement=success generation=NEW value=42\n", ""
            ).encode("utf-8")
        )
        self.assert_rejected()

    def test_tolerates_a_diagnostic_line_in_a_probe_log(self) -> None:
        self.files["results/after_write-update.txt"] = (
            CUT_LOGS["after_write"] + "note: unrelated diagnostic output\n"
        ).encode("utf-8")
        self.seal()
        self.assertTrue(self.run_validate()["pass"])

    def test_rejects_a_non_xfs_work_mount(self) -> None:
        self.files["filesystem.txt"] = FILESYSTEM.replace(
            "type=xfs block=4096", "type=btrfs block=4096"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_missing_filesystem_evidence(self) -> None:
        self.files["filesystem.txt"] = b"TARGET SOURCE FSTYPE OPTIONS\n"
        self.assert_rejected()

    def test_rejects_a_contradictory_work_fstype_record(self) -> None:
        self.files["filesystem.txt"] = (
            FILESYSTEM + "work_fstype=overlay required_fstype=xfs\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_a_second_filesystem_type_record(self) -> None:
        self.files["filesystem.txt"] = (
            FILESYSTEM + "type=tmpfs block=4096 namelen=255\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_accepts_the_enforced_work_fstype_record(self) -> None:
        self.files["filesystem.txt"] = (
            FILESYSTEM + "work_fstype=xfs required_fstype=xfs\n"
        ).encode("utf-8")
        self.seal()
        self.assertTrue(self.run_validate()["pass"])

    def test_rejects_codegen_evidence_without_a_call_instruction(self) -> None:
        self.files["codegen/objdump.txt"] = (
            "cow_crash_probe:     file format elf64-x86-64\n"
            '  4013a0:\t.string\t"renameat"\n'
            "  401224:\te8 47 fe ff ff       \tcall   401070 <openat@plt>\n"
            "  4015dc:\te8 0f fb ff ff       \tcall   4010f0 <fsync@plt>\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_accepts_aarch64_branch_instruction_evidence(self) -> None:
        self.files["codegen/objdump.txt"] = (
            "cow_crash_probe:     file format elf64-littleaarch64\n"
            "   162f8:\t97ffe7ca \tbl\t10220 <openat@plt>\n"
            "   16378:\t97ffe7aa \tbl\t10230 <fsync@plt>\n"
            "   163a0:\t97ffe728 \tbl\t10240 <renameat@plt>\n"
        ).encode("utf-8")
        self.seal()
        self.assertTrue(self.run_validate()["pass"])

    def test_rejects_an_identity_without_a_launcher_digest(self) -> None:
        self.files["identity.txt"] = b"".join(
            line + b"\n"
            for line in self.files["identity.txt"].splitlines()
            if not line.startswith(b"runner_sha256=")
        )
        self.assert_rejected()

    def test_rejects_a_launcher_digest_that_left_the_archive(self) -> None:
        self.files["identity.txt"] = identity_text(
            self.archive, runner=b"#!/usr/bin/env bash\nexit 0\n"
        )
        self.assert_rejected()

    def test_rejects_an_archive_without_the_launcher(self) -> None:
        buffer = io.BytesIO()
        with tarfile.open(
            fileobj=buffer,
            mode="w:gz",
            format=tarfile.PAX_FORMAT,
            pax_headers={"comment": COMMIT},
        ) as bundle:
            info = tarfile.TarInfo(f"systems-snackpack-{COMMIT}/{PROBE_SOURCE}")
            info.size = len(PROBE_BYTES)
            bundle.addfile(info, io.BytesIO(PROBE_BYTES))
        self.use_archive(buffer.getvalue())
        self.files["source-files-before.sha256"] = inventory(
            {PROBE_SOURCE: PROBE_BYTES}
        ).encode("utf-8")
        self.files["source-files-after.sha256"] = self.files[
            "source-files-before.sha256"
        ]
        self.assert_rejected()

    def test_rejects_a_truncated_archive_without_a_traceback(self) -> None:
        self.use_archive(self.archive[: len(self.archive) // 2])
        self.seal()
        with self.assertRaises(ValueError):
            self.run_validate()

    def test_rejects_a_missing_corruption_setup(self) -> None:
        self.files["results/corrupt-update.txt"] = CUT_LOGS["after_write"].encode(
            "utf-8"
        )
        self.assert_rejected()

    def test_rejects_a_corruption_action_at_another_offset(self) -> None:
        self.files["results/corrupt-action.txt"] = CORRUPTION_LOG.replace(
            "offset=128", "offset=4096"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_an_unsynchronized_corruption_action(self) -> None:
        self.files["results/corrupt-action.txt"] = (
            OPEN_LINE + "corruption_control=applied offset=128\n"
        ).encode("utf-8")
        self.assert_rejected()

    def test_rejects_a_clone_mutation_that_never_happened(self) -> None:
        self.files["results/reflink-corrupt-clone.txt"] = OPEN_LINE.encode("utf-8")
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
