//! Finite packet-buffer contracts, without sockets, DMA, or concurrent rings.
//!
//! A frame has one owner. Consuming a transmit descriptor does not return it.
//! These sequential transitions are an application ledger, not an AF_XDP driver.
//!
//! ```
//! use topic064_kernel_bypass::{Pool, State};
//! let mut pool = Pool::new(4);
//! pool.transmit(&[0], 1).unwrap();
//! pool.consume_tx(0).unwrap();
//! assert!(pool.fill(0).is_err());
//! pool.complete(0).unwrap();
//! pool.reclaim(0).unwrap();
//! assert_eq!(pool.state(0), Some(State::App));
//! ```

/// Mutually exclusive locations in the abstract frame ledger.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum State {
    /// Application owns the frame and may offer it to one path.
    App,
    /// Frame offered for receive; application must not modify it.
    Fill,
    /// Receive descriptor available but not yet consumed by the application.
    Rx,
    /// Published transmit descriptor still pending consumption.
    Tx,
    /// Transmit descriptor consumed, frame still unavailable to application.
    InFlight,
    /// Completion available but not yet reclaimed by application.
    Complete,
}

/// Rejected ledger operation. No rejected operation changes the ledger.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Error {
    /// Unknown frame or malformed buffer geometry.
    Invalid,
    /// Frame is held by another stage.
    Ownership,
    /// A burst or packet names one frame twice.
    Duplicate,
    /// A packet exceeds the configured frame bound.
    TooManyFrames,
}

/// Single-threaded ledger over a fixed number of frames.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Pool {
    states: Vec<State>,
}

impl Pool {
    /// Create application-owned frames numbered from zero.
    pub fn new(frames: usize) -> Self {
        Self {
            states: vec![State::App; frames],
        }
    }

    /// Read the ledger; an unknown frame returns `None`.
    pub fn state(&self, frame: usize) -> Option<State> {
        self.states.get(frame).copied()
    }

    fn move_frame(&mut self, frame: usize, from: State, to: State) -> Result<(), Error> {
        let state = self.states.get_mut(frame).ok_or(Error::Invalid)?;
        if *state != from {
            return Err(Error::Ownership);
        }
        *state = to;
        Ok(())
    }

    /// Offer one application-owned frame to receive.
    pub fn fill(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::App, State::Fill)
    }

    /// Model the driver publishing one receive descriptor.
    pub fn publish_rx(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::Fill, State::Rx)
    }

    /// Model consuming a receive descriptor and taking frame ownership.
    pub fn receive(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::Rx, State::App)
    }

    /// Transfer an accepted prefix; return the suffix still owned by the caller.
    ///
    /// The caller supplies a simulated burst result. This does not invoke DPDK.
    /// Every offered frame must be distinct and application-owned, including the
    /// unaccepted suffix. Invalid input fails before any ownership transfer.
    pub fn transmit<'a>(
        &mut self,
        frames: &'a [usize],
        accepted: usize,
    ) -> Result<&'a [usize], Error> {
        if accepted > frames.len() {
            return Err(Error::Invalid);
        }
        for (i, &frame) in frames.iter().enumerate() {
            match self.state(frame) {
                None => return Err(Error::Invalid),
                Some(State::App) => (),
                Some(_) => return Err(Error::Ownership),
            }
            if frames[..i].contains(&frame) {
                return Err(Error::Duplicate);
            }
        }
        for &frame in &frames[..accepted] {
            self.states[frame] = State::Tx;
        }
        Ok(&frames[accepted..])
    }

    /// Consume a transmit descriptor without returning its frame.
    pub fn consume_tx(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::Tx, State::InFlight)
    }

    /// Model an externally supplied completion, not successful remote delivery.
    pub fn complete(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::InFlight, State::Complete)
    }

    /// Consume a completion and return the frame to application ownership.
    pub fn reclaim(&mut self, frame: usize) -> Result<(), Error> {
        self.move_frame(frame, State::Complete, State::App)
    }
}

/// Normalize an aligned UMEM address to its chunk identity.
///
/// Chunk size is 2048 or 4096 bytes, matching `XDP_UMEM_REG` in the pinned
/// Linux v6.12 AF_XDP reference. Unaligned mode and packed address flags are
/// outside this helper's contract.
pub fn aligned_frame(address: usize, bytes: usize, chunk: usize) -> Result<usize, Error> {
    if !matches!(chunk, 2048 | 4096)
        || bytes == 0
        || !bytes.is_multiple_of(chunk)
        || address >= bytes
    {
        return Err(Error::Invalid);
    }
    Ok(address / chunk)
}

/// Whether a producer must request progress after publishing work.
///
/// Only models `XDP_USE_NEED_WAKEUP` enabled operation. The real helper reads
/// the actual shared flag. This predicate does not implement its ordering.
#[inline(never)]
pub fn wakeup_required(work_published: bool, needs_wakeup: bool) -> bool {
    work_published && needs_wakeup
}

/// Bounded frame-list assembly across application batch boundaries.
///
/// This owns identifiers, not payloads. The caller must retain every referenced
/// payload until packet processing ends; an error leaves pending frames intact.
#[derive(Debug, PartialEq, Eq)]
pub struct Assembly {
    pending: Vec<usize>,
    limit: usize,
}

impl Assembly {
    /// Set a positive maximum frame count per packet.
    pub fn new(limit: usize) -> Result<Self, Error> {
        if limit == 0 {
            return Err(Error::Invalid);
        }
        Ok(Self {
            pending: Vec::new(),
            limit,
        })
    }

