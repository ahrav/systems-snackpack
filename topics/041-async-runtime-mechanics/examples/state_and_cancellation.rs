//! Measures future-state liveness and a cancellation boundary without an executor.
//!
//! The state probe builds two futures around the same 4,096-byte workload. One
//! keeps the array live across `YieldOnce`; the other computes its checksum
//! before suspension. [`std::mem::size_of_val`] reports compiler-, target-, and
//! profile-specific frame sizes. For this experiment, the size assertions accept
//! only a candidate where the across-suspension frame is at least 4,096 bytes
//! and the scoped frame is less than 4,096 bytes. Those thresholds are measured
//! candidate checks, not portable Rust layout guarantees.
//!
//! The cancellation probe polls both race branches once, completes the left
//! branch, then drops the pending right branch. `UnsafeTake` removes its item
//! before returning `Poll::Pending`, so dropping it loses the item. `SafeTake`
//! returns `Poll::Pending` first, so dropping it leaves the item queued.
//!
//! The manual driver polls again immediately after `Poll::Pending`; wake calls
//! are counted but never schedule work. The output describes compiler layout
//! and these fixed poll sequences, not runtime timing or executor behavior.

use std::cell::RefCell;
use std::collections::VecDeque;
use std::future::Future;
use std::hint::black_box;
use std::mem::size_of_val;
use std::pin::Pin;
use std::rc::Rc;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::task::{Context, Poll, Wake, Waker};

// A 4 KiB payload makes across-suspension liveness dominate fixed future state.
const BUFFER_BYTES: usize = 4096;

// Counts wake calls without scheduling; callers perform every follow-up poll.
struct CountWake {
    wakes: AtomicUsize,
}

impl CountWake {
    fn new() -> Arc<Self> {
        Arc::new(Self {
            wakes: AtomicUsize::new(0),
        })
    }
}

impl Wake for CountWake {
    fn wake(self: Arc<Self>) {
        self.wakes.fetch_add(1, Ordering::Relaxed);
    }

    fn wake_by_ref(self: &Arc<Self>) {
        self.wakes.fetch_add(1, Ordering::Relaxed);
    }
}

// Returns `Pending` after self-waking on its first poll, then returns `Ready`.
struct YieldOnce {
    yielded: bool,
}

impl YieldOnce {
    fn new() -> Self {
        Self { yielded: false }
    }
}

impl Future for YieldOnce {
    type Output = ();

    #[inline(never)]
    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<()> {
        if self.yielded {
            Poll::Ready(())
        } else {
            self.yielded = true;
            cx.waker().wake_by_ref();
            Poll::Pending
        }
    }
}

#[inline(never)]
fn fill_bytes(bytes: &mut [u8; BUFFER_BYTES], seed: u8) {
    for (index, byte) in bytes.iter_mut().enumerate() {
        *byte = seed.wrapping_add((index as u8).wrapping_mul(17));
    }
}

#[inline(never)]
fn checksum(bytes: &[u8; BUFFER_BYTES]) -> u64 {
    // The checksum is a correctness oracle; the example never interprets its timing.
    let mut sum = 0_u64;
    for byte in bytes {
        sum = sum.wrapping_add(u64::from(black_box(*byte)));
    }
    black_box(sum)
}

// Keeps the 4 KiB array live in the future across its only suspension point.
async fn holds_large_value_across_yield(seed: u8) -> u64 {
    let mut bytes = [0_u8; BUFFER_BYTES];
    fill_bytes(&mut bytes, seed);
    black_box(&mut bytes);
    YieldOnce::new().await;
    checksum(black_box(&bytes))
}

// Ends the array's scope before suspension. The user value retained across it is
// `sum`; the future also retains its await and compiler state.
async fn finishes_large_value_before_yield(seed: u8) -> u64 {
    let sum = {
        let mut bytes = [0_u8; BUFFER_BYTES];
        fill_bytes(&mut bytes, seed);
        black_box(&mut bytes);
        checksum(black_box(&bytes))
    };
    YieldOnce::new().await;
    sum
}

type Queue = Rc<RefCell<VecDeque<u64>>>;

// Takes from a probe-owned nonempty queue before yielding; cancellation loses the item.
struct UnsafeTake {
    queue: Queue,
    staged: Option<u64>,
    yielded: bool,
}

impl UnsafeTake {
    fn new(queue: Queue) -> Self {
        Self {
            queue,
            staged: None,
            yielded: false,
        }
    }
}

impl Future for UnsafeTake {
    type Output = u64;

    #[inline(never)]
    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<u64> {
        if !self.yielded {
            // The irreversible step occurs before Pending. If this future loses
            // a race and is dropped now, the staged queue item is lost.
            let staged = self.queue.borrow_mut().pop_front();
            self.staged = staged;
            self.yielded = true;
            cx.waker().wake_by_ref();
            return Poll::Pending;
        }

        Poll::Ready(self.staged.take().expect("unsafe queue had one item"))
    }
}

// Takes from a probe-owned nonempty queue after yielding; cancellation preserves it.
struct SafeTake {
    queue: Queue,
    yielded: bool,
}

impl SafeTake {
    fn new(queue: Queue) -> Self {
        Self {
            queue,
            yielded: false,
        }
    }
}

