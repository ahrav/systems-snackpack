//! Runtime contracts and inspectable, safe batch kernels.
//!
//! `Arc` does not make a non-`Sync` payload safe to share:
//! ```compile_fail
//! use std::{cell::RefCell, sync::Arc};
//! fn send<T: Send>(_: T) {}
//! send(Arc::new(RefCell::new(1u64)));
//! ```
//! `Rc` cannot transfer its shared reference count across threads:
//! ```compile_fail
//! use std::rc::Rc;
//! fn send<T: Send>(_: T) {}
//! send(Rc::new(1u64));
//! ```

/// A transformation with an optional batch-level dispatch boundary.
pub trait Policy {
    /// Transform one value modulo 2^64.
    fn apply(&self, x: u64) -> u64;
    /// Sum transformed values modulo 2^64.
    fn batch(&self, xs: &[u64]) -> u64 {
        xs.iter().fold(0, |s, &x| s.wrapping_add(self.apply(x)))
    }
}
/// Add one runtime-selected constant.
pub struct Add(pub u64);
impl Policy for Add {
    fn apply(&self, x: u64) -> u64 {
        x.wrapping_add(self.0)
    }
}
/// Multiply, rotate, then xor using a runtime-selected constant.
pub struct Mix(pub u64);
impl Policy for Mix {
    fn apply(&self, x: u64) -> u64 {
        x.wrapping_mul(self.0).rotate_left(13) ^ 0xd1b54a32d192ed03
    }
}
/// A closed set of policy choices.
pub enum Choice {
    /// Addition policy.
    Add(Add),
    /// Multiply/rotate policy.
    Mix(Mix),
}
/// Concrete policy visible to the optimizer; one call per batch.
#[inline(never)]
pub fn generic<P: Policy>(p: &P, xs: &[u64]) -> u64 {
    p.batch(xs)
}
/// Match the closed policy choice once per batch.
#[inline(never)]
pub fn enumerated(p: &Choice, xs: &[u64]) -> u64 {
    match p {
        Choice::Add(p) => p.batch(xs),
        Choice::Mix(p) => p.batch(xs),
    }
}
/// Retain a potential virtual method call for each item.
#[inline(never)]
pub fn dyn_item(p: &dyn Policy, xs: &[u64]) -> u64 {
    xs.iter().fold(0, |s, &x| s.wrapping_add(p.apply(x)))
}
/// Dispatch once into a concrete policy's batch method.
#[inline(never)]
pub fn dyn_batch(p: &dyn Policy, xs: &[u64]) -> u64 {
    p.batch(xs)
}
/// Indexed dot product; rejects unequal lengths before processing.
///
/// # Panics
/// Panics if the input lengths differ.
#[inline(never)]
pub fn dot_index(a: &[u64], b: &[u64]) -> u64 {
    assert_eq!(a.len(), b.len());
    let mut sum = 0u64;
    for i in 0..a.len() {
        sum = sum.wrapping_add(a[i].wrapping_mul(b[i]));
    }
    sum
}
/// Zipped dot product with the same length and arithmetic contract.
///
/// # Panics
/// Panics if the input lengths differ.
#[inline(never)]
pub fn dot_zip(a: &[u64], b: &[u64]) -> u64 {
    assert_eq!(a.len(), b.len());
    a.iter()
        .zip(b)
        .fold(0u64, |s, (&x, &y)| s.wrapping_add(x.wrapping_mul(y)))
}
/// Deterministic input generator. The oracle uses arbitrary-precision integers.
pub fn data(n: usize, seed: u64) -> Vec<u64> {
    (0..n)
        .map(|i| {
            (i as u64)
                .wrapping_mul(0x9e3779b97f4a7c15)
                .wrapping_add(seed)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        cell::RefCell,
        mem::{align_of, size_of},
        num::NonZeroU64,
        panic::{AssertUnwindSafe, catch_unwind},
        sync::{Arc, Mutex},
    };

    #[test]
    #[allow(
        clippy::manual_rotate,
        reason = "Use a different formulation in the arithmetic oracle"
    )]
    fn kernels_match_wide_arithmetic_at_boundaries() {
        for n in [0, 1, 2, 3, 7, 8, 15, 16, 31, 32, 33, 129, 8192] {
            let xs = data(n, u64::MAX);
            for k in [0, 1, 7, u64::MAX] {
                let add = Add(k);
                let mix = Mix(k);
                // Independent arithmetic formulation, without production apply().
                let add_expected = xs.iter().fold(0u128, |s, &x| {
                    (s + ((x as u128 + k as u128) & u64::MAX as u128)) & u64::MAX as u128
                }) as u64;
                let mix_expected = xs.iter().fold(0u64, |s, &x| {
                    let y = (x as u128 * k as u128) as u64;
                    s.wrapping_add(((y << 13) | (y >> 51)) ^ 0xd1b54a32d192ed03)
                });
                for (p, e, c) in [
                    (&add as &dyn Policy, add_expected, Choice::Add(Add(k))),
                    (&mix as &dyn Policy, mix_expected, Choice::Mix(Mix(k))),
                ] {
                    assert_eq!(dyn_item(p, &xs), e);
                    assert_eq!(dyn_batch(p, &xs), e);
                    assert_eq!(enumerated(&c, &xs), e);
                }
                assert_eq!(generic(&add, &xs), add_expected);
                assert_eq!(generic(&mix, &xs), mix_expected);
            }
            let ys = data(n, 17);
            let expected = xs.iter().zip(&ys).fold(0u128, |s, (&x, &y)| {
                (s + (x as u128 * y as u128)) & u64::MAX as u128
            }) as u64;
            assert_eq!(dot_index(&xs, &ys), expected);
            assert_eq!(dot_zip(&xs, &ys), expected);
        }
    }
    #[test]
    fn unequal_inputs_reject_in_both_directions() {
        for (a, b) in [
            (&[1, 2][..], &[3][..]),
            (&[1][..], &[2, 3][..]),
            (&[][..], &[1][..]),
        ] {
            assert!(catch_unwind(|| dot_index(a, b)).is_err());
            assert!(catch_unwind(|| dot_zip(a, b)).is_err());
        }
    }
    #[test]
    fn documented_option_layout() {
        assert_eq!(size_of::<Option<NonZeroU64>>(), size_of::<u64>());
        assert_eq!(align_of::<Option<NonZeroU64>>(), align_of::<u64>());
        assert_eq!(NonZeroU64::new(0), None);
    }
    struct Guard<'a>(&'a RefCell<Vec<&'static str>>, &'static str);
    impl Drop for Guard<'_> {
        fn drop(&mut self) {
            self.0.borrow_mut().push(self.1);
        }
    }
    #[test]
    fn unwind_drops_live_locals_in_reverse_order() {
        let log = RefCell::new(Vec::new());
        let outcome = catch_unwind(AssertUnwindSafe(|| {
            let _first = Guard(&log, "first");
            let _second = Guard(&log, "second");
            panic!("intentional");
        }));
        assert!(outcome.is_err());
        assert_eq!(*log.borrow(), ["second", "first"]);
    }
    #[test]
    fn fields_drop_in_declaration_order() {
        struct Pair<'a> {
            _first: Guard<'a>,
            _second: Guard<'a>,
        }
        let log = RefCell::new(Vec::new());
        drop(Pair {
            _first: Guard(&log, "first"),
            _second: Guard(&log, "second"),
        });
        assert_eq!(*log.borrow(), ["first", "second"]);
    }
    #[test]
    fn share_only_with_a_suitable_payload() {
        fn send_sync<T: Send + Sync>() {}
        send_sync::<Arc<Vec<u64>>>();
        send_sync::<Arc<Mutex<RefCell<u64>>>>();
        let xs = Arc::new(vec![1u64, 2, 3]);
        assert_eq!(
            std::thread::spawn(move || xs.iter().sum::<u64>())
                .join()
                .unwrap(),
            6
        );
    }
}
