//! Byte admission with bounded pause credit and partial-write accounting.
//!
//! This is an application admission model, not a TCP or QUIC implementation.
//! One owner supplies a nondecreasing nanosecond clock and a nonblocking writer.
//! Credit limits bytes accepted by that writer, not packet departure or delivery.
//! The time envelope uses the supplied admission-check timestamps. A pause
//! inside an attempt can change actual acceptance spacing; this model does not
//! make the clock check and writer execution atomic.
//!
//! ```
//! use tcp_quic_application_pacing::{Admission, Bucket};
//! let mut bucket = Bucket::new(12_000_000, 2_400, 0).unwrap();
//! assert_eq!(bucket.try_write(0, &[0; 1_200], |b| Ok(b.len())).unwrap(),
//!            Admission::Accepted(1_200));
//! ```

use std::io;

const NS_PER_SECOND: u128 = 1_000_000_000;

/// The result of one nonblocking admission attempt.
#[derive(Debug, PartialEq, Eq)]
pub enum Admission {
    /// There was no input. The writer was not called.
    Empty,
    /// No whole byte of credit was available. The writer was not called.
    PacingLimited,
    /// The writer returned `WouldBlock`; no credit was charged.
    WriteBlocked,
    /// The writer accepted this many bytes; exactly those bytes were charged.
    Accepted(usize),
}

/// A fixed-rate bucket that starts full and retains fractional byte credit.
///
/// The maximum burst is `capacity` bytes at this admission boundary. Pending
/// producer bytes need a separate bound. A lower transport layer can buffer,
/// segment, retransmit, or delay accepted data.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Bucket {
    rate: u64,
    capacity: u64,
    credit: u128,
    last_ns: u64,
}

