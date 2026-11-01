//! Guarded integer specialization with explicit recovery state.
//!
//! The model commits each row's effect after both guards pass. Recovery resumes
//! before the failing row. It models state transfer; it generates no machine code.
//!
//! ```
//! use topic095_jit_specialization::{Row, specialized};
//! let r = specialized(&[Row::A(2), Row::B(3)]);
//! assert_eq!(r.total, 5);
//! assert_eq!(r.effects, vec![0, 1]);
//! assert_eq!(r.deopt_at, Some(1));
//! ```

/// Two layouts with the same logical integer field.
#[derive(Clone, Copy, Debug)]
pub enum Row {
    /// Layout accepted by the specialized path.
    A(i32),
    /// Layout requiring general access in this model.
    B(i32),
}

impl Row {
    fn value(self) -> i32 {
        match self {
            Self::A(x) | Self::B(x) => x,
        }
    }
}

/// Observable result and the recovery position, if a guard failed.
#[derive(Debug, PartialEq, Eq)]
pub struct Outcome {
    /// Exact sum, widened beyond every feasible slice of i32 values.
    pub total: i128,
    /// Ordered committed effects, represented by row indices.
    pub effects: Vec<usize>,
    /// Index of the first uncommitted row at recovery.
    pub deopt_at: Option<usize>,
}

fn resume(rows: &[Row], mut state: Outcome) -> Outcome {
    for (i, row) in rows.iter().enumerate().skip(state.effects.len()) {
        state.total += i128::from(row.value());
        state.effects.push(i);
    }
    state
}

/// Execute every row through the general representation.
pub fn generic(rows: &[Row]) -> Outcome {
    resume(
        rows,
        Outcome {
            total: 0,
            effects: Vec::new(),
            deopt_at: None,
        },
    )
}

/// Specialize layout A and signed 32-bit accumulation, then resume on failure.
///
/// The effect sequence is a prefix of row indices at every guard. The bailout
/// preserves that prefix and the exact sum. Baseline execution handles the suffix.
pub fn specialized(rows: &[Row]) -> Outcome {
    let mut sum = 0_i32;
    let mut state = Outcome {
        total: 0,
        effects: Vec::new(),
        deopt_at: None,
    };
    for (i, row) in rows.iter().enumerate() {
        let next = match row {
            Row::A(value) => sum.checked_add(*value),
            Row::B(_) => None,
        };
        let Some(next) = next else {
            state.total = i128::from(sum);
            state.deopt_at = Some(i);
            return resume(rows, state);
        };
        sum = next;
        state.effects.push(i);
    }
    state.total = i128::from(sum);
    state
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_shape_bailout_preserves_effect_order() {
        for n in 0..16 {
            for at in 0..=n {
                let mut rows = vec![Row::A(7); n];
                if at < n {
                    rows[at] = Row::B(9);
                }
                let got = specialized(&rows);
                let expected = generic(&rows);
                assert_eq!(got.total, expected.total);
                assert_eq!(got.effects, expected.effects);
                assert_eq!(got.deopt_at, (at < n).then_some(at));
            }
        }
    }

    #[test]
    fn overflow_preserves_prefix_and_failing_row() {
        for rows in [
            vec![Row::A(i32::MAX), Row::A(1), Row::A(-2)],
            vec![Row::A(i32::MIN), Row::A(-1), Row::B(2)],
        ] {
            let got = specialized(&rows);
            assert_eq!(got.total, generic(&rows).total);
            assert_eq!(got.effects, vec![0, 1, 2]);
            assert_eq!(got.deopt_at, Some(1));
        }
    }

    #[test]
    fn restarting_or_skipping_changes_observable_effects() {
        let rows = [Row::A(2), Row::B(3)];
        let got = specialized(&rows);
        assert_eq!(got.effects, vec![0, 1]);
        assert_ne!(got.effects, vec![0, 0, 1]);
        assert_ne!(got.effects, vec![0]);
    }
}
