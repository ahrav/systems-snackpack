//! Multipart receipt normalization and conservative completion reconciliation.
//!
//! This is a local protocol model, not an S3 client. Numeric receipt tokens are
//! fixtures, not checksums. An upload uses immutable bytes for each part number.
//! ```
//! use multipart_correctness::{manifest, Candidate, Receipt};
//! let rows = [Receipt { number: 2, token: 20 }, Receipt { number: 1, token: 10 }];
//! assert_eq!(manifest(Candidate::Slots, 2, &rows).unwrap()[0].number, 1);
//! ```
use std::collections::BTreeMap;

/// One successful upload receipt. The token stands for an opaque ETag.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Receipt {
    /// One-based part number, bounded by the expected manifest length.
    pub number: usize,
    /// Fixture token identifying immutable content for this part.
    pub token: u64,
}

/// Correct strategies for converting unordered, possibly duplicate receipts.
#[derive(Clone, Copy, Debug)]
pub enum Candidate {
    /// Copy all receipts, sort, then validate and deduplicate.
    Sort,
    /// Insert receipts into an ordered map, rejecting conflicting duplicates.
    Tree,
    /// Index bounded part numbers directly in a dense slot array.
    Slots,
}

/// An invalid receipt stream cannot be published.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Invalid {
    /// Expected part count must be between one and 10,000.
    Count,
    /// A receipt has a zero or out-of-plan part number.
    Number,
    /// Two receipts for one part refer to different content.
    Conflict,
    /// At least one planned part has no receipt.
    Missing,
}

/// Normalize receipts to exactly `1..=n`, rejecting all malformed input.
///
/// The contract deliberately requires consecutive parts for every mode. This
/// is an application restriction, not a claim that every S3 mode requires it.
/// Conflict precedence is unspecified when multiple errors occur.
pub fn manifest(c: Candidate, n: usize, rows: &[Receipt]) -> Result<Vec<Receipt>, Invalid> {
    if !(1..=10_000).contains(&n) {
        return Err(Invalid::Count);
    }
    if rows.iter().any(|r| r.number == 0 || r.number > n) {
        return Err(Invalid::Number);
    }
    let out = match c {
        Candidate::Sort => {
            let mut v = rows.to_vec();
            v.sort_unstable_by_key(|r| r.number);
            if v.windows(2)
                .any(|p| p[0].number == p[1].number && p[0].token != p[1].token)
            {
                return Err(Invalid::Conflict);
            }
            v.dedup_by_key(|r| r.number);
            v
        }
        Candidate::Tree => {
            let mut map = BTreeMap::new();
            for r in rows {
                if map
                    .insert(r.number, r.token)
                    .is_some_and(|old| old != r.token)
                {
                    return Err(Invalid::Conflict);
                }
            }
            map.into_iter()
                .map(|(number, token)| Receipt { number, token })
                .collect()
        }
        Candidate::Slots => {
            let mut slots = vec![None; n];
            for r in rows {
                let slot = &mut slots[r.number - 1];
                if slot.is_some_and(|old| old != r.token) {
                    return Err(Invalid::Conflict);
                }
                *slot = Some(r.token);
            }
            slots
                .into_iter()
                .enumerate()
                .map(|(i, token)| {
                    token
                        .map(|token| Receipt {
                            number: i + 1,
                            token,
                        })
                        .ok_or(Invalid::Missing)
                })
                .collect::<Result<Vec<_>, _>>()?
        }
    };
    if out.len() != n {
        return Err(Invalid::Missing);
    }
    Ok(out)
}

/// Evidence about an attempt after a complete request was sent.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Observation {
    /// A parsed success body from this attempt.
    Success,
    /// HTTP 200 headers only, without a complete parsed body.
    HeadersOnly,
    /// A timeout or connection failure with an unknown server outcome.
    Timeout,
    /// A parsed retryable embedded service error.
    RetryableError,
    /// Conditional completion reported HTTP 409.
    Conflict409,
    /// Conditional completion reported HTTP 412.
    Precondition412,
    /// Upload ID is absent, which can mean completed or aborted.
    NoSuchUpload,
}

/// Evidence from reading the destination under an immutable-key contract.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Identity {
    /// Attempt ID, length, and selected checksum contract all match.
    Match,
    /// A different object occupies the key.
    Other,
    /// Object was not found at the instant of the read.
    Absent,
    /// Read failed or metadata/checksum evidence is incomplete.
    Unknown,
}

