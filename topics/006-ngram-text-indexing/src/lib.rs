//! Exact byte-substring search through a document-level trigram filter.
//!
//! [`TrigramIndex`] owns one immutable document generation. Each posting list
//! records documents that contain a three-byte key. A query intersects those
//! presence lists, then applies the same exact matcher used by [`scan_count`].
//! The filter can admit false positives, but verification preserves exact
//! byte-substring results.
//!
//! Patterns shorter than three bytes cannot use a trigram. The index scans all
//! documents for those patterns instead of returning an incomplete result.
//!
//! # Example
//!
//! ```
//! use systems_snackpack_topic_006::{TrigramIndex, scan_count};
//!
//! let documents = vec![b"abc---bcd".to_vec(), b"xabcd".to_vec()];
//! let expected = scan_count(&documents, b"abcd");
//! let index = TrigramIndex::build(documents);
//! let result = index.query(b"abcd");
//!
//! assert_eq!(expected, 1);
//! assert_eq!(result.candidate_documents, 2);
//! assert_eq!(result.exact_matches, expected);
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

use std::collections::BTreeMap;

const GRAM_BYTES: usize = 3;
type Gram = [u8; GRAM_BYTES];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Candidate and exact-match counts for one query.
pub struct QueryResult {
    /// Documents that satisfy every distinct trigram-presence condition.
    ///
    /// A needle shorter than three bytes imposes no trigram condition and
    /// admits the entire generation.
    pub candidate_documents: usize,
    /// Candidate documents that contain the needle at least once under exact
    /// byte semantics.
    pub exact_matches: usize,
}

#[derive(Debug)]
/// Immutable documents and their document-level byte-trigram postings.
///
/// Each posting list contains ascending, duplicate-free document IDs. This
/// representation discards occurrence counts, positions, and relative offsets,
/// so [`TrigramIndex::query`] verifies every candidate against the owned bytes.
pub struct TrigramIndex {
    documents: Vec<Vec<u8>>,
    postings: BTreeMap<Gram, Vec<usize>>,
}

impl TrigramIndex {
    /// Builds one immutable generation with sorted, duplicate-free postings.
    ///
    /// # Examples
    ///
    /// ```
    /// use systems_snackpack_topic_006::TrigramIndex;
    ///
    /// let index = TrigramIndex::build(vec![b"needle in a document".to_vec()]);
    /// assert_eq!(index.document_count(), 1);
    /// ```
    pub fn build(documents: Vec<Vec<u8>>) -> Self {
        let mut postings = BTreeMap::<Gram, Vec<usize>>::new();
        let mut document_grams = Vec::<Gram>::new();

        for (document_id, document) in documents.iter().enumerate() {
            document_grams.clear();
            document_grams.extend(document.windows(GRAM_BYTES).map(to_gram));
            document_grams.sort_unstable();
            document_grams.dedup();

            for gram in document_grams.iter().copied() {
                postings.entry(gram).or_default().push(document_id);
            }
        }

        Self {
            documents,
            postings,
        }
    }

    /// Counts every owned document, including documents too short to contribute
    /// a trigram.
    ///
    /// # Examples
    ///
    /// ```
    /// use systems_snackpack_topic_006::TrigramIndex;
    ///
    /// let index = TrigramIndex::build(vec![Vec::new(), b"ab".to_vec()]);
    /// assert_eq!(index.document_count(), 2);
    /// ```
    pub fn document_count(&self) -> usize {
        self.documents.len()
    }

