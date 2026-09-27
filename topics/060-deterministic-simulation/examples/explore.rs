//! Exhaust both increment models and replay the broken model's first witness.
use topic060_deterministic_simulation::{Mode, Status, replay, search};

fn main() {
    for (mode, depth) in [(Mode::Split, 4), (Mode::Atomic, 2), (Mode::Split, 3)] {
        let r = search(mode, depth);
        println!("{mode:?} depth={depth}: {r:?}");
        if let Some(ref trace) = r.witness {
            let result = replay(mode, trace).expect("search witness must replay");
            assert_eq!(result.valid_terminal(), Some(false));
            println!("replay {trace:?}: {result:?}");
        }
    }
    assert_eq!(search(Mode::Split, 4).failures, 4);
    assert_eq!(search(Mode::Atomic, 2).failures, 0);
    assert_eq!(search(Mode::Split, 3).status, Status::Cutoff);
}
