//! Deterministic model of snapshot visibility, heap-only tuple (HOT) chains,
//! and cleanup.
//!
//! The model uses monotonically increasing, committed transaction identifiers
//! and one explicit in-progress list. It omits aborted transactions,
//! subtransactions, command identifiers, wraparound and freezing, hint bits,
//! row-lock groups called MultiXacts, page headers and redirects, write-ahead
//! logging, index implementations, and concurrent vacuum work.
//!
//! # Example
//!
//! ```
//! use mvcc_hot_vacuum::{Snapshot, Version, visible_version};
//!
//! let versions = [
//!     Version { xmin: 10, xmax: Some(20), next: Some(1), page: 0, indexed_key: 7, value: 100 },
//!     Version { xmin: 20, xmax: None, next: None, page: 0, indexed_key: 7, value: 120 },
//! ];
//! let snapshot = Snapshot { xmin: 15, xmax: 20, in_progress: &[] };
//!
//! assert_eq!(visible_version(&versions, 0, snapshot), Some((0, 100)));
//! ```

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Snapshot bounds and the transaction identifiers still in progress.
///
/// This simplified representation treats every identifier absent from
/// `in_progress` and below `xmax` as committed. Real PostgreSQL visibility has
/// additional transaction states and wraparound-aware comparisons.
/// Callers constructing PostgreSQL-shaped snapshots keep `xmin <= xmax` and
/// place every `in_progress` identifier in the half-open range
/// `[xmin, xmax)`; the type does not enforce either condition.
pub struct Snapshot<'a> {
    /// Lower bound below which the model assumes transactions committed.
    pub xmin: u64,
    /// Upper bound at or above which the model assumes transactions were unfinished.
    pub xmax: u64,
    /// Identifiers inside the bounds that the snapshot observed in progress.
    pub in_progress: &'a [u64],
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// One physical version in a modeled forward chain.
///
/// HOT-like scenarios keep every linked version on one page and preserve the
/// indexed key. The type records those properties but does not enforce them.
pub struct Version {
    /// Identifier of the transaction that inserted this version.
    pub xmin: u64,
    /// Identifier that ended this version, or `None` while it remains current.
    pub xmax: Option<u64>,
    /// Array position of the successor in the slice passed to [`visible_version`].
    pub next: Option<usize>,
    /// Modeled heap-page number.
    pub page: u32,
    /// Modeled value referenced by an ordinary index.
    pub indexed_key: u32,
    /// Payload used to identify the selected version.
    pub value: u64,
}

/// Applies the model's snapshot-bound rule to one transaction identifier.
///
/// `in_progress` states whether the caller found `xid` in the snapshot's
/// in-progress list. Identifiers below `xmin` remain visible even if the caller
/// passes `true`, matching the model's assumption that the lower bound contains
/// no active transaction. The C application binary interface (ABI) and unmangled
/// name retain a stable symbol for linked-code inspection.
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic32_xid_visible_bounds(
    xid: u64,
    xmin: u64,
    xmax: u64,
    in_progress: bool,
) -> bool {
    xid < xmax && (xid < xmin || !in_progress)
}

/// Applies the model's strict cleanup-horizon rule to one ending identifier.
///
/// Equality is not reclaimable: a version ending at `oldest_xmin` can still be
/// relevant at that horizon. The C application binary interface (ABI) and
/// unmangled name retain a stable symbol for linked-code inspection.
#[must_use]
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic32_reclaimable_before(delete_xid: u64, oldest_xmin: u64) -> bool {
    delete_xid < oldest_xmin
}

#[must_use]
/// Returns whether `xid` is visible under the simplified snapshot rule.
///
/// The result assumes an identifier absent from `snapshot.in_progress` and
/// below `snapshot.xmax` committed; it does not consult transaction status.
///
/// # Performance
///
/// The in-progress lookup takes linear time in `snapshot.in_progress` and
/// allocates no memory.
///
/// # Examples
///
/// ```
/// use mvcc_hot_vacuum::{Snapshot, xid_visible};
///
/// let snapshot = Snapshot { xmin: 20, xmax: 25, in_progress: &[20] };
/// assert!(xid_visible(10, snapshot));
/// assert!(!xid_visible(20, snapshot));
/// ```
pub fn xid_visible(xid: u64, snapshot: Snapshot<'_>) -> bool {
    let in_progress = snapshot.in_progress.contains(&xid);
    topic32_xid_visible_bounds(xid, snapshot.xmin, snapshot.xmax, in_progress)
}

