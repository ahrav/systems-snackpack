//! Generation-tagged identities for a single-owner descriptor table.
//!
//! The caller serializes lookup through I/O with retirement and owns OS closure.
//! This model stores integers; it does not extend an OS descriptor's lifetime.
//!
//! ```
//! use topic108_fd_reuse::Registry;
//! let mut r = Registry::new(1);
//! let old = r.insert(0, 7).unwrap();
//! assert_eq!(r.retire(old), Some(7));
//! let new = r.insert(0, 7).unwrap();
//! assert_eq!(r.resolve(old), None);
//! assert_eq!(r.resolve(new), Some(7));
//! ```

/// An epoll-compatible token: high 32 bits generation, low 32 bits slot.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Token(pub u64);

#[derive(Clone, Default)]
struct Slot {
    generation: u32,
    fd: Option<i32>,
}

/// A table whose caller owns registration, use, and retirement as one protocol.
pub struct Registry {
    slots: Vec<Slot>,
}

impl Registry {
    /// Creates empty slots. Each slot permits at most `u32::MAX` lifetimes.
    pub fn new(slots: usize) -> Self {
        Self {
            slots: vec![Slot::default(); slots],
        }
    }

    /// Inserts a nonnegative descriptor into a vacant slot. The caller registers it in one slot.
    /// Returns `None` for a negative descriptor or an out-of-range, occupied, or exhausted slot.
    pub fn insert(&mut self, slot: u32, fd: i32) -> Option<Token> {
        let entry = self.slots.get_mut(slot as usize)?;
        if fd < 0 || entry.fd.is_some() {
            return None;
        }
        let generation = entry.generation.checked_add(1)?;
        entry.generation = generation;
        entry.fd = Some(fd);
        Some(Token((u64::from(generation) << 32) | u64::from(slot)))
    }

    /// Resolves a live identity. The caller must prevent close through actual I/O.
    pub fn resolve(&self, token: Token) -> Option<i32> {
        let entry = self.slots.get((token.0 as u32) as usize)?;
        if entry.generation != (token.0 >> 32) as u32 {
            return None;
        }
        entry.fd
    }

    /// Invalidates a live token and returns its descriptor for deregister/close.
    /// Stale retirement commands leave the current occupant intact.
    pub fn retire(&mut self, token: Token) -> Option<i32> {
        let fd = self.resolve(token)?;
        self.slots[(token.0 as u32) as usize].fd = None;
        Some(fd)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stale_retirement_and_invalid_tokens() {
        let mut r = Registry::new(1);
        assert_eq!(r.insert(0, -1), None);
        assert_eq!(r.insert(1, 7), None);
        let old = r.insert(0, 7).unwrap();
        assert_eq!(r.insert(0, 9), None);
        assert_eq!(r.retire(old), Some(7));
        assert_eq!(r.resolve(old), None);
        let new = r.insert(0, 7).unwrap();
        assert_eq!(r.retire(old), None);
        assert_eq!(r.resolve(new), Some(7));
        assert_eq!(r.resolve(Token(u64::MAX)), None);
        assert_eq!(r.resolve(Token(0)), None);
    }

    #[test]
    fn exhaustion_retires_slot_instead_of_wrapping() {
        let mut r = Registry::new(1);
        r.slots[0].generation = u32::MAX - 1;
        let last = r.insert(0, 7).unwrap();
        assert_eq!(r.retire(last), Some(7));
        assert_eq!(r.insert(0, 8), None);
        assert_eq!(r.resolve(last), None);
    }

    #[test]
    fn validate_then_release_ownership_leaves_a_gap() {
        let mut r = Registry::new(1);
        let a = r.insert(0, 7).unwrap();
        let copied_fd = r.resolve(a).unwrap();
        r.retire(a);
        let b = r.insert(0, 7).unwrap();
        assert_eq!(r.resolve(a), None);
        assert_eq!(r.resolve(b), Some(copied_fd));
    }

    #[test]
    fn second_slot_descriptor_zero_and_vacant_retirement() {
        let mut r = Registry::new(2);
        assert_eq!(r.insert(1, -1), None);
        let first = r.insert(1, 0).unwrap();
        assert_eq!(first, Token((1 << 32) | 1));
        assert_eq!(r.resolve(first), Some(0));
        assert_eq!(r.resolve(Token(1 << 32)), None);
        assert_eq!(r.retire(first), Some(0));
        assert_eq!(r.retire(first), None);
        let second = r.insert(1, 9).unwrap();
        assert_eq!(second, Token((2 << 32) | 1));
        assert_eq!(r.resolve(second), Some(9));
        let moved = r.insert(0, 0).unwrap();
        assert_eq!(r.resolve(moved), Some(0));
        assert_eq!(r.resolve(first), None);
        assert_eq!(r.retire(second), Some(9));
        assert_eq!(r.resolve(moved), Some(0));
        assert_eq!(Registry::new(0).insert(0, 7), None);
    }
}
