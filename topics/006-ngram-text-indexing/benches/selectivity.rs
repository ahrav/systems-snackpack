//! Compares exact scanning with a document-level trigram filter.
//!
//! The deterministic 6 MiB corpus contains 8,192 documents of 768 bytes. It
//! defines 160 literal slices from the corpus and 160 common or adversarial
//! needles. A timed invocation runs both query classes against one search
//! method.
//!
//! `selective_ns` and `common_ns` each cover one complete query batch after four
//! untimed warm-up queries. They exclude process startup, corpus and query
//! construction, index construction, candidate diagnostics, and output.
//! `data_ns` reports corpus and query construction; `build_ns` reports index
//! construction and is zero for scanning.
//!
//! Treat each process invocation, not an inner-loop query, as a replication
//! unit. External runs must balance method order and `--workload-order` because
//! this binary records both query classes for only one method.

use std::{env, hint::black_box, process, time::Instant};

use systems_snackpack_topic_006::{TrigramIndex, scan_count};

const DOCUMENTS: usize = 8_192;
const DOCUMENT_BYTES: usize = 768;
const QUERIES: usize = 160;
const ALPHABET: u8 = 16;

#[derive(Clone, Copy)]
enum Method {
    Scan,
    Index,
}

enum Backend {
    Scan(Vec<Vec<u8>>),
    Index(TrigramIndex),
}

fn next_u64(state: &mut u64) -> u64 {
    // Advance the fixed-seed xorshift generator used only for reproducible
    // corpus bytes.
    let mut value = *state;
    value ^= value << 13;
    value ^= value >> 7;
    value ^= value << 17;
    *state = value;
    value
}

fn make_corpus() -> Vec<Vec<u8>> {
    // Combine fixed-seed bytes with shared structures that control posting
    // selectivity. Every document receives a 32-byte `a` prefix, the same gram
    // motif, and one byte that cycles through the 16-symbol alphabet.
    let mut state = 0x9e37_79b9_7f4a_7c15_u64;
    let mut documents = Vec::with_capacity(DOCUMENTS);

    for document_id in 0..DOCUMENTS {
        let mut document = vec![0_u8; DOCUMENT_BYTES];
        for byte in &mut document {
            *byte = b'a' + (next_u64(&mut state) as u8 % ALPHABET);
        }

        document[..32].fill(b'a');
        let motifs = b"cccaabcccabacccbaaccc";
        document[40..40 + motifs.len()].copy_from_slice(motifs);
        document[80] = b'a' + (document_id as u8 % ALPHABET);
        documents.push(document);
    }
    documents
}

fn make_queries(documents: &[Vec<u8>]) -> (Vec<Vec<u8>>, Vec<Vec<u8>>) {
    // Build one class from 12-byte corpus slices beyond the injected structures.
    // The second class alternates literals guaranteed by the shared `a` prefix
    // with literals whose grams occur in every document but whose order and
    // distance require exact verification.
    let mut selective = Vec::with_capacity(QUERIES);
    for query_id in 0..QUERIES {
        let document_id = (query_id * 5_003 + 17) % documents.len();
        let offset = 128 + ((query_id * 97) % (DOCUMENT_BYTES - 128 - 12));
        selective.push(documents[document_id][offset..offset + 12].to_vec());
    }

    let common_needles: [&[u8]; 4] = [
        b"aaaaaaaa",
        b"aaaaaaaaaaaa",
        b"aaaaaaaaaaaaaaaa",
        b"aaaaaaaaaaaaaaaaaaaaaaaa",
    ];
    let adversarial_needles: [&[u8]; 4] = [b"aaaabaaaa", b"baaaabaaa", b"abaaabaaa", b"aabaaabaa"];
    let mut common_adversarial = Vec::with_capacity(QUERIES);
    for query_id in 0..QUERIES {
        let needle = if query_id % 2 == 0 {
            common_needles[(query_id / 2) % common_needles.len()]
        } else {
            adversarial_needles[(query_id / 2) % adversarial_needles.len()]
        };
        common_adversarial.push(needle.to_vec());
    }

    (selective, common_adversarial)
}

fn result_hash(current: u64, query_id: usize, count: usize) -> u64 {
    // Fold every result and its query position into a deterministic diagnostic;
    // the digest is not a substitute for the per-query assertions in `verify`.
    current
        .rotate_left(9)
        .wrapping_add((count as u64).wrapping_mul(0x9e37_79b9))
        ^ query_id as u64
}

