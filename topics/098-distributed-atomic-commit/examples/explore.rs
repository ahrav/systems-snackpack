//! Export a finite graph for the independent Python oracle.
use distributed_atomic_commit::{Mode, explore};
use std::io::{self, Write};

fn main() -> io::Result<()> {
    let args: Vec<_> = std::env::args().collect();
    let mode = match args.get(1).map(String::as_str).unwrap_or("safe") {
        "safe" => Mode::Safe,
        "timeout" => Mode::Timeout,
        "early" => Mode::Early,
        _ => panic!("mode must be safe, timeout or early"),
    };
    let n = args
        .get(2)
        .map_or(2, |s| s.parse().expect("participant count"));
    let g = explore(n, mode);
    let mut out = io::BufWriter::new(io::stdout().lock());
    writeln!(out, "meta\t{n}\t{mode:?}")?;
    for (id, state) in g.states.iter().enumerate() {
        writeln!(out, "node\t{id}\t{}", state.fields(n))?;
    }
    for (from, to, label) in g.edges {
        writeln!(out, "edge\t{from}\t{to}\t{label}")?;
    }
    out.flush()
}
