//! Process identities survive numeric PID reuse in this single-owner model.
//!
//! Signaling here selects running targets only. Zombie signal syscall return
//! values are outside the model. Reaping releases a PID, while retained handles
//! keep their original identity. OS descriptor ownership is a separate contract.
//!
//! ```
//! use topic109_pidfd::Processes;
//! let mut p = Processes::default();
//! let old = p.spawn(0).unwrap();
//! p.exit(0);
//! p.reap(0);
//! let new = p.spawn(0).unwrap();
//! assert_eq!(p.signal(old), None);
//! assert_eq!(p.signal(new), Some(new.identity()));
//! ```

/// A retained process identity, acquired atomically during spawn.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Handle(u64);
impl Handle {
    /// Returns the unique birth identity used by the experiment.
    pub fn identity(self) -> u64 {
        self.0
    }
}

#[derive(Clone, Copy)]
struct Process {
    id: u64,
    running: bool,
}

/// Two reusable numeric PIDs with monotonically allocated process identities.
#[derive(Default)]
pub struct Processes {
    slots: [Option<Process>; 2],
    next: u64,
}
impl Processes {
    /// Creates a process and its handle together, or rejects an occupied PID.
    pub fn spawn(&mut self, pid: usize) -> Option<Handle> {
        let slot = self.slots.get_mut(pid)?;
        if slot.is_some() {
            return None;
        }
        self.next = self.next.checked_add(1)?;
        *slot = Some(Process {
            id: self.next,
            running: true,
        });
        Some(Handle(self.next))
    }
    /// Acquires whichever process currently owns this PID, including a zombie.
    pub fn open(&self, pid: usize) -> Option<Handle> {
        Some(Handle(self.slots.get(pid)?.as_ref()?.id))
    }
    /// Marks the PID's current occupant exited; exit retains its identity.
    pub fn exit(&mut self, pid: usize) {
        if let Some(Some(p)) = self.slots.get_mut(pid) {
            p.running = false;
        }
    }
    /// Releases an exited process's numeric PID for reuse.
    pub fn reap(&mut self, pid: usize) {
        if let Some(slot) = self.slots.get_mut(pid)
            && slot.as_ref().is_some_and(|p| !p.running)
        {
            *slot = None;
        }
    }
    /// Returns the running target's birth identity for a retained handle.
    pub fn signal(&self, handle: Handle) -> Option<u64> {
        self.slots
            .iter()
            .flatten()
            .find(|p| p.id == handle.0 && p.running)
            .map(|p| p.id)
    }
    /// Returns the running occupant selected by a raw numeric PID.
    pub fn raw_signal(&self, pid: usize) -> Option<u64> {
        self.slots
            .get(pid)?
            .as_ref()
            .filter(|p| p.running)
            .map(|p| p.id)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn zombie_retains_identity_until_reap() {
        let mut p = Processes::default();
        let a = p.spawn(0).unwrap();
        p.exit(0);
        assert_eq!(p.open(0), Some(a));
        assert_eq!(p.spawn(0), None);
        p.reap(0);
        let b = p.spawn(0).unwrap();
        assert_ne!(a, b);
        assert_eq!(p.open(0), Some(b));
        assert_eq!(p.signal(a), None);
        assert_eq!(p.raw_signal(0), Some(b.identity()));
    }
    #[test]
    fn running_reap_invalid_pid_and_identity_exhaustion() {
        let mut p = Processes::default();
        let a = p.spawn(1).unwrap();
        p.reap(1);
        assert_eq!(p.signal(a), Some(a.identity()));
        assert_eq!(p.spawn(2), None);
        assert_eq!(p.open(2), None);
        assert_eq!(p.raw_signal(2), None);
        p.exit(2);
        p.reap(2);
        p.next = u64::MAX;
        assert_eq!(p.spawn(0), None);
        assert_eq!(p.signal(a), Some(a.identity()));
    }
}