fn run_queries(backend: &Backend, queries: &[Vec<u8>]) -> u64 {
    // Keep the complete batch observable to the optimizer through its final
    // digest instead of retaining each query result.
    let mut hash = 0x243f_6a88_85a3_08d3_u64;
    for (query_id, query) in queries.iter().enumerate() {
        let count = match backend {
            Backend::Scan(documents) => scan_count(documents, query),
            Backend::Index(index) => index.query(query).exact_matches,
        };
        hash = result_hash(hash, query_id, count);
    }
    black_box(hash)
}

fn candidate_total(backend: &Backend, queries: &[Vec<u8>]) -> usize {
    // Compute candidate diagnostics outside timed regions. The index path
    // reruns exact verification as part of `query`; that work does not enter
    // `selective_ns` or `common_ns`.
    match backend {
        Backend::Scan(documents) => documents.len() * queries.len(),
        Backend::Index(index) => queries
            .iter()
            .map(|query| index.query(query).candidate_documents)
            .sum(),
    }
}

fn time_workload(backend: &Backend, queries: &[Vec<u8>]) -> (u128, u64) {
    // Measure one complete batch after warming the first four queries. The
    // interval contains only `run_queries` and excludes caller-side setup and
    // diagnostics.
    black_box(run_queries(backend, &queries[..4]));
    let start = Instant::now();
    let hash = run_queries(backend, queries);
    (start.elapsed().as_nanos(), hash)
}

fn verify(documents: Vec<Vec<u8>>, selective: &[Vec<u8>], common: &[Vec<u8>]) {
    // Compare every indexed count with a precomputed scan result before emitting
    // hashes and candidate totals for the two query classes.
    let expected = selective
        .iter()
        .chain(common)
        .map(|query| scan_count(&documents, query))
        .collect::<Vec<_>>();
    let index = TrigramIndex::build(documents);

    for (query, expected) in selective.iter().chain(common).zip(expected) {
        assert_eq!(index.query(query).exact_matches, expected);
    }

    let backend = Backend::Index(index);
    let selective_hash = run_queries(&backend, selective);
    let common_hash = run_queries(&backend, common);
    println!(
        "VERIFY status=ok checked={} selective_hash={} common_hash={} selective_candidates={} common_candidates={}",
        selective.len() + common.len(),
        selective_hash,
        common_hash,
        candidate_total(&backend, selective),
        candidate_total(&backend, common),
    );
}

fn argument<'a>(arguments: &'a [String], name: &str) -> Option<&'a str> {
    arguments
        .windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].as_str())
}

fn main() {
    let arguments = env::args().collect::<Vec<_>>();
    let workload_order = argument(&arguments, "--workload-order").unwrap_or("selective-first");

    let data_start = Instant::now();
    let documents = make_corpus();
    let (selective, common) = make_queries(&documents);
    let data_ns = data_start.elapsed().as_nanos();

    if arguments.iter().any(|argument| argument == "--verify")
        || argument(&arguments, "--method").is_none()
    {
        verify(documents, &selective, &common);
        return;
    }

    let method = match argument(&arguments, "--method") {
        Some("scan") => Method::Scan,
        Some("index") => Method::Index,
        Some(other) => panic!("unknown method {other}; use scan or index"),
        None => unreachable!("missing method is handled above"),
    };

    let (backend, build_ns) = match method {
        Method::Scan => (Backend::Scan(documents), 0),
        Method::Index => {
            let build_start = Instant::now();
            let index = TrigramIndex::build(documents);
            (Backend::Index(index), build_start.elapsed().as_nanos())
        }
    };

    let ((selective_ns, selective_hash), (common_ns, common_hash)) = match workload_order {
        "selective-first" => {
            let selective_result = time_workload(&backend, &selective);
            let common_result = time_workload(&backend, &common);
            (selective_result, common_result)
        }
        "common-first" => {
            let common_result = time_workload(&backend, &common);
            let selective_result = time_workload(&backend, &selective);
            (selective_result, common_result)
        }
        other => panic!("unknown workload order {other}"),
    };

    println!(
        "RESULT pid={} method={} workload_order={} corpus_bytes={} documents={} document_bytes={} queries={} data_ns={} build_ns={} selective_ns={} selective_hash={} selective_candidates={} common_ns={} common_hash={} common_candidates={}",
        process::id(),
        match method {
            Method::Scan => "scan",
            Method::Index => "index",
        },
        workload_order,
        DOCUMENTS * DOCUMENT_BYTES,
        DOCUMENTS,
        DOCUMENT_BYTES,
        QUERIES,
        data_ns,
        build_ns,
        selective_ns,
        selective_hash,
        candidate_total(&backend, &selective),
        common_ns,
        common_hash,
        candidate_total(&backend, &common),
    );
}