    #[inline(never)]
    /// Returns exact matches after a lossless trigram-presence filter.
    ///
    /// Patterns shorter than three bytes scan every document; the empty needle
    /// matches every document. Longer patterns drive candidate generation from
    /// the shortest posting list, probe the remaining lists, and verify
    /// survivors with exact byte comparison.
    ///
    /// # Examples
    ///
    /// ```
    /// use systems_snackpack_topic_006::TrigramIndex;
    ///
    /// let index = TrigramIndex::build(vec![b"abcd".to_vec(), b"abc---bcd".to_vec()]);
    /// let result = index.query(b"abcd");
    /// assert_eq!(result.candidate_documents, 2);
    /// assert_eq!(result.exact_matches, 1);
    /// ```
    pub fn query(&self, needle: &[u8]) -> QueryResult {
        if needle.len() < GRAM_BYTES {
            return QueryResult {
                candidate_documents: self.documents.len(),
                exact_matches: scan_count(&self.documents, needle),
            };
        }

        let mut query_grams = needle.windows(GRAM_BYTES).map(to_gram).collect::<Vec<_>>();
        query_grams.sort_unstable();
        query_grams.dedup();

        let mut lists = Vec::with_capacity(query_grams.len());
        for gram in &query_grams {
            let Some(posting) = self.postings.get(gram) else {
                return QueryResult {
                    candidate_documents: 0,
                    exact_matches: 0,
                };
            };
            lists.push(posting);
        }
        lists.sort_unstable_by_key(|posting| posting.len());

        let mut candidate_documents = 0;
        let mut exact_matches = 0;
        'candidate: for &document_id in lists[0] {
            for posting in &lists[1..] {
                if posting.binary_search(&document_id).is_err() {
                    continue 'candidate;
                }
            }

            candidate_documents += 1;
            if contains_exact(&self.documents[document_id], needle) {
                exact_matches += 1;
            }
        }

        QueryResult {
            candidate_documents,
            exact_matches,
        }
    }
}

#[inline(never)]
/// Counts documents that contain `needle` at least once under exact byte
/// semantics.
///
/// An empty needle matches every document. Repeated occurrences within one
/// document still contribute one match.
///
/// # Examples
///
/// ```
/// use systems_snackpack_topic_006::scan_count;
///
/// let documents = vec![b"banana".to_vec(), b"band".to_vec()];
/// assert_eq!(scan_count(&documents, b"ana"), 1);
/// ```
pub fn scan_count(documents: &[Vec<u8>], needle: &[u8]) -> usize {
    documents
        .iter()
        .filter(|document| contains_exact(document, needle))
        .count()
}

fn to_gram(window: &[u8]) -> Gram {
    window
        .try_into()
        .expect("window is exactly GRAM_BYTES bytes")
}

#[inline(never)]
fn contains_exact(haystack: &[u8], needle: &[u8]) -> bool {
    if needle.is_empty() {
        return true;
    }
    if needle.len() > haystack.len() {
        return false;
    }

    let first = needle[0];
    for offset in 0..=haystack.len() - needle.len() {
        if haystack[offset] == first && haystack[offset..offset + needle.len()] == *needle {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::{TrigramIndex, scan_count};

    #[test]
    fn index_matches_scan_across_edge_cases() {
        let documents = vec![
            Vec::new(),
            b"a".to_vec(),
            b"ab".to_vec(),
            b"abc---bcd".to_vec(),
            b"xabcd".to_vec(),
            b"aaaaaaaa".to_vec(),
            vec![0, 1, 2, 0xff, 3, 4],
        ];
        let needles: &[&[u8]] = &[
            b"",
            b"a",
            b"ab",
            b"abc",
            b"abcd",
            b"aaaa",
            b"missing",
            &[2, 0xff, 3],
        ];

        let expected = needles
            .iter()
            .map(|needle| scan_count(&documents, needle))
            .collect::<Vec<_>>();
        let index = TrigramIndex::build(documents);

        for (needle, expected) in needles.iter().zip(expected) {
            assert_eq!(index.query(needle).exact_matches, expected);
        }
    }

    #[test]
    fn document_postings_admit_wrong_distance() {
        let index = TrigramIndex::build(vec![b"abc---bcd".to_vec(), b"xabcd".to_vec()]);
        let result = index.query(b"abcd");

        assert_eq!(result.candidate_documents, 2);
        assert_eq!(result.exact_matches, 1);
    }

    #[test]
    fn repeated_grams_keep_a_lossless_presence_filter() {
        let index = TrigramIndex::build(vec![b"aaaaaaaa".to_vec(), b"aaa-x-aaa".to_vec()]);
        let result = index.query(b"aaaa");

        assert_eq!(result.candidate_documents, 2);
        assert_eq!(result.exact_matches, 1);
    }

    #[test]
    fn short_patterns_fall_back_to_all_documents() {
        let index = TrigramIndex::build(vec![b"ab".to_vec(), b"zz".to_vec(), Vec::new()]);
        let result = index.query(b"a");

        assert_eq!(result.candidate_documents, 3);
        assert_eq!(result.exact_matches, 1);
    }
}