impl Bucket {
    /// Creates a full bucket, using bytes per second and bytes respectively.
    ///
    /// Zero rate or capacity returns `InvalidInput`. Time is relative to the
    /// caller's monotonic clock origin; it is not a wall-clock timestamp.
    pub fn new(rate: u64, capacity: u64, now_ns: u64) -> io::Result<Self> {
        if rate == 0 || capacity == 0 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "zero rate or capacity",
            ));
        }
        Ok(Self {
            rate,
            capacity,
            credit: u128::from(capacity) * NS_PER_SECOND,
            last_ns: now_ns,
        })
    }

    /// Offers a credit-limited prefix to a single nonblocking writer.
    ///
    /// The writer must report the actual accepted prefix length. Retry only
    /// the unaccepted suffix after `Accepted`. Wait for writable readiness
    /// after `WriteBlocked`, and for credit after `PacingLimited`.
    ///
    /// Clock regression fails before changing state or invoking the writer.
    /// Other writer errors preserve the refilled credit. `Ok(0)` is `WriteZero`.
    /// An impossible count larger than the offered prefix empties the bucket
    /// and returns `InvalidData`; the caller must stop that broken writer.
    pub fn try_write(
        &mut self,
        now_ns: u64,
        pending: &[u8],
        writer: impl FnOnce(&[u8]) -> io::Result<usize>,
    ) -> io::Result<Admission> {
        let elapsed = now_ns
            .checked_sub(self.last_ns)
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "clock regressed"))?;
        let refill = u128::from(elapsed) * u128::from(self.rate);
        self.credit = self
            .credit
            .saturating_add(refill)
            .min(u128::from(self.capacity) * NS_PER_SECOND);
        self.last_ns = now_ns;
        if pending.is_empty() {
            return Ok(Admission::Empty);
        }
        let whole = self.credit / NS_PER_SECOND;
        let offer = whole.min(pending.len() as u128) as usize;
        if offer == 0 {
            return Ok(Admission::PacingLimited);
        }
        let accepted = match writer(&pending[..offer]) {
            Err(e) if e.kind() == io::ErrorKind::WouldBlock => return Ok(Admission::WriteBlocked),
            result => result?,
        };
        if accepted > offer {
            self.credit = 0;
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "writer exceeded offered prefix",
            ));
        }
        if accepted == 0 {
            return Err(io::Error::from(io::ErrorKind::WriteZero));
        }
        self.credit -= (accepted as u128) * NS_PER_SECOND;
        Ok(Admission::Accepted(accepted))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn partial_write_preserves_suffix_and_charges_only_accepted_bytes() {
        let mut b = Bucket::new(1, 4, 0).unwrap();
        let data = [1, 2, 3, 4, 5];
        assert_eq!(
            b.try_write(0, &data, |p| {
                assert_eq!(p, &[1, 2, 3, 4]);
                Ok(1)
            })
            .unwrap(),
            Admission::Accepted(1)
        );
        assert_eq!(
            b.try_write(0, &data[1..], |p| {
                assert_eq!(p, &[2, 3, 4]);
                Ok(3)
            })
            .unwrap(),
            Admission::Accepted(3)
        );
        assert_eq!(
            b.try_write(0, &data[4..], |_| panic!("no credit")).unwrap(),
            Admission::PacingLimited
        );
        assert_eq!(
            b.try_write(1_000_000_000, &data[4..], |p| {
                assert_eq!(p, &[5]);
                Ok(1)
            })
            .unwrap(),
            Admission::Accepted(1)
        );
    }

    #[test]
    fn would_block_does_not_consume_credit() {
        let mut b = Bucket::new(12_000_000, 2400, 0).unwrap();
        assert_eq!(
            b.try_write(0, &[0; 1200], |_| Err(io::ErrorKind::WouldBlock.into()))
                .unwrap(),
            Admission::WriteBlocked
        );
        assert_eq!(
            b.try_write(0, &[0; 3000], |p| Ok(p.len())).unwrap(),
            Admission::Accepted(2400)
        );
    }

    #[test]
    fn fractional_refill_survives_frequent_polls() {
        let mut b = Bucket::new(3, 1, 0).unwrap();
        b.try_write(0, &[0], |_| Ok(1)).unwrap();
        for ns in [100_000_000, 200_000_000, 300_000_000, 333_333_333] {
            assert_eq!(
                b.try_write(ns, &[0], |_| panic!("fraction only")).unwrap(),
                Admission::PacingLimited
            );
        }
        assert_eq!(
            b.try_write(333_333_334, &[0], |_| Ok(1)).unwrap(),
            Admission::Accepted(1)
        );
    }

    #[test]
    fn regression_leaves_state_and_writer_untouched() {
        let mut b = Bucket::new(1, 2, 42).unwrap();
        let before = b.clone();
        assert_eq!(
            b.try_write(41, &[0], |_| panic!("invalid time"))
                .unwrap_err()
                .kind(),
            io::ErrorKind::InvalidInput
        );
        assert_eq!(b, before);
    }

    #[test]
    fn pause_and_extreme_arithmetic_never_exceed_capacity() {
        let mut b = Bucket::new(u64::MAX, u64::MAX, 0).unwrap();
        assert_eq!(
            b.try_write(u64::MAX, &[0; 3], |p| Ok(p.len())).unwrap(),
            Admission::Accepted(3)
        );
        let mut b = Bucket::new(12_000_000, 2400, 0).unwrap();
        b.try_write(0, &[0; 2400], |p| Ok(p.len())).unwrap();
        assert_eq!(
            b.try_write(u64::MAX, &[0; 3000], |p| Ok(p.len())).unwrap(),
            Admission::Accepted(2400)
        );
        assert_eq!(
            b.try_write(u64::MAX, &[0], |_| panic!("cap consumed"))
                .unwrap(),
            Admission::PacingLimited
        );
    }

    #[test]
    fn invalid_configuration_empty_input_and_writer_errors() {
        assert!(Bucket::new(0, 1, 0).is_err());
        assert!(Bucket::new(1, 0, 0).is_err());
        let mut b = Bucket::new(1, 2, 0).unwrap();
        assert_eq!(
            b.try_write(0, &[], |_| panic!("empty")).unwrap(),
            Admission::Empty
        );
        assert_eq!(
            b.try_write(0, &[0], |_| Ok(0)).unwrap_err().kind(),
            io::ErrorKind::WriteZero
        );
        assert_eq!(
            b.try_write(0, &[0], |_| Err(io::ErrorKind::Interrupted.into()))
                .unwrap_err()
                .kind(),
            io::ErrorKind::Interrupted
        );
        assert_eq!(
            b.try_write(0, &[0; 2], |_| Ok(3)).unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
        assert_eq!(
            b.try_write(0, &[0], |_| panic!("invalid writer emptied credit"))
                .unwrap(),
            Admission::PacingLimited
        );
    }

    #[test]
    fn every_interval_obeys_the_byte_envelope_under_partial_and_blocked_writes() {
        let mut b = Bucket::new(12_000_000, 2400, 0).unwrap();
        let mut events = Vec::new();
        for tick in 0_u64..200 {
            if (20..70).contains(&tick) {
                continue;
            }
            let now = tick * 100_000;
            for attempt in 0..5 {
                let outcome = b
                    .try_write(now, &[0; 1200], |p| {
                        if (tick + attempt) % 7 == 0 {
                            return Err(io::ErrorKind::WouldBlock.into());
                        }
                        Ok(p.len().min(if attempt % 2 == 0 { 317 } else { 1200 }))
                    })
                    .unwrap();
                if let Admission::Accepted(bytes) = outcome {
                    events.push((now, bytes as u128));
                }
            }
        }
        assert!(events.len() > 200);
        for first in 0..events.len() {
            let mut bytes = 0;
            for last in first..events.len() {
                bytes += events[last].1;
                let elapsed = u128::from(events[last].0 - events[first].0);
                assert!(bytes * NS_PER_SECOND <= 2400 * NS_PER_SECOND + 12_000_000 * elapsed);
            }
        }
    }
}
