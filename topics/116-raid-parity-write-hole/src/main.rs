//! Batch interface for the independent trace oracle.
use std::io::{self, BufRead, BufWriter, Write};
use topic116_raid_parity_write_hole::{Record, rebuild, stripe};

fn main() -> io::Result<()> {
    let mut output = BufWriter::new(io::stdout().lock());
    for line in io::stdin().lock().lines() {
        let words = line?
            .split_ascii_whitespace()
            .map(str::parse)
            .collect::<Result<Vec<u8>, _>>()
            .map_err(io::Error::other)?;
        let [a, b, new_a, new_b, kind, cut, lost, replay_cut] = words[..] else {
            return Err(io::Error::other("expected eight decimal byte values"));
        };
        let old = stripe(a, b).map(Some);
        let record = match kind {
            0 => Record::partial(stripe(a, b), 0, new_a),
            1 => Record::partial(stripe(a, b), 1, new_b),
            2 => Record::full(new_a, new_b),
            _ => return Err(io::Error::other("invalid write kind")),
        };
        if lost > 2 || cut > 7 || replay_cut > 7 {
            return Err(io::Error::other("invalid member or persistence mask"));
        }
        let lose_member = |mut members: [Option<u8>; 3]| {
            members[usize::from(lost)] = None;
            members
        };
        let before_log = rebuild(lose_member(old));
        let mut home = old;
        record.install(&mut home, cut);
        let mut survivors = lose_member(home);
        let unprotected = rebuild(survivors);
        record.install(&mut survivors, replay_cut); // Another crash during replay.
        record.install(&mut survivors, 7); // The retained record is still valid.
        let replayed = rebuild(survivors);
        let mut installed = old;
        record.install(&mut installed, 7);
        let retired = rebuild(lose_member(installed));
        for group in [before_log, unprotected, replayed, retired] {
            write!(output, "{:02x}{:02x}{:02x} ", group[0], group[1], group[2])?;
        }
        writeln!(output)?;
    }
    output.flush()
}
