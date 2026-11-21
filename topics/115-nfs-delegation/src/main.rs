//! Batch interface for the independent ordering oracle.
use std::io::{self, BufRead, Write};
use topic115_nfs_delegation::trace;

fn main() -> io::Result<()> {
    let mut out = io::BufWriter::new(io::stdout().lock());
    for line in io::stdin().lock().lines() {
        let line = line?;
        let mut fields = line.split_whitespace();
        let grant = fields.next().expect("read or write grant");
        let open = fields.next().expect("read or write open");
        let events = fields.next().unwrap_or("");
        assert!(matches!(grant, "r" | "w") && matches!(open, "r" | "w"));
        assert!(fields.next().is_none());
        writeln!(out, "{}", trace(grant == "w", open == "w", events))?;
    }
    out.flush()
}
