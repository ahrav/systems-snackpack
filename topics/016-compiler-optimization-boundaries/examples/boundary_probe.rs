//! Compares a local helper, an imported inlineable helper, and an opaque
//! separately compiled helper.
//!
//! The exported `run_*` wrappers provide stable final-image inspection points.
//! A timing difference does not identify the responsible transformation;
//! inspect the exact linked image used for the measurement.

use compiler_optimization_boundaries::{imported_inline_mix, topic16_opaque_mix};
use std::env;
use std::hint::black_box;
use std::process::ExitCode;
use std::time::Instant;

const DEFAULT_ELEMENTS: usize = 1 << 20;
const DEFAULT_ROUNDS: u32 = 32;
const SALT: u32 = 0x243f_6a88;

#[derive(Clone, Copy)]
enum Mode {
    Local,
    Imported,
    Opaque,
}

impl Mode {
    fn parse(value: &str) -> Result<Self, String> {
        match value {
            "local" => Ok(Self::Local),
            "imported" => Ok(Self::Imported),
            "opaque" => Ok(Self::Opaque),
            _ => Err(format!(
                "unknown mode {value:?}; expected local, imported, or opaque"
            )),
        }
    }

    const fn name(self) -> &'static str {
        match self {
            Self::Local => "local",
            Self::Imported => "imported",
            Self::Opaque => "opaque",
        }
    }
}

#[inline(always)]
fn local_mix(x: u32, salt: u32) -> u32 {
    let y = x ^ salt;
    y.rotate_left(5).wrapping_add(y ^ 0x9e37_79b9)
}

/// Provides a named inspection point for reduction through the local helper.
///
/// The final linked image, rather than the attributes alone, establishes the
/// generated loop body for a particular build.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn run_local(words: &[u32], salt: u32) -> u32 {
    words
        .iter()
        .fold(0u32, |sum, &word| sum.wrapping_add(local_mix(word, salt)))
}

/// Provides a named inspection point for reduction through the imported body.
///
/// The library publishes the helper body, but the final linked image determines
/// whether the caller contains it.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn run_imported(words: &[u32], salt: u32) -> u32 {
    words.iter().fold(0u32, |sum, &word| {
        sum.wrapping_add(imported_inline_mix(word, salt))
    })
}

/// Provides a named inspection point for the separately compiled helper.
///
/// A retained call is evidence for this build, not proof that the C ABI forms
/// an optimizer barrier or that call overhead explains a timing difference.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn run_opaque(words: &[u32], salt: u32) -> u32 {
    words.iter().fold(0u32, |sum, &word| {
        sum.wrapping_add(topic16_opaque_mix(word, salt))
    })
}

fn run(mode: Mode, words: &[u32], salt: u32) -> u32 {
    match mode {
        Mode::Local => run_local(words, salt),
        Mode::Imported => run_imported(words, salt),
        Mode::Opaque => run_opaque(words, salt),
    }
}

fn make_words(elements: usize) -> Vec<u32> {
    let mut state = 0x6a09_e667u32;
    (0..elements)
        .map(|index| {
            state = state.wrapping_mul(1_664_525).wrapping_add(1_013_904_223);
            state ^ (index as u32).rotate_left(11)
        })
        .collect()
}

fn parse_positive<T>(value: Option<String>, default: T, name: &str) -> Result<T, String>
where
    T: std::str::FromStr + PartialEq + Default,
{
    let parsed = match value {
        Some(value) => value
            .parse::<T>()
            .map_err(|_| format!("invalid {name}: {value:?}"))?,
        None => default,
    };
    if parsed == T::default() {
        return Err(format!("{name} must be positive"));
    }
    Ok(parsed)
}

fn execute() -> Result<(), String> {
    let mut args = env::args().skip(1);
    let mode = Mode::parse(args.next().as_deref().unwrap_or("local"))?;
    let elements = parse_positive(args.next(), DEFAULT_ELEMENTS, "elements")?;
    let rounds = parse_positive(args.next(), DEFAULT_ROUNDS, "rounds")?;
    if let Some(extra) = args.next() {
        return Err(format!("unexpected argument: {extra:?}"));
    }

    let words = make_words(elements);
    let local = run_local(&words, SALT);
    assert_eq!(local, run_imported(&words, SALT));
    assert_eq!(local, run_opaque(&words, SALT));

    let _warmup = black_box(run(mode, black_box(&words), SALT ^ 0xa5a5_5a5a));

    let start = Instant::now();
    let mut checksum = 0u32;
    for round in 0..rounds {
        let salt = SALT ^ round.wrapping_mul(0x9e37_79b9).rotate_left(7);
        checksum = checksum.wrapping_add(run(mode, black_box(&words), salt));
    }
    let steady_ns = start.elapsed().as_nanos();

    println!(
        "mode={} elements={} rounds={} checksum={} steady_ns={steady_ns}",
        mode.name(),
        elements,
        rounds,
        black_box(checksum)
    );
    Ok(())
}

fn main() -> ExitCode {
    match execute() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("error: {message}");
            ExitCode::FAILURE
        }
    }
}
