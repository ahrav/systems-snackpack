//! Request grammar for a report service. Filesystem containment requires an
//! operation-time policy such as Linux `openat2`; this filter checks bytes only.
//!
//! ```
//! use topic110_path_resolution::relative_request;
//! assert!(relative_request(b"job/report"));
//! assert!(!relative_request(b"../outside/report"));
//! ```

/// Accept nonempty relative names with no NUL or parent components.
///
/// Repeated separators and `.` are allowed. A symlink can still redirect an
/// accepted name, so callers must apply containment during the actual open.
pub fn relative_request(path: &[u8]) -> bool {
    !path.is_empty()
        && path[0] != b'/'
        && !path.contains(&0)
        && !path.split(|&c| c == b'/').any(|part| part == b"..")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ordinary_and_normalized_components() {
        for path in [b"job/report".as_slice(), b"job//./report", b"a..b", b"."] {
            assert!(relative_request(path));
        }
    }

    #[test]
    fn rejects_escape_syntax() {
        for path in [b"".as_slice(), b"/job", b"..", b"a/../b", b"a\0b"] {
            assert!(!relative_request(path));
        }
    }

    #[test]
    fn grammar_cannot_observe_symlinks() {
        assert!(relative_request(b"job/report"));
        // The native fixture replaces job after checking this same request.
    }
}
