//! One file, one original delegation, and one competing open with DENY_NONE.
//! The initial conflicting request starts recall. P retries the open.
//!
//! ```
//! use topic115_nfs_delegation::trace;
//! assert_eq!(trace(true, false, "KFP"), "held wait GOLD");
//! assert_eq!(trace(true, false, "KFRP"), "returned open GOLD");
//! assert_eq!(trace(true, true, "VPBF"), "revoked open RED");
//! ```

/// Evaluate a schedule. A write holder starts with private GOLD over server BLUE.
/// B writes RED only after gaining write access. K acknowledges recall, F attempts
/// A's writeback, R asks the holder to finish a clean return, V represents a
/// server recall timeout, P asks for admission, and B attempts B's write.
/// The holder knows whether its dirty data reached the server.
pub fn trace(write_grant: bool, write_open: bool, events: &str) -> String {
    let conflicts = write_grant || write_open;
    let mut grant = "held";
    let mut dirty = write_grant;
    let mut open = !conflicts;
    let mut data = "BLUE";
    for event in events.bytes() {
        match event {
            b'F' if grant == "held" && dirty => {
                data = "GOLD";
                dirty = false;
            }
            b'R' if grant == "held" && !dirty => grant = "returned",
            b'V' if grant == "held" && conflicts => grant = "revoked",
            b'P' if grant != "held" || !conflicts => open = true,
            b'B' if open && write_open => data = "RED",
            b'K' | b'F' | b'R' | b'V' | b'P' | b'B' => {}
            _ => panic!("unknown event"),
        }
    }
    let access = if open { "open" } else { "wait" };
    format!("{grant} {access} {data}")
}

#[cfg(test)]
mod tests {
    use super::trace;

    #[test]
    fn callback_and_flush_each_leave_the_reader_waiting() {
        assert_eq!(trace(true, false, "KPFPRP"), "returned open GOLD");
        assert_eq!(trace(true, false, "KPFPR"), "returned wait GOLD");
        assert_eq!(trace(true, false, "KRPF"), "held wait GOLD");
    }

    #[test]
    fn revocation_preserves_accepted_writes_and_fences_late_ones() {
        assert_eq!(trace(true, true, "FVP"), "revoked open GOLD");
        assert_eq!(trace(true, true, "VPBF"), "revoked open RED");
        assert_eq!(trace(false, false, "KPV"), "held open BLUE");
    }
}
