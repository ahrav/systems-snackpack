//! Exhaustively compares token dispatch with a connection-identity ledger.
use topic108_fd_reuse::{Registry, Token};

fn main() {
    let mut comparisons = 0_u64;
    let mut raw_misroutes = 0_u64;
    for history in 0..4_usize.pow(8) {
        let mut r = Registry::new(2);
        let mut live = [None; 2];
        let mut current_token = [None; 2];
        let mut queued: Vec<(Token, usize, usize)> = Vec::new();
        let mut actions = history;
        for step in 0..8 {
            let action = actions % 4;
            actions /= 4;
            let slot = action % 2;
            let fd = 7 + slot as i32;
            if action < 2 {
                let token = r.insert(slot as u32, fd);
                assert_eq!(token.is_some(), live[slot].is_none());
                if let Some(token) = token {
                    let identity = step + 1;
                    live[slot] = Some(identity);
                    current_token[slot] = Some(token);
                    queued.push((token, slot, identity));
                }
            } else if let Some(token) = current_token[slot].take() {
                assert_eq!(r.retire(token), Some(fd));
                live[slot] = None;
            }
            for &(token, origin_slot, identity) in &queued {
                let expected =
                    (live[origin_slot] == Some(identity)).then_some(7 + origin_slot as i32);
                assert_eq!(r.resolve(token), expected);
                comparisons += 1;
                if live[origin_slot].is_some() && expected.is_none() {
                    raw_misroutes += 1;
                    assert_eq!(r.retire(token), None);
                }
            }
        }
    }
    assert!(raw_misroutes > 0);
    println!(
        "histories=65536 comparisons={comparisons} raw_misroutes={raw_misroutes} guarded_misroutes=0"
    );
}
