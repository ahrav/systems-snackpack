//! Deterministic admission traces; the printed times are simulated, not measured.

const CHUNK: usize = 1_200;
const CAP: usize = 2_400;
const BYTES_PER_US: usize = 12;

fn trace(capped: bool, pause: bool) -> Vec<usize> {
    let mut sent = Vec::new();
    let mut next_due = 0;
    let mut credit = CAP;
    let mut last = 0;
    for now in (0..=20_000).step_by(100) {
        if pause && (2_000..7_000).contains(&now) {
            continue;
        }
        credit = CAP.min(credit + (now - last) * BYTES_PER_US);
        last = now;
        while sent.len() < 100 {
            if capped {
                if credit < CHUNK {
                    break;
                }
                credit -= CHUNK;
            } else {
                if now < next_due {
                    break;
                }
                next_due += 100;
            }
            sent.push(now);
        }
    }
    assert_eq!(sent.len(), 100);
    sent
}

fn max_burst(trace: &[usize]) -> usize {
    trace
        .iter()
        .map(|time| trace.iter().filter(|other| *other == time).count())
        .max()
        .unwrap_or(0)
}

fn envelope_holds(trace: &[usize]) -> bool {
    for first in 0..trace.len() {
        for last in first..trace.len() {
            let bytes = (last - first + 1) * CHUNK;
            let elapsed = trace[last] - trace[first];
            if bytes > CAP + elapsed * BYTES_PER_US {
                return false;
            }
        }
    }
    true
}

fn main() {
    for pause in [false, true] {
        let overdue = trace(false, pause);
        let capped = trace(true, pause);
        assert!(envelope_holds(&capped));
        assert_eq!(max_burst(&capped), 2);
        assert_eq!(max_burst(&overdue), if pause { 51 } else { 1 });
        assert_eq!(envelope_holds(&overdue), !pause);
        println!(
            "pause={pause} overdue_burst={} capped_burst={} overdue_finish_us={} capped_finish_us={}",
            max_burst(&overdue),
            max_burst(&capped),
            overdue.last().unwrap(),
            capped.last().unwrap()
        );
    }
}
