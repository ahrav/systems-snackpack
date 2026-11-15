//! Exhaustive histories compared with independently retained object references.
use std::{cell::Cell, rc::Rc};
use topic109_pidfd::Processes;

fn main() {
    let mut comparisons = 0_u64;
    let mut wrong_raw_targets = 0_u64;
    for encoded in 0..6_usize.pow(7) {
        let mut digits = encoded;
        let mut actual = Processes::default();
        // Oracle handles retain the object itself. Reap clears the PID slot;
        // it cannot change an old object's live flag or redirect its reference.
        let mut slots: [Option<Rc<Cell<bool>>>; 2] = [None, None];
        let mut saved = Vec::new();
        for _ in 0..7 {
            let action = digits % 6;
            digits /= 6;
            let pid = action % 2;
            match action / 2 {
                0 => {
                    let handle = actual.spawn(pid);
                    assert_eq!(handle.is_some(), slots[pid].is_none());
                    if let Some(handle) = handle {
                        let object = Rc::new(Cell::new(true));
                        slots[pid] = Some(object.clone());
                        saved.push((pid, handle, object));
                    }
                }
                1 => {
                    actual.exit(pid);
                    if let Some(object) = &slots[pid] {
                        object.set(false);
                    }
                }
                _ => {
                    actual.reap(pid);
                    if slots[pid].as_ref().is_some_and(|o| !o.get()) {
                        slots[pid] = None;
                    }
                }
            }
            for (pid, handle, object) in &saved {
                let expected = object.get().then_some(handle.identity());
                assert_eq!(actual.signal(*handle), expected);
                comparisons += 1;
                if let Some(target) = actual.raw_signal(*pid)
                    && target != handle.identity()
                {
                    wrong_raw_targets += 1;
                }
            }
        }
    }
    assert!(wrong_raw_targets > 0, "raw-PID negative control must fail");
    println!(
        "histories=279936 identity_comparisons={comparisons} wrong_raw_targets={wrong_raw_targets} PASS"
    );
}
