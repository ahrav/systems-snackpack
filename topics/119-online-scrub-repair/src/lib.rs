//! A repair plan carries the exact verified bytes and observed object lifetime.
//! The caller must hold exclusive access to the current slot for the entire install.
//! The teaching model stores the expected bytes directly. The SQLite example
//! uses a SHA-256 digest in the authoritative row.
//!
//! ```
//! use topic119_online_scrub_repair::{Block, Version};
//! let mut slot = Some(Block::new(Version(1, 7), b"BLUE", b"FAIL", b"BLUE"));
//! let repair = slot.as_ref().unwrap().inspect().unwrap();
//! slot = Some(Block::new(Version(1, 8), b"GOLD", b"GOLD", b"GOLD"));
//! assert!(!repair.install(&mut slot));
//! assert_eq!(slot.unwrap().target(), b"GOLD");
//! ```

/// Object incarnation and logical generation. The store must never reuse a pair.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Version(pub u64, pub u64);

/// One logical block and its two physical copies.
pub struct Block {
    version: Version,
    expected: Vec<u8>,
    target: Vec<u8>,
    mirror: Vec<u8>,
}

impl Block {
    /// Constructs a committed version with possibly damaged physical copies.
    pub fn new(version: Version, expected: &[u8], target: &[u8], mirror: &[u8]) -> Self {
        Self {
            version,
            expected: expected.to_vec(),
            target: target.to_vec(),
            mirror: mirror.to_vec(),
        }
    }

    /// Returns a plan only for a damaged target with a verified donor.
    pub fn inspect(&self) -> Option<Repair> {
        (self.target != self.expected && self.mirror == self.expected).then(|| Repair {
            observed: self.version,
            bytes: self.mirror.clone(),
        })
    }

    /// Returns the bytes stored in the target copy.
    pub fn target(&self) -> &[u8] {
        &self.target
    }
}

/// Verified donor bytes from one observation.
pub struct Repair {
    observed: Version,
    bytes: Vec<u8>,
}

impl Repair {
    /// Replaces the target only if the same version still occupies this slot.
    pub fn install(self, slot: &mut Option<Block>) -> bool {
        let Some(block) = slot.as_mut().filter(|b| b.version == self.observed) else {
            return false;
        };
        block.target = self.bytes;
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn damaged() -> Block {
        Block::new(Version(1, 7), b"BLUE", b"FAIL", b"BLUE")
    }

    #[test]
    fn repair_uses_owned_verified_bytes() {
        let mut block = damaged();
        let repair = block.inspect().unwrap();
        block.mirror.fill(0);
        let mut slot = Some(block);
        assert!(repair.install(&mut slot));
        let repaired = slot.unwrap();
        assert_eq!(repaired.target(), b"BLUE");
        assert!(repaired.inspect().is_none());
        assert!(
            Block::new(Version(1, 7), b"BLUE", b"FAIL", b"FAIL")
                .inspect()
                .is_none()
        );
    }

    #[test]
    fn delayed_worker_rechecks_slot_under_the_lock() {
        use std::sync::{Mutex, mpsc};
        use std::thread;

        for replacement in [None, Some(Version(1, 8)), Some(Version(2, 7))] {
            let slot = Mutex::new(Some(damaged()));
            let (observed, wait_observed) = mpsc::channel();
            let (resume, wait_resume) = mpsc::channel();
            thread::scope(|scope| {
                let slot_ref = &slot;
                let worker = scope.spawn(move || {
                    let plan = slot_ref
                        .lock()
                        .unwrap()
                        .as_ref()
                        .unwrap()
                        .inspect()
                        .unwrap();
                    observed.send(()).unwrap();
                    wait_resume.recv().unwrap();
                    plan.install(&mut slot_ref.lock().unwrap())
                });
                wait_observed.recv().unwrap();
                *slot.lock().unwrap() =
                    replacement.map(|v| Block::new(v, b"GOLD", b"GOLD", b"GOLD"));
                resume.send(()).unwrap();
                assert!(!worker.join().unwrap());
            });
            let block = slot.into_inner().unwrap();
            assert_eq!(
                block.as_ref().map(Block::target),
                replacement.map(|_| &b"GOLD"[..])
            );
        }
    }
}
