//! Read bytes from stdin and print comma-separated exclusive chunk ends.
use content_addressed_storage::{Policy, boundaries};
use std::io::{self, Read};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let policy = match std::env::args().nth(1).as_deref() {
        Some("whole") => Policy::Whole,
        Some("fixed") => Policy::Fixed,
        Some("cdc") => Policy::Content,
        _ => return Err("expected whole, fixed, or cdc".into()),
    };
    let mut data = Vec::new();
    io::stdin().read_to_end(&mut data)?;
    let ends = boundaries(&data, policy);
    println!(
        "{}",
        ends.iter()
            .map(usize::to_string)
            .collect::<Vec<_>>()
            .join(",")
    );
    Ok(())
}
