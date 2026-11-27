//! Model one object's current representation at the instant a write takes effect.
//! Small integer labels stand for opaque ETags. Reinstalling a representation
//! repeats its label so histories can exercise validator reuse.
//!
//! ```
//! use topic121_conditional_writes::{apply, Condition};
//! let mut current = None;
//! assert_eq!(apply(&mut current, Condition::Absent, 1), 200);
//! assert_eq!(apply(&mut current, Condition::Matches(1), 2), 200);
//! assert_eq!(apply(&mut current, Condition::Matches(1), 3), 412);
//! assert_eq!(current, Some(2));
//! ```

/// Requirement evaluated at publication.
#[derive(Clone, Copy)]
pub enum Condition {
    /// The current object is absent (including a current delete marker).
    Absent,
    /// The current representation has this validator.
    Matches(u8),
}

/// Apply a serialized PUT and return its modeled S3 status.
pub fn apply(current: &mut Option<u8>, condition: Condition, new_tag: u8) -> u16 {
    match (condition, *current) {
        (Condition::Absent, Some(_)) => 412,
        (Condition::Matches(_), None) => 404,
        (Condition::Matches(expected), Some(actual)) if expected != actual => 412,
        _ => {
            *current = Some(new_tag);
            200
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_after_delete_marker() {
        let mut current = None;
        assert_eq!(apply(&mut current, Condition::Absent, 1), 200);
        assert_eq!(apply(&mut current, Condition::Absent, 2), 412);
        assert_eq!(current, Some(1));
        current = None;
        assert_eq!(apply(&mut current, Condition::Absent, 2), 200);
    }

    #[test]
    fn returning_to_a_validator_allows_an_old_request() {
        let mut current = Some(1);
        assert_eq!(apply(&mut current, Condition::Matches(1), 2), 200);
        assert_eq!(apply(&mut current, Condition::Matches(2), 1), 200);
        assert_eq!(apply(&mut current, Condition::Matches(1), 3), 200);
    }
}
