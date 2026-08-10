//! Fresh-process command-line probe for the two index layouts.

use database_index_internals::{
    Corpus, DEFAULT_ENTRIES, DEFAULT_QUERIES, DEFAULT_REPS, Treatment, make_queries, run_treatment,
    validate,
};
use std::process::ExitCode;

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), String> {
    let command = std::env::args()
        .nth(1)
        .ok_or_else(|| "usage: index-layout-probe check|narrow|covering".to_owned())?;
    let entries = env_usize("TOPIC31_ENTRIES", DEFAULT_ENTRIES)?;
    let queries = env_usize("TOPIC31_QUERIES", DEFAULT_QUERIES)?;
    let reps = env_usize("TOPIC31_REPS", DEFAULT_REPS)?;

    if command == "check" {
        let corpus = Corpus::new(entries);
        let query_stream = make_queries(entries, queries);
        validate(&corpus, &query_stream)?;
        let layout = corpus.layout();
        println!(
            "CHECK_OK rows={} queries={} logical_narrow_index={} logical_heap={} logical_covering_index={} rust_narrow_entry={} rust_payload={} rust_covering_entry={}",
            layout.rows,
            queries,
            layout.logical_narrow_index,
            layout.logical_heap,
            layout.logical_covering_index,
            layout.rust_narrow_entry,
            layout.rust_payload,
            layout.rust_covering_entry
        );
        return Ok(());
    }

    let treatment = Treatment::parse(&command).ok_or_else(|| {
        format!("unknown command {command:?}; expected check, narrow, or covering")
    })?;
    let result = run_treatment(treatment, entries, queries, reps)?;
    let lookups = result.queries * result.reps;
    let steady_ns = result.steady.as_nanos();
    let ns_per_lookup = steady_ns as f64 / lookups as f64;
    println!(
        concat!(
            "{{\"treatment\":\"{}\",\"entries\":{},\"queries\":{},\"reps\":{},",
            "\"lookups\":{},\"setup_ns\":{},\"nonsteady_ns\":{},\"steady_ns\":{},",
            "\"ns_per_lookup\":{:.9},\"checksum\":{},",
            "\"logical_narrow_index\":{},\"logical_heap\":{},",
            "\"logical_covering_index\":{},\"rust_narrow_entry\":{},",
            "\"rust_payload\":{},\"rust_covering_entry\":{}}}"
        ),
        result.treatment.as_str(),
        result.entries,
        result.queries,
        result.reps,
        lookups,
        result.setup.as_nanos(),
        result.nonsteady.as_nanos(),
        steady_ns,
        ns_per_lookup,
        result.checksum,
        result.layout.logical_narrow_index,
        result.layout.logical_heap,
        result.layout.logical_covering_index,
        result.layout.rust_narrow_entry,
        result.layout.rust_payload,
        result.layout.rust_covering_entry,
    );
    Ok(())
}

fn env_usize(name: &str, default: usize) -> Result<usize, String> {
    match std::env::var(name) {
        Ok(value) => value
            .parse::<usize>()
            .map_err(|error| format!("invalid {name}={value:?}: {error}"))
            .and_then(|parsed| {
                (parsed > 0)
                    .then_some(parsed)
                    .ok_or_else(|| format!("{name} must be positive"))
            }),
        Err(std::env::VarError::NotPresent) => Ok(default),
        Err(error) => Err(format!("cannot read {name}: {error}")),
    }
}
