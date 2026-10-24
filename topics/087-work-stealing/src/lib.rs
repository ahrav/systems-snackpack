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
}
