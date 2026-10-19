//! Emit bounded schedules for an independent Python oracle.
use topic082_linux_runtime::drain;

fn main() {
    for a in 0..6 {
        for b in 0..6 {
            for c in 0..6 {
                for budget in 1..5 {
                    let visits = drain(vec![a, b, c], budget);
                    println!(
                        "{a} {b} {c} {budget}|{}",
                        visits
                            .iter()
                            .map(|(id, n)| format!("{id}:{n}"))
                            .collect::<Vec<_>>()
                            .join(",")
                    );
                }
            }
        }
    }
}
