//! Work-stealing and task-granularity lesson.
//!
//! The runnable implementation is `work_stealing_bench.c`. The Python validation
//! checks its checksums independently and forces a split-publication interleaving.

#[cfg(test)]
mod tests {
    #[test]
    fn native_scheduler_contracts() {
        let status = std::process::Command::new("python3")
            .arg("scripts/validate.py")
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .status()
            .expect("python3 and a C11 pthread compiler are required");
        assert!(status.success(), "native scheduler validation failed");
    }

    #[test]
    fn campaign_refuses_nonempty_output_directory() {
        let dir = std::env::temp_dir().join(format!("topic087-campaign-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("create output directory");
        std::fs::write(dir.join("raw.csv"), "stale\n").expect("write stale result");
        let status = std::process::Command::new("python3")
            .args([
                "scripts/run_campaign.py",
                "--source-commit",
                "test",
                "--output",
            ])
            .arg(&dir)
            .current_dir(env!("CARGO_MANIFEST_DIR"))
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .expect("python3 is required");
        let wrote_metadata = dir.join("metadata.json").exists();
        std::fs::remove_dir_all(&dir).expect("remove output directory");
        assert!(
            !status.success(),
            "a nonempty output directory must be refused"
        );
        assert!(
            !wrote_metadata,
            "refusal must happen before any file is written"
        );
    }
}