    /// Append a frame; return identifiers only when the final frame arrives.
    pub fn push(&mut self, frame: usize, continues: bool) -> Result<Option<Vec<usize>>, Error> {
        if self.pending.contains(&frame) {
            return Err(Error::Duplicate);
        }
        if self.pending.len() == self.limit {
            return Err(Error::TooManyFrames);
        }
        self.pending.push(frame);
        if continues {
            Ok(None)
        } else {
            Ok(Some(std::mem::take(&mut self.pending)))
        }
    }

    /// Number of frames whose payloads the caller must still retain.
    pub fn pending(&self) -> usize {
        self.pending.len()
    }

    /// Abort a malformed/incomplete packet and return every retained identifier.
    pub fn abort(&mut self) -> Vec<usize> {
        std::mem::take(&mut self.pending)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn completion_is_required_after_descriptor_consumption() {
        let mut p = Pool::new(1);
        p.transmit(&[0], 1).unwrap();
        assert_eq!(p.fill(0), Err(Error::Ownership));
        p.consume_tx(0).unwrap();
        assert_eq!(p.fill(0), Err(Error::Ownership));
        assert_eq!(p.reclaim(0), Err(Error::Ownership));
        p.complete(0).unwrap();
        assert_eq!(p.fill(0), Err(Error::Ownership));
        p.reclaim(0).unwrap();
        p.fill(0).unwrap();
    }

    #[test]
    fn receive_needs_supply_and_consumption() {
        let mut p = Pool::new(1);
        assert_eq!(p.publish_rx(0), Err(Error::Ownership));
        p.fill(0).unwrap();
        assert_eq!(p.fill(0), Err(Error::Ownership));
        p.publish_rx(0).unwrap();
        assert_eq!(p.transmit(&[0], 1), Err(Error::Ownership));
        p.receive(0).unwrap();
        p.transmit(&[0], 1).unwrap();
    }

    #[test]
    fn every_partial_transmit_preserves_unsent_suffix() {
        let frames: Vec<_> = (0..32).collect();
        for accepted in 0..=32 {
            let mut p = Pool::new(32);
            assert_eq!(p.transmit(&frames, accepted).unwrap(), &frames[accepted..]);
            for id in 0..32 {
                assert_eq!(
                    p.state(id),
                    Some(if id < accepted { State::Tx } else { State::App })
                );
            }
        }
    }

    #[test]
    fn rejected_bursts_are_atomic() {
        let mut p = Pool::new(4);
        let before = p.clone();
        for (ids, accepted, error) in [
            (vec![0, 1], 3, Error::Invalid),
            (vec![0, 4], 1, Error::Invalid),
            (vec![0, 0], 1, Error::Duplicate),
        ] {
            assert_eq!(p.transmit(&ids, accepted), Err(error));
            assert_eq!(p, before);
        }
        p.fill(1).unwrap();
        let before = p.clone();
        assert_eq!(p.transmit(&[0, 1], 1), Err(Error::Ownership));
        assert_eq!(p, before);
    }

    #[test]
    fn aligned_alias_cannot_be_assigned_twice() {
        let a = aligned_frame(2048, 8192, 2048).unwrap();
        let b = aligned_frame(2050, 8192, 2048).unwrap();
        assert_eq!(a, b);
        let mut p = Pool::new(4);
        p.fill(a).unwrap();
        assert_eq!(p.transmit(&[b], 1), Err(Error::Ownership));
        for (addr, bytes, chunk) in [
            (8192, 8192, 2048),
            (0, 8192, 0),
            (0, 8192, 3),
            (0, 8191, 2048),
            (0, 8192, 1024),
            (0, 16384, 8192),
        ] {
            assert_eq!(aligned_frame(addr, bytes, chunk), Err(Error::Invalid));
        }
    }

    #[test]
    fn packet_crosses_batch_without_premature_return() {
        let mut a = Assembly::new(4).unwrap();
        assert_eq!(a.push(0, true), Ok(None));
        assert_eq!(a.push(1, true), Ok(None));
        assert_eq!(a.pending(), 2);
        // A later peek batch contains the final frame and another packet.
        assert_eq!(a.push(2, false), Ok(Some(vec![0, 1, 2])));
        assert_eq!(a.push(3, false), Ok(Some(vec![3])));
        assert_eq!(a.pending(), 0);
    }

    #[test]
    fn malformed_packet_retains_frames_until_explicit_abort() {
        let mut a = Assembly::new(2).unwrap();
        a.push(0, true).unwrap();
        assert_eq!(a.push(0, false), Err(Error::Duplicate));
        a.push(1, true).unwrap();
        assert_eq!(a.push(2, false), Err(Error::TooManyFrames));
        assert_eq!(a.abort(), vec![0, 1]);
        assert_eq!(a.push(2, false), Ok(Some(vec![2])));
        assert_eq!(Assembly::new(0), Err(Error::Invalid));
    }

    #[test]
    fn wakeup_flag_controls_explicit_progress_request() {
        assert!(wakeup_required(true, true));
        assert!(!wakeup_required(true, false));
        assert!(!wakeup_required(false, true));
        assert!(!wakeup_required(false, false));
    }

    #[test]
    fn recycled_frames_survive_repeated_complete_cycles() {
        let mut p = Pool::new(32);
        for _ in 0..100 {
            for id in 0..32 {
                p.fill(id).unwrap();
                p.publish_rx(id).unwrap();
                p.receive(id).unwrap();
                p.transmit(&[id], 1).unwrap();
                p.consume_tx(id).unwrap();
                p.complete(id).unwrap();
                p.reclaim(id).unwrap();
            }
        }
        assert_eq!(p, Pool::new(32));
    }
}