/// Safe next action in this deliberately restricted protocol model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decision {
    /// Success is proven by the response or matching immutable identity.
    Committed,
    /// A different object owns the destination; do not overwrite it.
    Conflict,
    /// Reconcile before any success or abort claim.
    Reconcile,
    /// Retry the frozen manifest using a bounded policy.
    RetryFrozen,
    /// Reconcile/rebase, then initiate and upload again for a new attempt.
    Reinitiate,
}

/// Decide from observations, never from a timeout or HTTP headers alone.
///
/// `Match` requires a unique, immutable attempt key and trusted identity
/// metadata. Absence does not fence a late completion. This function does not
/// provide a distributed lock, a durable journal, or a cleanup implementation.
pub fn decide(response: Observation, identity: Identity) -> Decision {
    if response == Observation::Success || identity == Identity::Match {
        return Decision::Committed;
    }
    if identity == Identity::Other {
        return Decision::Conflict;
    }
    match response {
        Observation::Conflict409 => Decision::Reinitiate,
        Observation::RetryableError => Decision::RetryFrozen,
        _ => Decision::Reconcile,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const ALL: [Candidate; 3] = [Candidate::Sort, Candidate::Tree, Candidate::Slots];
    // Independent oracle scans by expected number; it shares no normalization algorithm.
    fn oracle(n: usize, rows: &[Receipt]) -> Option<Vec<Receipt>> {
        if !(1..=10_000).contains(&n) || rows.iter().any(|r| r.number == 0 || r.number > n) {
            return None;
        }
        (1..=n)
            .map(|number| {
                let matching: Vec<_> = rows.iter().filter(|r| r.number == number).collect();
                let first = *matching.first()?;
                matching
                    .iter()
                    .all(|r| r.token == first.token)
                    .then_some(*first)
            })
            .collect()
    }
    #[test]
    fn exhaustive_receipts() {
        let alphabet = [
            Receipt {
                number: 0,
                token: 0,
            },
            Receipt {
                number: 1,
                token: 10,
            },
            Receipt {
                number: 1,
                token: 11,
            },
            Receipt {
                number: 2,
                token: 20,
            },
            Receipt {
                number: 3,
                token: 30,
            },
        ];
        for len in 0..=6 {
            for mut code in 0..5usize.pow(len) {
                let mut rows = Vec::new();
                for _ in 0..len {
                    rows.push(alphabet[code % 5]);
                    code /= 5;
                }
                let expected = oracle(2, &rows);
                for c in ALL {
                    assert_eq!(manifest(c, 2, &rows).ok(), expected);
                }
            }
        }
    }
    #[test]
    fn limits_and_maximum() {
        let rows: Vec<_> = (1..=10_000)
            .rev()
            .map(|number| Receipt {
                number,
                token: number as u64,
            })
            .collect();
        for c in ALL {
            assert_eq!(manifest(c, 0, &[]), Err(Invalid::Count));
            assert_eq!(manifest(c, 10_001, &[]), Err(Invalid::Count));
            assert_eq!(manifest(c, 10_000, &rows).unwrap().len(), 10_000);
            assert_eq!(manifest(c, 10_000, &rows[..9999]), Err(Invalid::Missing));
        }
    }
    #[test]
    fn completion_truth_table() {
        use Observation::*;
        for response in [
            Success,
            HeadersOnly,
            Timeout,
            RetryableError,
            Conflict409,
            Precondition412,
            NoSuchUpload,
        ] {
            for identity in [
                Identity::Match,
                Identity::Other,
                Identity::Absent,
                Identity::Unknown,
            ] {
                let result = decide(response, identity);
                assert_eq!(
                    result == Decision::Committed,
                    response == Success || identity == Identity::Match
                );
                if matches!(
                    response,
                    HeadersOnly | Timeout | Precondition412 | NoSuchUpload
                ) && matches!(identity, Identity::Absent | Identity::Unknown)
                {
                    assert_eq!(result, Decision::Reconcile);
                }
            }
        }
        assert_eq!(decide(Conflict409, Identity::Absent), Decision::Reinitiate);
        assert_eq!(
            decide(RetryableError, Identity::Absent),
            Decision::RetryFrozen
        );
    }
    #[test]
    fn rejects_header_only_success_policy() {
        // A server can return 200 headers then an embedded error. The unsafe
        // policy would declare success in this counterexample.
        let unsafe_policy_claims_success = true;
        let server_committed = false;
        assert_ne!(unsafe_policy_claims_success, server_committed);
        assert_eq!(
            decide(Observation::HeadersOnly, Identity::Unknown),
            Decision::Reconcile
        );
    }
}