#[must_use]
/// Returns the first visible `(array position, payload)` along a forward chain.
///
/// The walk starts at `root` and follows at most `versions.len()` links. If the
/// walk reaches an invalid position before selecting a version, or exhausts the
/// step bound without selecting one, it returns `None`. Selection uses only
/// transaction visibility: the function does not validate page equality,
/// indexed-key equality, or chain direction.
///
/// # Performance
///
/// For chain length `v` and in-progress-list length `x`, the worst-case time is
/// `O(v * x)`. The walk allocates no memory.
///
/// # Examples
///
/// ```
/// use mvcc_hot_vacuum::{Snapshot, Version, visible_version};
///
/// let versions = [Version {
///     xmin: 10, xmax: None, next: None, page: 0, indexed_key: 7, value: 100,
/// }];
/// let snapshot = Snapshot { xmin: 15, xmax: 15, in_progress: &[] };
/// assert_eq!(visible_version(&versions, 0, snapshot), Some((0, 100)));
/// ```
pub fn visible_version(
    versions: &[Version],
    root: usize,
    snapshot: Snapshot<'_>,
) -> Option<(usize, u64)> {
    let mut current = Some(root);
    for _ in 0..versions.len() {
        let position = current?;
        let version = versions.get(position)?;
        let inserted = xid_visible(version.xmin, snapshot);
        let ended = version
            .xmax
            .is_some_and(|delete_xid| xid_visible(delete_xid, snapshot));
        if inserted && !ended {
            return Some((position, version.value));
        }
        current = version.next;
    }
    None
}

#[must_use]
/// Counts versions whose ending identifiers precede `oldest_xmin`.
///
/// Current versions with no `xmax` never qualify. The model assumes every
/// ending identifier committed; PostgreSQL must also check transaction status
/// and wraparound-aware ordering. The count reports eligibility only and does
/// not mutate chains, heap slots, or index entries.
///
/// # Performance
///
/// The scan takes `O(n)` time for `n` versions and allocates no memory.
///
/// # Examples
///
/// ```
/// use mvcc_hot_vacuum::{Version, reclaimable_count};
///
/// let versions = [Version {
///     xmin: 10, xmax: Some(20), next: None, page: 0, indexed_key: 7, value: 100,
/// }];
/// assert_eq!(reclaimable_count(&versions, 20), 0);
/// assert_eq!(reclaimable_count(&versions, 21), 1);
/// ```
pub fn reclaimable_count(versions: &[Version], oldest_xmin: u64) -> usize {
    versions
        .iter()
        .filter_map(|version| version.xmax)
        .filter(|delete_xid| topic32_reclaimable_before(*delete_xid, oldest_xmin))
        .count()
}

