//! Runs the one-frame account-page schedule.
use topic122_buffer_pinning::{Page, Pool};

fn main() {
    let pool = Pool::default();
    let reader = pool.pin(Page::A).unwrap();
    println!("first read A {}", reader.read());
    std::thread::scope(|scope| {
        scope.spawn(|| pool.pin(Page::A).unwrap().write(42));
    });
    assert!(pool.pin(Page::B).is_none());
    println!("B request busy");
    println!("second read A {}", reader.read());
    drop(reader);
    println!("B retry {}", pool.pin(Page::B).unwrap().read());
    println!("A reloaded {}", pool.pin(Page::A).unwrap().read());
}
