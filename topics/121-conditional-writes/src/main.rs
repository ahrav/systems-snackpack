//! Read one event history per line. Emit the status and current label after each event.
use std::io::{self, BufRead};
use topic121_conditional_writes::{Condition, apply};

fn main() -> io::Result<()> {
    for line in io::stdin().lock().lines() {
        let mut current = None;
        let mut observations = Vec::new();
        for event in line?.chars() {
            let status = match event {
                'a' => apply(&mut current, Condition::Absent, 1),
                'b' => apply(&mut current, Condition::Absent, 2),
                'x' => apply(&mut current, Condition::Matches(1), 2),
                'y' => apply(&mut current, Condition::Matches(2), 1),
                'd' => {
                    current = None;
                    204
                }
                _ => return Err(io::Error::new(io::ErrorKind::InvalidInput, "unknown event")),
            };
            observations.push(format!("{status}/{}", current.unwrap_or(0)));
        }
        println!("{}", observations.join(" "));
    }
    Ok(())
}
