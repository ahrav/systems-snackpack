//! Recovery of an interrupted transfer from an ordered undo record.
//!
//! ```
//! use topic111_robust_mutex::Snapshot;
//! let mut s = Snapshot::at_crash(60, 10, 3);
//! assert_eq!(s.recover(), Some((60, 40)));
//! ```

/// Shared data at one modeled process-death boundary.
#[derive(Clone, Copy, Debug)]
pub struct Snapshot {
    a: u32,
    b: u32,
    active: bool,
    undo: (u32, u32),
}

impl Snapshot {
    /// Construct one of six ordered crash points for a transfer out of `a`.
    ///
    /// Panics unless `amount <= a <= 100` and `point <= 5`.
    pub fn at_crash(a: u32, amount: u32, point: u8) -> Self {
        assert!(a <= 100 && amount <= a && point <= 5);
        Self {
            a: if point >= 3 { a - amount } else { a },
            b: if point >= 4 {
                100 - a + amount
            } else {
                100 - a
            },
            active: (2..5).contains(&point),
            undo: (a, 100 - a),
        }
    }

    /// Restore an active transaction and validate the resulting balances.
    ///
    /// `None` requires refusing normal use of the protected data.
    pub fn recover(&mut self) -> Option<(u32, u32)> {
        let pair = if self.active {
            self.undo
        } else {
            (self.a, self.b)
        };
        if pair.0.checked_add(pair.1) != Some(100) {
            return None;
        }
        self.a = pair.0;
        self.b = pair.1;
        self.active = false;
        Some(pair)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serial_transaction_oracle() {
        let mut count = 0;
        for a in 0..=100 {
            for amount in 0..=a {
                for point in 0..=5 {
                    let mut s = Snapshot::at_crash(a, amount, point);
                    let committed = u32::from(point == 5) * amount;
                    let expected = (a - committed, 100 - a + committed);
                    assert_eq!(s.recover(), Some(expected));
                    assert_eq!(s.recover(), Some(expected));
                    count += 1;
                }
            }
        }
        assert_eq!(count, 30_906);
    }

    #[test]
    fn invalid_recovery_evidence() {
        let mut s = Snapshot::at_crash(60, 10, 3);
        s.undo = (u32::MAX, 40);
        assert_eq!(s.recover(), None);
        assert!(s.active);
    }

    #[test]
    fn interrupted_repair_repeats_assignments() {
        let mut s = Snapshot::at_crash(60, 10, 4);
        s.a = s.undo.0;
        assert_eq!(s.recover(), Some((60, 40)));
        let mut committed = Snapshot::at_crash(60, 10, 5);
        assert_eq!(committed.recover(), Some((50, 50)));
    }
}
