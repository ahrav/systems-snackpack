use std::{cell::RefCell, mem::size_of, num::NonZeroU64, panic, sync::Arc};

trait Policy {
    fn apply(&self, x: u64) -> u64;
    fn batch(&self, xs: &[u64]) -> u64 {
        xs.iter().fold(0, |s, &x| s.wrapping_add(self.apply(x)))
    }
}
struct Add(u64);
impl Policy for Add {
    fn apply(&self, x: u64) -> u64 {
        x.wrapping_add(self.0)
    }
}
fn generic<P: Policy>(p: &P, xs: &[u64]) -> u64 {
    p.batch(xs)
}
fn per_item(p: &dyn Policy, xs: &[u64]) -> u64 {
    xs.iter().fold(0, |s, &x| s.wrapping_add(p.apply(x)))
}
fn dot_index(a: &[u64], b: &[u64]) -> u64 {
    assert_eq!(a.len(), b.len());
    let mut s = 0u64;
    for i in 0..a.len() {
        s = s.wrapping_add(a[i].wrapping_mul(b[i]));
    }
    s
}
fn dot_zip(a: &[u64], b: &[u64]) -> u64 {
    assert_eq!(a.len(), b.len()); // zip alone would silently truncate.
    a.iter()
        .zip(b)
        .fold(0u64, |s, (&x, &y)| s.wrapping_add(x.wrapping_mul(y)))
}
struct Guard<'a>(&'a RefCell<Vec<&'static str>>, &'static str);
impl Drop for Guard<'_> {
    fn drop(&mut self) {
        self.0.borrow_mut().push(self.1);
    }
}
fn main() {
    let xs = [1, 2, 3];
    let p = Add(7);
    assert_eq!(generic(&p, &xs), 27);
    assert_eq!(per_item(&p, &xs), 27);
    assert_eq!((&p as &dyn Policy).batch(&xs), 27);
    assert_eq!(dot_index(&xs, &xs), 14);
    assert_eq!(dot_zip(&xs, &xs), 14);
    assert_eq!(size_of::<Option<NonZeroU64>>(), size_of::<u64>());
    println!(
        "optional nonzero ID: {} bytes",
        size_of::<Option<NonZeroU64>>()
    );
    let log = RefCell::new(Vec::new());
    let outcome = panic::catch_unwind(panic::AssertUnwindSafe(|| {
        let _first = Guard(&log, "first");
        let _second = Guard(&log, "second");
        panic!("intentional lesson panic");
    }));
    assert!(outcome.is_err());
    assert_eq!(*log.borrow(), ["second", "first"]);
    println!("unwind cleanup: {:?}", log.borrow());
    let shared = Arc::new(xs);
    assert_eq!(
        std::thread::spawn(move || shared.iter().sum::<u64>())
            .join()
            .unwrap(),
        6
    );
    println!("dispatch=27 dot=14 thread_sum=6");
}
