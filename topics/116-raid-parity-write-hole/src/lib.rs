//! One serialized RAID 5 stripe update with atomic member writes.
//! The record names only the changed data and parity. Recovery assumes a valid,
//! durable record survives every interrupted installation until retirement.
//!
//! ```
//! use topic116_raid_parity_write_hole::{Record, rebuild, stripe};
//! let old = stripe(0x3c, 0x55);
//! let record = Record::partial(old, 0, 0xa6);
//! let mut members = old.map(Some);
//! record.install(&mut members, 1); // Only A reaches disk.
//! members[1] = None;
//! assert_eq!(rebuild(members)[1], 0xcf);
//! record.install(&mut members, 7);
//! assert_eq!(rebuild(members)[1], 0x55);
//! ```

/// The two data bytes followed by their parity byte.
pub fn stripe(a: u8, b: u8) -> [u8; 3] {
    [a, b, a ^ b]
}

/// New values needed to redo one update in this fixed stripe.
#[derive(Clone, Copy)]
pub struct Record([Option<u8>; 3]);

impl Record {
    /// Plan a single-data-member overwrite. Reads old data and old parity.
    ///
    /// # Panics
    /// The data member index must be 0 or 1.
    pub fn partial(old: [u8; 3], member: usize, value: u8) -> Self {
        assert!(member < 2);
        let mut changes = [None, None, Some(old[2] ^ old[member] ^ value)];
        changes[member] = Some(value);
        Self(changes)
    }

    /// Plan a full-stripe overwrite from caller-supplied data alone.
    pub fn full(a: u8, b: u8) -> Self {
        Self(stripe(a, b).map(Some))
    }

    /// Persist the selected writes on available members. Bit i selects member i.
    pub fn install(&self, members: &mut [Option<u8>; 3], durable: u8) {
        for (i, (member, change)) in members.iter_mut().zip(self.0).enumerate() {
            if durable & (1 << i) != 0 && member.is_some() && change.is_some() {
                *member = change;
            }
        }
    }
}

/// Reconstruct one missing member using the other two; all values remain
/// available when no member is missing. Survivors must agree for a correct rebuild.
///
/// # Panics
/// More than one missing member exceeds this stripe's redundancy.
pub fn rebuild(members: [Option<u8>; 3]) -> [u8; 3] {
    assert!(members.iter().filter(|m| m.is_none()).count() <= 1);
    let recovered = members.iter().flatten().fold(0, |acc, x| acc ^ x);
    members.map(|m| m.unwrap_or(recovered))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parity_first_also_damages_an_untouched_member() {
        let old = stripe(0x3c, 0x55);
        let record = Record::partial(old, 0, 0xa6);
        let mut members = old.map(Some);
        record.install(&mut members, 4);
        members[1] = None;
        assert_eq!(rebuild(members)[1], 0xcf);
    }

    #[test]
    fn full_stripe_crash_can_mix_generations() {
        let mut members = stripe(0x3c, 0x55).map(Some);
        let record = Record::full(0xa6, 0x11);
        record.install(&mut members, 3);
        members[0] = None;
        assert_eq!(rebuild(members)[0], 0x78);
        record.install(&mut members, 7);
        assert_eq!(rebuild(members), stripe(0xa6, 0x11));
    }
}