impl Future for SafeTake {
    type Output = u64;

    #[inline(never)]
    fn poll(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<u64> {
        if !self.yielded {
            // Pending is returned before the irreversible step. Cancellation
            // at this boundary leaves the queue unchanged.
            self.yielded = true;
            cx.waker().wake_by_ref();
            return Poll::Pending;
        }

        Poll::Ready(
            self.queue
                .borrow_mut()
                .pop_front()
                .expect("safe queue had one item"),
        )
    }
}

#[inline(never)]
fn poll_once<F: Future>(future: Pin<&mut F>, cx: &mut Context<'_>) -> Poll<F::Output> {
    future.poll(cx)
}

// Polls until `Ready`, immediately retrying after `Pending` independent of wakes.
fn drive_u64<F: Future<Output = u64>>(future: F, cx: &mut Context<'_>) -> (u64, usize) {
    let mut future = Box::pin(future);
    let mut polls = 0;
    loop {
        polls += 1;
        match poll_once(future.as_mut(), cx) {
            Poll::Ready(value) => return (value, polls),
            Poll::Pending => {}
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
struct RaceResult {
    winner: u64,
    left_remaining: usize,
    right_remaining: usize,
}

#[inline(never)]
fn run_unsafe_race(cx: &mut Context<'_>) -> RaceResult {
    let left = Rc::new(RefCell::new(VecDeque::from([11_u64])));
    let right = Rc::new(RefCell::new(VecDeque::from([22_u64])));
    let mut left_future = Box::pin(UnsafeTake::new(Rc::clone(&left)));
    let mut right_future = Box::pin(UnsafeTake::new(Rc::clone(&right)));

    assert!(poll_once(left_future.as_mut(), cx).is_pending());
    assert!(poll_once(right_future.as_mut(), cx).is_pending());
    let winner = match poll_once(left_future.as_mut(), cx) {
        Poll::Ready(value) => value,
        Poll::Pending => panic!("left unsafe future should now be ready"),
    };
    drop(right_future);

    RaceResult {
        winner,
        left_remaining: left.borrow().len(),
        right_remaining: right.borrow().len(),
    }
}

#[inline(never)]
fn run_safe_race(cx: &mut Context<'_>) -> RaceResult {
    let left = Rc::new(RefCell::new(VecDeque::from([11_u64])));
    let right = Rc::new(RefCell::new(VecDeque::from([22_u64])));
    let mut left_future = Box::pin(SafeTake::new(Rc::clone(&left)));
    let mut right_future = Box::pin(SafeTake::new(Rc::clone(&right)));

    assert!(poll_once(left_future.as_mut(), cx).is_pending());
    assert!(poll_once(right_future.as_mut(), cx).is_pending());
    let winner = match poll_once(left_future.as_mut(), cx) {
        Poll::Ready(value) => value,
        Poll::Pending => panic!("left safe future should now be ready"),
    };
    drop(right_future);

    RaceResult {
        winner,
        left_remaining: left.borrow().len(),
        right_remaining: right.borrow().len(),
    }
}

fn main() {
    let wake = CountWake::new();
    let waker = Waker::from(Arc::clone(&wake));
    let mut cx = Context::from_waker(&waker);

    let large_future = holds_large_value_across_yield(3);
    let small_future = finishes_large_value_before_yield(3);
    let large_size = size_of_val(&large_future);
    let small_size = size_of_val(&small_future);

    let (large_sum, large_polls) = drive_u64(large_future, &mut cx);
    let (small_sum, small_polls) = drive_u64(small_future, &mut cx);
    assert_eq!(large_sum, small_sum);
    assert_eq!(large_sum, 522_240);
    assert_eq!(large_polls, 2);
    assert_eq!(small_polls, 2);
    assert!(large_size >= BUFFER_BYTES);
    assert!(small_size < BUFFER_BYTES);

    let unsafe_result = run_unsafe_race(&mut cx);
    let safe_result = run_safe_race(&mut cx);
    assert_eq!(
        unsafe_result,
        RaceResult {
            winner: 11,
            left_remaining: 0,
            right_remaining: 0,
        }
    );
    assert_eq!(
        safe_result,
        RaceResult {
            winner: 11,
            left_remaining: 0,
            right_remaining: 1,
        }
    );

    println!("experiment=topic41-async-state-and-cancellation");
    println!("buffer_bytes={BUFFER_BYTES}");
    println!("future_large_bytes={large_size}");
    println!("future_small_bytes={small_size}");
    println!("future_size_delta_bytes={}", large_size - small_size);
    println!("checksum={large_sum}");
    println!("large_polls={large_polls} small_polls={small_polls}");
    println!(
        "unsafe_race=winner:{} left_remaining:{} right_remaining:{}",
        unsafe_result.winner, unsafe_result.left_remaining, unsafe_result.right_remaining
    );
    println!(
        "safe_race=winner:{} left_remaining:{} right_remaining:{}",
        safe_result.winner, safe_result.left_remaining, safe_result.right_remaining
    );
    println!("wake_by_ref_calls={}", wake.wakes.load(Ordering::Relaxed));
    println!("outcome=PASS");
}
