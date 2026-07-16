//! Shows candidate generation and exact verification for one false positive.
//!
//! `abc---bcd` contains the `abc` and `bcd` query trigrams but not their required
//! adjacency. The document-level filter admits it, and exact verification
//! rejects it.

use systems_snackpack_topic_006::{TrigramIndex, scan_count};

fn main() {
    let documents = vec![
        b"abc---bcd".to_vec(),
        b"xabcd".to_vec(),
        b"unrelated".to_vec(),
    ];
    let expected = scan_count(&documents, b"abcd");
    let index = TrigramIndex::build(documents);
    let result = index.query(b"abcd");

    assert_eq!(result.exact_matches, expected);
    assert_eq!(result.candidate_documents, 2);
    println!(
        "candidate_documents={} exact_matches={}",
        result.candidate_documents, result.exact_matches
    );
}
