//! Atomic-step marking model with fixed roots and a fixed object set.
//! Run `cargo run -p topic094-concurrent-gc --release --example probe -- bench satb delete`.
//! SATB callers may publish only objects reachable at cycle start. Root changes,
//! allocation, weak references, relocation and hardware memory ordering are outside this model.
//!
//! ```
//! use topic094_concurrent_gc::{Marker, Mode};
//! let mut gc = Marker::new(vec![None, Some(2), None], &[0, 1], Mode::Satb);
//! gc.scan();
//! gc.store(0, Some(2));
//! gc.store(1, None);
//! gc.finish();
//! assert_eq!(gc.marked(), &[true, true, true]);
//! ```

/// Marking policy. STW defers all scanning until after stores finish.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Mode {
    /// Trace the final graph with application mutation stopped.
    Stw,
    /// Shade every inserted referent before publishing it.
    Insertion,
    /// Shade every overwritten referent before deleting its edge.
    Satb,
    /// Deliberately broken concurrent tracing control.
    None,
}

/// Marking state. A marked object is queued or has already been scanned.
pub struct Marker {
    heap: Vec<Option<usize>>,
    marked: Vec<bool>,
    pending: Vec<usize>,
    mode: Mode,
    /// Number of object scans, including objects with empty slots.
    pub scans: usize,
    /// Barrier calls, including null or already marked referents.
    pub barriers: usize,
}
impl Marker {
    /// Start a cycle with stable roots. IDs must index `heap`.
    pub fn new(heap: Vec<Option<usize>>, roots: &[usize], mode: Mode) -> Self {
        let n = heap.len();
        assert!(heap.iter().flatten().all(|&x| x < n));
        let mut s = Self {
            heap,
            marked: vec![false; n],
            pending: Vec::new(),
            mode,
            scans: 0,
            barriers: 0,
        };
        for &r in roots.iter().rev() {
            s.shade(Some(r));
        }
        s
    }
    fn shade(&mut self, obj: Option<usize>) {
        if let Some(x) = obj
            && !self.marked[x]
        {
            self.marked[x] = true;
            self.pending.push(x);
        }
    }
    /// Execute one atomic scan. STW scans begin only in `finish`.
    pub fn scan(&mut self) {
        if self.mode == Mode::Stw {
            return;
        }
        self.scan_one();
    }
    fn scan_one(&mut self) {
        if let Some(x) = self.pending.pop() {
            self.scans += 1;
            self.shade(self.heap[x]);
        }
    }
    /// Execute one atomic pointer store and its policy's barrier.
    pub fn store(&mut self, owner: usize, new: Option<usize>) {
        assert!(new.is_none_or(|x| x < self.heap.len()));
        match self.mode {
            Mode::Insertion => {
                self.barriers += 1;
                self.shade(new);
            }
            Mode::Satb => {
                self.barriers += 1;
                self.shade(self.heap[owner]);
            }
            _ => {}
        }
        self.heap[owner] = new;
    }
    /// Stop mutation and drain all remaining work.
    pub fn finish(&mut self) {
        while !self.pending.is_empty() {
            self.scan_one();
        }
    }
    /// Objects retained by this cycle.
    pub fn marked(&self) -> &[bool] {
        &self.marked
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn hidden_live_object() {
        for mode in [Mode::None, Mode::Insertion, Mode::Satb, Mode::Stw] {
            let mut m = Marker::new(vec![None, Some(2), None], &[0, 1], mode);
            m.scan();
            m.store(0, Some(2));
            m.store(1, None);
            m.finish();
            assert_eq!(m.marked()[2], mode != Mode::None);
        }
    }
    #[test]
    fn snapshot_retains_deleted_chain() {
        for mode in [Mode::Insertion, Mode::Satb, Mode::Stw] {
            let mut m = Marker::new(vec![Some(1), Some(2), None], &[0], mode);
            m.store(0, None);
            m.finish();
            assert_eq!(
                m.marked().iter().filter(|&&x| x).count(),
                if mode == Mode::Satb { 3 } else { 1 }
            );
        }
    }
    #[test]
    fn cycles_and_duplicate_barriers_terminate() {
        let mut m = Marker::new(vec![Some(1), Some(0)], &[0], Mode::Insertion);
        for _ in 0..100 {
            m.store(0, Some(1));
        }
        m.finish();
        assert_eq!(m.scans, 2);
        assert_eq!(m.barriers, 100);
    }
}