/// Builds and validates the fixed model, then returns its stable text receipt.
///
/// The scenario checks three snapshot selections, one in-progress exclusion,
/// same-page HOT-like chain shape, unlinked non-HOT control versions, explicit
/// index-entry accounting, and cleanup results before and after releasing the
/// modeled horizon.
///
/// # Errors
///
/// Returns a message naming the first violated visibility, page, chain, index,
/// or reclamation invariant.
///
/// # Examples
///
/// ```
/// let receipt = mvcc_hot_vacuum::self_check_receipt()?;
/// assert!(receipt.ends_with("CHECK=PASS\n"));
/// # Ok::<(), String>(())
/// ```
pub fn self_check_receipt() -> Result<String, String> {
    let hot_like = [
        Version {
            xmin: 10,
            xmax: Some(20),
            next: Some(1),
            page: 0,
            indexed_key: 7,
            value: 100,
        },
        Version {
            xmin: 20,
            xmax: Some(30),
            next: Some(2),
            page: 0,
            indexed_key: 7,
            value: 120,
        },
        Version {
            xmin: 30,
            xmax: None,
            next: None,
            page: 0,
            indexed_key: 7,
            value: 140,
        },
    ];
    let non_hot = [
        Version {
            next: None,
            indexed_key: 7,
            ..hot_like[0]
        },
        Version {
            next: None,
            indexed_key: 8,
            ..hot_like[1]
        },
        Version {
            next: None,
            indexed_key: 9,
            ..hot_like[2]
        },
    ];

    check(
        hot_like.iter().all(|version| version.page == 0),
        "HOT-like versions must share one page",
    )?;
    check(
        hot_like.map(|version| version.next) == [Some(1), Some(2), None],
        "HOT-like successor chain must be 0->1->2",
    )?;
    check(
        hot_like.iter().all(|version| version.indexed_key == 7),
        "HOT-like chain must preserve its indexed key",
    )?;
    check(
        non_hot.iter().all(|version| version.page == 0),
        "non-HOT control must use the same page placement",
    )?;
    check(
        non_hot.map(|version| (version.next, version.indexed_key))
            == [(None, 7), (None, 8), (None, 9)],
        "non-HOT control must use independent entries with changed keys",
    )?;

    let hot_index_entries_before = 1;
    let non_hot_index_entries_before = non_hot.len();

    let snapshots = [
        (
            "old",
            Snapshot {
                xmin: 15,
                xmax: 20,
                in_progress: &[],
            },
            (0, 100),
        ),
        (
            "middle",
            Snapshot {
                xmin: 25,
                xmax: 25,
                in_progress: &[],
            },
            (1, 120),
        ),
        (
            "new",
            Snapshot {
                xmin: 35,
                xmax: 35,
                in_progress: &[],
            },
            (2, 140),
        ),
    ];
    for (name, snapshot, expected) in snapshots {
        check(
            visible_version(&hot_like, 0, snapshot) == Some(expected),
            &format!("{name} snapshot selected the wrong version"),
        )?;
    }

    let in_progress_snapshot = Snapshot {
        xmin: 20,
        xmax: 25,
        in_progress: &[20],
    };
    check(
        !xid_visible(20, in_progress_snapshot),
        "in-progress identifier must remain invisible",
    )?;
    check(
        xid_visible(10, in_progress_snapshot),
        "identifier below xmin must remain visible",
    )?;

    let pinned_horizon = 20;
    let released_horizon = 40;
    let hot_pinned = reclaimable_count(&hot_like, pinned_horizon);
    let non_hot_pinned = reclaimable_count(&non_hot, pinned_horizon);
    let hot_released = reclaimable_count(&hot_like, released_horizon);
    let non_hot_released = reclaimable_count(&non_hot, released_horizon);
    check(
        (hot_pinned, non_hot_pinned) == (0, 0),
        "pinned horizon must reclaim no versions",
    )?;
    check(
        (hot_released, non_hot_released) == (2, 2),
        "released horizon must reclaim two versions",
    )?;
    let hot_index_entries_after = hot_index_entries_before;
    let non_hot_index_entries_after = non_hot_index_entries_before - non_hot_released;
    check(
        (hot_index_entries_after, non_hot_index_entries_after) == (1, 1),
        "released horizon must leave one entry in each index shape",
    )?;

    let receipt = format!(
        concat!(
            "MODEL_BOUNDARY=committed monotonic XIDs plus one in-progress list; ",
            "excludes aborts, subtransactions, command IDs, wraparound/freezing, hint bits, ",
            "row locks/MultiXacts, page headers/redirects, WAL, index/lock details, and concurrent vacuum\n",
            "HOT_LIKE versions=3 same_page=true index_entries_before={} keys=7,7,7 chain=0->1->2\n",
            "NON_HOT versions=3 same_page=true index_entries_before={} keys=7,8,9 chains=none\n",
            "SNAPSHOT name=old xmin=15 xmax=20 visible_version=0 value=100\n",
            "SNAPSHOT name=middle xmin=25 xmax=25 visible_version=1 value=120\n",
            "SNAPSHOT name=new xmin=35 xmax=35 visible_version=2 value=140\n",
            "IN_PROGRESS xid=20 xmin=20 xmax=25 visible=false\n",
            "VACUUM oldest_xmin={} hot_reclaimable={} non_hot_reclaimable={}\n",
            "VACUUM oldest_xmin={} hot_reclaimable={} non_hot_reclaimable={}\n",
            "AFTER_RELEASED_HORIZON live_heap_versions=1 hot_index_entries={} non_hot_index_entries={}\n",
            "CHECK=PASS\n"
        ),
        hot_index_entries_before,
        non_hot_index_entries_before,
        pinned_horizon,
        hot_pinned,
        non_hot_pinned,
        released_horizon,
        hot_released,
        non_hot_released,
        hot_index_entries_after,
        non_hot_index_entries_after,
    );
    Ok(receipt)
}

fn check(condition: bool, message: &str) -> Result<(), String> {
    condition.then_some(()).ok_or_else(|| message.to_owned())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn visibility_hook_covers_every_bound_case() {
        assert!(topic32_xid_visible_bounds(9, 10, 20, false));
        assert!(topic32_xid_visible_bounds(10, 10, 20, false));
        assert!(!topic32_xid_visible_bounds(10, 10, 20, true));
        assert!(topic32_xid_visible_bounds(19, 10, 20, false));
        assert!(!topic32_xid_visible_bounds(20, 10, 20, false));
    }

    #[test]
    fn cleanup_hook_keeps_the_equal_horizon() {
        assert!(topic32_reclaimable_before(19, 20));
        assert!(!topic32_reclaimable_before(20, 20));
        assert!(!topic32_reclaimable_before(21, 20));
    }

    #[test]
    fn bounded_walk_rejects_invalid_and_cyclic_chains() {
        let snapshot = Snapshot {
            xmin: 30,
            xmax: 30,
            in_progress: &[],
        };
        let cycle = [Version {
            xmin: 40,
            xmax: None,
            next: Some(0),
            page: 0,
            indexed_key: 7,
            value: 1,
        }];
        assert_eq!(visible_version(&cycle, 0, snapshot), None);
        assert_eq!(visible_version(&cycle, 1, snapshot), None);
    }

    #[test]
    fn stable_receipt_matches_the_checked_in_oracle() {
        let receipt = self_check_receipt().expect("fixed scenario must pass");
        assert_eq!(receipt, include_str!("../experiment/expected.txt"));
    }
}
