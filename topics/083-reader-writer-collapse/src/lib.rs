//! Reader admission and consistent routing snapshots.
//!
//! The admission model uses logical time, not a platform fairness guarantee.
//! Run `cargo test -p reader-writer-collapse` and see `experiment/run.py`.

/// One immutable routing version. Both fields must be copied under one guard.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Route {
    /// Version identifier.
    pub generation: u64,
    /// Destination associated with this version.
    pub destination: u64,
}

impl Route {
    /// Construct a deterministic version; wrapping is part of this toy mapping.
    pub fn new(generation: u64) -> Self {
        Self {
            generation,
            destination: generation.wrapping_mul(100),
        }
    }
    /// Check the cross-field invariant.
    pub fn valid(self) -> bool {
        self.destination == self.generation.wrapping_mul(100)
    }
}

/// Compute request work from one consistent version; all arithmetic wraps.
#[inline(never)]
pub fn compute(route: Route, request: u64, rounds: u32) -> u64 {
    let mut value = route.generation ^ route.destination ^ request;
    for _ in 0..rounds {
        value = value
            .wrapping_mul(6364136223846793005)
            .rotate_left(13)
            .wrapping_add(1);
    }
    value
}

/// Return `(writer_start, late_reader_start)` for a three-request model.
///
/// Reader A runs from zero to `long_read`. The writer arrives before reader B,
/// and both arrive before A finishes. All durations are positive. Writer
/// preference gates B; reader preference admits B immediately.
///
/// # Panics
/// Panics for invalid input or time overflow.
///
/// ```
/// use reader_writer_collapse::admission;
/// assert_eq!(admission(true, 100, 10, 20, 10, 5), (100, 110));
/// assert_eq!(admission(false, 100, 10, 20, 10, 5), (100, 20));
/// ```
pub fn admission(
    prefer_writer: bool,
    long_read: u64,
    writer_at: u64,
    reader_at: u64,
    write_time: u64,
    read_time: u64,
) -> (u64, u64) {
    assert!(writer_at < reader_at && reader_at < long_read);
    assert!(write_time > 0 && read_time > 0);
    if prefer_writer {
        (
            long_read,
            long_read.checked_add(write_time).expect("time overflow"),
        )
    } else {
        (
            long_read.max(reader_at.checked_add(read_time).expect("time overflow")),
            reader_at,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Barrier, Mutex, RwLock};
    use std::thread;

    #[test]
    fn writer_gate_and_reader_extension() {
        assert_eq!(admission(true, 100, 10, 20, 10, 5), (100, 110));
        assert_eq!(admission(false, 100, 10, 20, 10, 200), (220, 20));
    }

    #[test]
    #[should_panic]
    fn rejects_wrong_arrival_order() {
        admission(true, 10, 5, 4, 1, 1);
    }

    #[test]
    #[should_panic]
    fn rejects_time_overflow() {
        admission(true, u64::MAX, 0, 1, 1, 1);
    }

    #[test]
    fn snapshot_survives_publication() {
        let table = RwLock::new(Route::new(7));
        let saved = *table.read().unwrap();
        *table.write().unwrap() = Route::new(8);
        assert_eq!(saved, Route::new(7));
        assert_eq!(*table.read().unwrap(), Route::new(8));
    }

    #[test]
    fn concurrent_versions_remain_whole() {
        let table = RwLock::new(Route::new(0));
        let start = Barrier::new(5);
        thread::scope(|scope| {
            scope.spawn(|| {
                start.wait();
                for generation in 1..=10_000 {
                    *table.write().unwrap() = Route::new(generation);
                }
            });
            for _ in 0..4 {
                scope.spawn(|| {
                    start.wait();
                    let mut previous = 0;
                    for _ in 0..10_000 {
                        let saved = *table.read().unwrap();
                        assert!(saved.valid() && saved.generation >= previous);
                        previous = saved.generation;
                        std::hint::black_box(compute(saved, 1, 8));
                    }
                });
            }
        });
        assert_eq!(*table.read().unwrap(), Route::new(10_000));
    }

    #[test]
    fn candidates_agree_over_requests() {
        for generation in [0, 7, u64::MAX] {
            let mutex = Mutex::new(Route::new(generation));
            let rw = RwLock::new(Route::new(generation));
            for rounds in [0, 1, 256] {
                for request in 0..32 {
                    let m = compute(*mutex.lock().unwrap(), request, rounds);
                    let r = compute(*rw.read().unwrap(), request, rounds);
                    let saved = *rw.read().unwrap();
                    assert_eq!(m, r);
                    assert_eq!(m, compute(saved, request, rounds));
                }
            }
        }
    }
}
