//! Checked models for compression-path costs, representation fallback, decoder
//! budgets, and independently decodable units.
//!
//! This crate deliberately does not implement a compression algorithm. It
//! models the system around a codec: saved I/O bytes, codec time, raw fallback,
//! caller-owned resource limits, and the bytes a point read must decode. The
//! Linux experiment links the zstd and LZ4 C libraries so codec implementation
//! details do not become hidden Rust dependencies.
//!
//! # Example
//!
//! ```
//! use compression_systems_primitive::{CostInputs, estimate_serial_path};
//!
//! let estimate = estimate_serial_path(CostInputs {
//!     original_bytes: 1_000_000,
//!     encoded_bytes: 400_000,
//!     io_bytes_per_second: 100_000_000,
//!     codec_bytes_per_second: 500_000_000,
//!     fixed_codec_ns: 20_000,
//! })?;
//! assert!(estimate.compression_wins);
//! assert_eq!(estimate.saved_bytes, 600_000);
//! # Ok::<(), compression_systems_primitive::ModelError>(())
//! ```

use std::fmt;

const NANOS_PER_SECOND: u128 = 1_000_000_000;

/// The byte representation selected for one independently addressable unit.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Codec {
    /// Bytes are stored unchanged.
    Identity,
    /// Bytes the caller identifies as a complete zstd frame.
    ///
    /// This crate accounts for the bytes but does not validate zstd grammar.
    ZstdFrame,
    /// Bytes the caller identifies as an LZ4 raw block, wrapped by this crate.
    ///
    /// This crate validates its wrapper, not the payload's LZ4 grammar.
    Lz4RawBlock,
}

/// An invalid input or arithmetic result in a checked compression model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ModelError {
    /// A rate used as a divisor was zero.
    ZeroRate,
    /// A unit size was zero.
    ZeroUnitSize,
    /// A ratio numerator or denominator was zero.
    ZeroRatioTerm,
    /// Integer arithmetic exceeded the selected representation.
    ArithmeticOverflow,
    /// A read range extends past the logical object.
    ReadOutsideObject,
    /// Raw fallback was asked to evaluate the identity representation as a candidate.
    IdentityIsNotCandidate,
    /// A length cannot be represented by the fixed-width LZ4 raw-block header.
    LengthDoesNotFitHeader,
    /// The LZ4 raw-block wrapper is missing bytes or has the wrong magic value.
    InvalidLz4RawHeader,
    /// The LZ4 raw-block wrapper length does not exactly match its payload.
    InvalidLz4RawLength,
    /// A decoder budget would be exceeded.
    DecoderBudgetExceeded(BudgetDimension),
}

impl fmt::Display for ModelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ZeroRate => formatter.write_str("rate must be greater than zero"),
            Self::ZeroUnitSize => formatter.write_str("unit size must be greater than zero"),
            Self::ZeroRatioTerm => formatter.write_str("ratio terms must be greater than zero"),
            Self::ArithmeticOverflow => formatter.write_str("checked arithmetic overflowed"),
            Self::ReadOutsideObject => formatter.write_str("read extends outside the object"),
            Self::IdentityIsNotCandidate => {
                formatter.write_str("identity is the fallback, not a compressed candidate")
            }
            Self::LengthDoesNotFitHeader => {
                formatter.write_str("length does not fit the LZ4 raw-block header")
            }
            Self::InvalidLz4RawHeader => formatter.write_str("invalid LZ4 raw-block header"),
            Self::InvalidLz4RawLength => formatter.write_str("invalid LZ4 raw-block length"),
            Self::DecoderBudgetExceeded(dimension) => {
                write!(formatter, "decoder budget exceeded: {dimension}")
            }
        }
    }
}

impl std::error::Error for ModelError {}

/// Inputs to the serial, no-overlap latency model.
///
/// Byte rates are measured in uncompressed bytes per second for the codec and
/// physical bytes per second for I/O. The model adds codec and I/O time. It is
/// a filter for candidate configurations, not a queueing or contention model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CostInputs {
    /// Bytes presented to the encoder or returned by the decoder.
    pub original_bytes: u64,
    /// Total bytes stored or transferred, including frame and container overhead.
    pub encoded_bytes: u64,
    /// Physical storage or network bandwidth in bytes per second.
    pub io_bytes_per_second: u64,
    /// Codec throughput in uncompressed bytes per second.
    pub codec_bytes_per_second: u64,
    /// Fixed setup and framing time for the modeled unit, in nanoseconds.
    pub fixed_codec_ns: u64,
}

/// A latency comparison produced by [`estimate_serial_path`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PathEstimate {
    /// Raw I/O time rounded up to a whole nanosecond.
    pub raw_ns: u128,
    /// Codec time plus encoded I/O time, rounded up per term.
    pub compressed_ns: u128,
    /// Bytes avoided by the encoded representation, or zero if it expanded.
    pub saved_bytes: u64,
    /// Whether the modeled compressed path is strictly faster.
    pub compression_wins: bool,
}

/// Estimates raw and compressed latency when codec work and I/O do not overlap.
///
/// The calculation uses checked integer arithmetic and rounds each duration up.
/// It does not include queueing, allocation, copies, cache effects, startup, or
/// interference from concurrent work; those belong in the end-to-end experiment.
///
/// # Errors
///
/// Returns [`ModelError::ZeroRate`] if either byte rate is zero. The full `u64`
/// input domain fits in the model's `u128` duration intermediates.
pub fn estimate_serial_path(inputs: CostInputs) -> Result<PathEstimate, ModelError> {
    if inputs.io_bytes_per_second == 0 || inputs.codec_bytes_per_second == 0 {
        return Err(ModelError::ZeroRate);
    }

    let raw_ns = duration_ns(inputs.original_bytes, inputs.io_bytes_per_second)?;
    let codec_ns = duration_ns(inputs.original_bytes, inputs.codec_bytes_per_second)?
        .checked_add(u128::from(inputs.fixed_codec_ns))
        .ok_or(ModelError::ArithmeticOverflow)?;
    let encoded_io_ns = duration_ns(inputs.encoded_bytes, inputs.io_bytes_per_second)?;
    let compressed_ns = codec_ns
        .checked_add(encoded_io_ns)
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(PathEstimate {
        raw_ns,
        compressed_ns,
        saved_bytes: inputs.original_bytes.saturating_sub(inputs.encoded_bytes),
        compression_wins: compressed_ns < raw_ns,
    })
}

fn duration_ns(bytes: u64, bytes_per_second: u64) -> Result<u128, ModelError> {
    let numerator = u128::from(bytes)
        .checked_mul(NANOS_PER_SECOND)
        .ok_or(ModelError::ArithmeticOverflow)?;
    checked_ceil_div(numerator, u128::from(bytes_per_second))
}

fn checked_ceil_div(numerator: u128, denominator: u128) -> Result<u128, ModelError> {
    if denominator == 0 {
        return Err(ModelError::ZeroRate);
    }
    if numerator == 0 {
        return Ok(0);
    }
    numerator
        .checked_sub(1)
        .and_then(|value| value.checked_div(denominator))
        .and_then(|value| value.checked_add(1))
        .ok_or(ModelError::ArithmeticOverflow)
}

/// Bytes in the explicit wrapper around one LZ4 raw block.
///
/// Raw LZ4 blocks are not self-delimiting. This teaching wrapper stores a
/// four-byte magic value followed by little-endian encoded and decoded `u32`
/// lengths. It is a local experiment contract, not the LZ4 frame format.
pub const LZ4_RAW_HEADER_LEN: usize = 12;

/// Bytes used by the teaching container to select identity, zstd, or LZ4.
pub const STORED_CODEC_SELECTOR_LEN: usize = 1;

const LZ4_RAW_MAGIC: [u8; 4] = *b"L4RB";

/// A borrowed view whose wrapper magic and encoded length are validated.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Lz4RawBlock<'a> {
    /// Raw LZ4 block bytes, excluding the teaching wrapper.
    pub payload: &'a [u8],
    /// Caller-declared decoded byte count stored by the wrapper.
    ///
    /// Validate this untrusted value against a caller-owned output budget
    /// before allocating or decoding.
    pub decoded_len: u32,
}

/// Wraps a raw LZ4 block with exact encoded and decoded lengths.
///
/// The payload is assumed to be an LZ4 raw block; this function only supplies
/// the missing boundary metadata. A decoder must still enforce its own output
/// budget before using `decoded_len` for allocation.
///
/// # Errors
///
/// - [`ModelError::LengthDoesNotFitHeader`] if either length exceeds `u32::MAX`.
/// - [`ModelError::ArithmeticOverflow`] if the header and payload length cannot
///   be added as a `usize`.
pub fn frame_lz4_raw_block(payload: &[u8], decoded_len: usize) -> Result<Vec<u8>, ModelError> {
    let encoded_len =
        u32::try_from(payload.len()).map_err(|_| ModelError::LengthDoesNotFitHeader)?;
    let decoded_len = u32::try_from(decoded_len).map_err(|_| ModelError::LengthDoesNotFitHeader)?;
    let total = LZ4_RAW_HEADER_LEN
        .checked_add(payload.len())
        .ok_or(ModelError::ArithmeticOverflow)?;
    let mut framed = Vec::with_capacity(total);
    framed.extend_from_slice(&LZ4_RAW_MAGIC);
    framed.extend_from_slice(&encoded_len.to_le_bytes());
    framed.extend_from_slice(&decoded_len.to_le_bytes());
    framed.extend_from_slice(payload);
    Ok(framed)
}

/// Validates the wrapper and opens a block produced by [`frame_lz4_raw_block`].
///
/// Trailing bytes are rejected because an independently addressed unit must
/// have one unambiguous boundary. This function does not validate LZ4 grammar
/// or prove that decoding produces the declared byte count.
///
/// # Errors
///
/// - [`ModelError::InvalidLz4RawHeader`] if `bytes` is shorter than the
///   12-byte header or has the wrong magic value.
/// - [`ModelError::InvalidLz4RawLength`] if the encoded length does not consume
///   exactly the remaining bytes.
/// - [`ModelError::ArithmeticOverflow`] if the declared encoded length plus
///   the header does not fit in `usize`.
pub fn parse_lz4_raw_block(bytes: &[u8]) -> Result<Lz4RawBlock<'_>, ModelError> {
    if bytes.len() < LZ4_RAW_HEADER_LEN || bytes[..4] != LZ4_RAW_MAGIC {
        return Err(ModelError::InvalidLz4RawHeader);
    }
    let encoded_len = u32::from_le_bytes(
        bytes[4..8]
            .try_into()
            .map_err(|_| ModelError::InvalidLz4RawHeader)?,
    ) as usize;
    let decoded_len = u32::from_le_bytes(
        bytes[8..12]
            .try_into()
            .map_err(|_| ModelError::InvalidLz4RawHeader)?,
    );
    let expected_len = LZ4_RAW_HEADER_LEN
        .checked_add(encoded_len)
        .ok_or(ModelError::ArithmeticOverflow)?;
    if bytes.len() != expected_len {
        return Err(ModelError::InvalidLz4RawLength);
    }
    Ok(Lz4RawBlock {
        payload: &bytes[LZ4_RAW_HEADER_LEN..],
        decoded_len,
    })
}

/// One selected stored representation, including required wrapper bytes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StoredUnit {
    codec: Codec,
    bytes: Vec<u8>,
    decoded_len: usize,
}

impl StoredUnit {
    /// Returns the representation a reader must dispatch to.
    pub fn codec(&self) -> Codec {
        self.codec
    }

    /// Returns exactly the bytes stored for this unit.
    ///
    /// Byte zero is the teaching container's codec selector. The remaining
    /// bytes are raw identity bytes, bytes tagged as a zstd frame, or the
    /// explicit LZ4 wrapper returned by [`frame_lz4_raw_block`]. Codec grammar
    /// remains the caller's responsibility.
    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// Returns the original byte length supplied to [`select_with_raw_fallback`].
    pub fn decoded_len(&self) -> usize {
        self.decoded_len
    }
}

/// Selects a candidate only when its total stored bytes meet the savings gate.
///
/// The caller asserts that `candidate_payload` is a complete zstd frame for
/// [`Codec::ZstdFrame`] or a raw LZ4 block for [`Codec::Lz4RawBlock`]. This
/// function does not validate either codec grammar. Every representation
/// includes a one-byte codec selector, and LZ4 also includes its 12-byte
/// teaching wrapper.
/// If `candidate bytes + minimum_savings` exceeds the serialized identity
/// representation, the returned representation is identity. Equality satisfies
/// the savings gate. The function accounts for candidate bytes but does not
/// parse or decode them.
///
/// # Errors
///
/// - [`ModelError::IdentityIsNotCandidate`] if `candidate_codec` is
///   [`Codec::Identity`].
/// - [`ModelError::LengthDoesNotFitHeader`] if an LZ4 payload length or the
///   original decoded length exceeds `u32::MAX`.
/// - [`ModelError::ArithmeticOverflow`] if wrapper, selector, or savings
///   arithmetic exceeds `usize`.
pub fn select_with_raw_fallback(
    original: &[u8],
    candidate_codec: Codec,
    candidate_payload: &[u8],
    minimum_savings: usize,
) -> Result<StoredUnit, ModelError> {
    let candidate_body = match candidate_codec {
        Codec::Identity => return Err(ModelError::IdentityIsNotCandidate),
        Codec::ZstdFrame => candidate_payload.to_vec(),
        Codec::Lz4RawBlock => frame_lz4_raw_block(candidate_payload, original.len())?,
    };
    let candidate = serialize_stored(candidate_codec, &candidate_body)?;
    let identity = serialize_stored(Codec::Identity, original)?;
    let required_raw_len = candidate
        .len()
        .checked_add(minimum_savings)
        .ok_or(ModelError::ArithmeticOverflow)?;
    if required_raw_len <= identity.len() {
        Ok(StoredUnit {
            codec: candidate_codec,
            bytes: candidate,
            decoded_len: original.len(),
        })
    } else {
        Ok(StoredUnit {
            codec: Codec::Identity,
            bytes: identity,
            decoded_len: original.len(),
        })
    }
}

fn serialize_stored(codec: Codec, body: &[u8]) -> Result<Vec<u8>, ModelError> {
    let total = STORED_CODEC_SELECTOR_LEN
        .checked_add(body.len())
        .ok_or(ModelError::ArithmeticOverflow)?;
    let mut bytes = Vec::with_capacity(total);
    bytes.push(match codec {
        Codec::Identity => 0,
        Codec::ZstdFrame => 1,
        Codec::Lz4RawBlock => 2,
    });
    bytes.extend_from_slice(body);
    Ok(bytes)
}

/// A resource dimension controlled by [`DecoderBudget`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BudgetDimension {
    /// Total accepted compressed input bytes.
    InputBytes,
    /// Total bytes the decoder may produce.
    OutputBytes,
    /// Per-unit history window or dictionary memory.
    WindowBytes,
    /// Aggregate decoder, dictionary, and temporary memory across units.
    MemoryBytes,
    /// Number of independently framed units.
    Units,
    /// Caller-defined CPU or instruction work units.
    Work,
    /// Aggregate decoded-to-input expansion ratio.
    ExpansionRatio,
}

impl fmt::Display for BudgetDimension {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let name = match self {
            Self::InputBytes => "input bytes",
            Self::OutputBytes => "output bytes",
            Self::WindowBytes => "window bytes",
            Self::MemoryBytes => "aggregate memory bytes",
            Self::Units => "unit count",
            Self::Work => "work units",
            Self::ExpansionRatio => "expansion ratio",
        };
        formatter.write_str(name)
    }
}

/// A maximum aggregate expansion ratio expressed exactly as `output / input`.
///
/// [`DecoderLedger::try_admit`] rejects a limit with either term set to zero.
/// Admission otherwise requires
/// `decoded_bytes * input <= compressed_bytes * output`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ExpansionLimit {
    /// Maximum output-side ratio term.
    pub output: u64,
    /// Input-side ratio term.
    pub input: u64,
}

/// Caller-owned limits for a complete decode request, including nested units.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DecoderBudget {
    /// Maximum aggregate compressed bytes.
    pub max_input_bytes: u64,
    /// Maximum aggregate decoded bytes.
    pub max_output_bytes: u64,
    /// Maximum window or dictionary memory requested by any single unit.
    pub max_window_bytes: u64,
    /// Maximum aggregate decoder, dictionary, and temporary memory.
    pub max_memory_bytes: u64,
    /// Maximum number of independently framed units.
    pub max_units: u64,
    /// Maximum caller-defined work units across the request.
    pub max_work: u64,
    /// Optional secondary expansion guard; absolute caps remain primary.
    pub max_expansion: Option<ExpansionLimit>,
}

/// Resource claims for one decoder operation.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DecodeClaim {
    /// Compressed bytes consumed by this operation.
    pub input_bytes: u64,
    /// Maximum decoded bytes this operation may produce.
    pub output_bytes: u64,
    /// Window or dictionary memory required by this operation.
    pub window_bytes: u64,
    /// Decoder, dictionary, and temporary memory reserved by this operation.
    ///
    /// This is aggregate accounting and should include `window_bytes` rather
    /// than treating the per-unit window check as a substitute.
    pub memory_bytes: u64,
    /// Caller-defined estimate of CPU or instruction work.
    pub work: u64,
}

/// Accepted aggregate decoder use.
///
/// [`DecoderLedger::try_admit`] returns a new value. A rejected claim therefore
/// cannot partially update accounting.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct DecoderLedger {
    input_bytes: u64,
    output_bytes: u64,
    units: u64,
    work: u64,
    memory_bytes: u64,
}

impl DecoderLedger {
    /// Returns aggregate accepted compressed bytes.
    pub fn input_bytes(&self) -> u64 {
        self.input_bytes
    }

    /// Returns aggregate accepted output bytes.
    pub fn output_bytes(&self) -> u64 {
        self.output_bytes
    }

    /// Returns the number of accepted units.
    pub fn units(&self) -> u64 {
        self.units
    }

    /// Returns aggregate caller-defined work units.
    pub fn work(&self) -> u64 {
        self.work
    }

    /// Returns aggregate accepted decoder, dictionary, and temporary memory.
    pub fn memory_bytes(&self) -> u64 {
        self.memory_bytes
    }

    /// Checks one claim against absolute and optional ratio limits.
    ///
    /// The expansion comparison uses aggregate request totals, so splitting a
    /// nested object into many individually acceptable frames cannot reset the
    /// budget. Limits are inclusive. When an expansion limit is enabled, an
    /// empty aggregate input may produce only empty output.
    ///
    /// # Errors
    ///
    /// - [`ModelError::DecoderBudgetExceeded`] with the failing
    ///   [`BudgetDimension`] if the claim exceeds a per-unit or aggregate limit.
    /// - [`ModelError::ZeroRatioTerm`] if either term of an enabled expansion
    ///   limit is zero and earlier absolute-limit checks pass.
    /// - [`ModelError::ArithmeticOverflow`] if aggregate `u64` accounting
    ///   overflows.
    pub fn try_admit(self, budget: DecoderBudget, claim: DecodeClaim) -> Result<Self, ModelError> {
        if claim.window_bytes > budget.max_window_bytes {
            return Err(ModelError::DecoderBudgetExceeded(
                BudgetDimension::WindowBytes,
            ));
        }
        let next = Self {
            input_bytes: checked_add_budget(
                self.input_bytes,
                claim.input_bytes,
                budget.max_input_bytes,
                BudgetDimension::InputBytes,
            )?,
            output_bytes: checked_add_budget(
                self.output_bytes,
                claim.output_bytes,
                budget.max_output_bytes,
                BudgetDimension::OutputBytes,
            )?,
            units: checked_add_budget(self.units, 1, budget.max_units, BudgetDimension::Units)?,
            work: checked_add_budget(
                self.work,
                claim.work,
                budget.max_work,
                BudgetDimension::Work,
            )?,
            memory_bytes: checked_add_budget(
                self.memory_bytes,
                claim.memory_bytes,
                budget.max_memory_bytes,
                BudgetDimension::MemoryBytes,
            )?,
        };
        if let Some(limit) = budget.max_expansion {
            if limit.output == 0 || limit.input == 0 {
                return Err(ModelError::ZeroRatioTerm);
            }
            if next.input_bytes == 0 {
                if next.output_bytes != 0 {
                    return Err(ModelError::DecoderBudgetExceeded(
                        BudgetDimension::ExpansionRatio,
                    ));
                }
            } else {
                let left = u128::from(next.output_bytes)
                    .checked_mul(u128::from(limit.input))
                    .ok_or(ModelError::ArithmeticOverflow)?;
                let right = u128::from(next.input_bytes)
                    .checked_mul(u128::from(limit.output))
                    .ok_or(ModelError::ArithmeticOverflow)?;
                if left > right {
                    return Err(ModelError::DecoderBudgetExceeded(
                        BudgetDimension::ExpansionRatio,
                    ));
                }
            }
        }
        Ok(next)
    }
}

fn checked_add_budget(
    current: u64,
    added: u64,
    limit: u64,
    dimension: BudgetDimension,
) -> Result<u64, ModelError> {
    let next = current
        .checked_add(added)
        .ok_or(ModelError::ArithmeticOverflow)?;
    if next > limit {
        return Err(ModelError::DecoderBudgetExceeded(dimension));
    }
    Ok(next)
}

/// Full-unit decoding required for one logical contiguous read.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ReadAmplification {
    /// Bytes requested by the caller.
    pub requested_bytes: u64,
    /// Bytes produced when every touched unit must be decoded in full.
    pub decoded_bytes: u64,
    /// Number of independently decodable units touched.
    pub units_touched: u64,
}

impl ReadAmplification {
    /// Returns decoded bytes divided by requested bytes.
    ///
    /// An empty read returns `1.0` by convention because it performs no work.
    pub fn factor(self) -> f64 {
        if self.requested_bytes == 0 {
            1.0
        } else {
            self.decoded_bytes as f64 / self.requested_bytes as f64
        }
    }
}

/// Computes point-read amplification for fixed, independently decoded units.
///
/// The final unit may be shorter than `unit_bytes`. The calculation assumes an
/// index already supplies exact unit boundaries; independence alone does not
/// provide that index. All sizes and `read_offset` are byte counts measured from
/// the start of the logical object. An empty read at the object end is valid.
///
/// # Errors
///
/// - [`ModelError::ZeroUnitSize`] if `unit_bytes` is zero.
/// - [`ModelError::ReadOutsideObject`] if the representable read range lies
///   beyond `object_bytes`.
/// - [`ModelError::ArithmeticOverflow`] if a range end or unit boundary does
///   not fit in `u64`.
pub fn fixed_unit_read_amplification(
    object_bytes: u64,
    unit_bytes: u64,
    read_offset: u64,
    read_bytes: u64,
) -> Result<ReadAmplification, ModelError> {
    if unit_bytes == 0 {
        return Err(ModelError::ZeroUnitSize);
    }
    let read_end = read_offset
        .checked_add(read_bytes)
        .ok_or(ModelError::ArithmeticOverflow)?;
    if read_offset > object_bytes || read_end > object_bytes {
        return Err(ModelError::ReadOutsideObject);
    }
    if read_bytes == 0 {
        return Ok(ReadAmplification {
            requested_bytes: 0,
            decoded_bytes: 0,
            units_touched: 0,
        });
    }

    let first_unit = read_offset / unit_bytes;
    let last_unit = (read_end - 1) / unit_bytes;
    let first_start = first_unit
        .checked_mul(unit_bytes)
        .ok_or(ModelError::ArithmeticOverflow)?;
    let last_start = last_unit
        .checked_mul(unit_bytes)
        .ok_or(ModelError::ArithmeticOverflow)?;
    let last_end = last_start
        .checked_add(unit_bytes)
        .ok_or(ModelError::ArithmeticOverflow)?
        .min(object_bytes);
    let decoded_bytes = last_end
        .checked_sub(first_start)
        .ok_or(ModelError::ArithmeticOverflow)?;
    let units_touched = last_unit
        .checked_sub(first_unit)
        .and_then(|count| count.checked_add(1))
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(ReadAmplification {
        requested_bytes: read_bytes,
        decoded_bytes,
        units_touched,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serial_model_includes_fixed_cost_and_saved_io() {
        let estimate = estimate_serial_path(CostInputs {
            original_bytes: 1_000_000,
            encoded_bytes: 400_000,
            io_bytes_per_second: 100_000_000,
            codec_bytes_per_second: 500_000_000,
            fixed_codec_ns: 20_000,
        })
        .unwrap();
        assert_eq!(estimate.raw_ns, 10_000_000);
        assert_eq!(estimate.compressed_ns, 6_020_000);
        assert_eq!(estimate.saved_bytes, 600_000);
        assert!(estimate.compression_wins);
    }

    #[test]
    fn serial_model_rounds_up_and_rejects_zero_rates() {
        let estimate = estimate_serial_path(CostInputs {
            original_bytes: 1,
            encoded_bytes: 1,
            io_bytes_per_second: 3,
            codec_bytes_per_second: 3,
            fixed_codec_ns: 0,
        })
        .unwrap();
        assert_eq!(estimate.raw_ns, 333_333_334);
        assert_eq!(estimate.compressed_ns, 666_666_668);
        assert_eq!(
            estimate_serial_path(CostInputs {
                io_bytes_per_second: 0,
                ..CostInputs {
                    original_bytes: 1,
                    encoded_bytes: 1,
                    io_bytes_per_second: 1,
                    codec_bytes_per_second: 1,
                    fixed_codec_ns: 0,
                }
            }),
            Err(ModelError::ZeroRate)
        );
    }

    #[test]
    fn lz4_raw_wrapper_is_exact_and_rejects_trailing_bytes() {
        let framed = frame_lz4_raw_block(b"block", 42).unwrap();
        let parsed = parse_lz4_raw_block(&framed).unwrap();
        assert_eq!(parsed.payload, b"block");
        assert_eq!(parsed.decoded_len, 42);

        let mut trailing = framed.clone();
        trailing.push(0);
        assert_eq!(
            parse_lz4_raw_block(&trailing),
            Err(ModelError::InvalidLz4RawLength)
        );
        assert_eq!(
            parse_lz4_raw_block(b"short"),
            Err(ModelError::InvalidLz4RawHeader)
        );
    }

    #[test]
    fn fallback_counts_lz4_wrapper_bytes() {
        let original = [7_u8; 20];
        let falls_back =
            select_with_raw_fallback(&original, Codec::Lz4RawBlock, &[1; 8], 1).unwrap();
        assert_eq!(falls_back.codec(), Codec::Identity);
        assert_eq!(falls_back.bytes()[0], 0);
        assert_eq!(&falls_back.bytes()[1..], original);

        let compressed =
            select_with_raw_fallback(&original, Codec::Lz4RawBlock, &[1; 7], 1).unwrap();
        assert_eq!(compressed.codec(), Codec::Lz4RawBlock);
        assert_eq!(compressed.bytes()[0], 2);
        assert_eq!(compressed.bytes().len(), 20);
        assert_eq!(compressed.decoded_len(), original.len());
    }

    #[test]
    fn fallback_rejects_identity_and_checked_savings_overflow() {
        assert_eq!(
            select_with_raw_fallback(b"x", Codec::Identity, b"x", 0),
            Err(ModelError::IdentityIsNotCandidate)
        );
        assert_eq!(
            select_with_raw_fallback(b"x", Codec::ZstdFrame, b"z", usize::MAX),
            Err(ModelError::ArithmeticOverflow)
        );
    }

    fn budget() -> DecoderBudget {
        DecoderBudget {
            max_input_bytes: 100,
            max_output_bytes: 500,
            max_window_bytes: 64,
            max_memory_bytes: 128,
            max_units: 2,
            max_work: 1_000,
            max_expansion: Some(ExpansionLimit {
                output: 5,
                input: 1,
            }),
        }
    }

    #[test]
    fn decoder_budget_is_aggregate_and_transactional() {
        let ledger = DecoderLedger::default()
            .try_admit(
                budget(),
                DecodeClaim {
                    input_bytes: 50,
                    output_bytes: 200,
                    window_bytes: 64,
                    memory_bytes: 64,
                    work: 100,
                },
            )
            .unwrap();
        assert_eq!((ledger.input_bytes(), ledger.output_bytes()), (50, 200));
        let rejected = ledger.try_admit(
            budget(),
            DecodeClaim {
                input_bytes: 1,
                output_bytes: 100,
                window_bytes: 1,
                memory_bytes: 1,
                work: 1,
            },
        );
        assert_eq!(
            rejected,
            Err(ModelError::DecoderBudgetExceeded(
                BudgetDimension::ExpansionRatio
            ))
        );
        assert_eq!((ledger.input_bytes(), ledger.output_bytes()), (50, 200));
    }

    #[test]
    fn decoder_budget_checks_absolute_dimensions() {
        let claim = DecodeClaim {
            input_bytes: 1,
            output_bytes: 1,
            window_bytes: 65,
            memory_bytes: 65,
            work: 1,
        };
        assert_eq!(
            DecoderLedger::default().try_admit(budget(), claim),
            Err(ModelError::DecoderBudgetExceeded(
                BudgetDimension::WindowBytes
            ))
        );
        let ledger = DecoderLedger::default()
            .try_admit(
                budget(),
                DecodeClaim {
                    window_bytes: 1,
                    memory_bytes: 1,
                    ..claim
                },
            )
            .unwrap()
            .try_admit(
                budget(),
                DecodeClaim {
                    window_bytes: 1,
                    memory_bytes: 1,
                    ..claim
                },
            )
            .unwrap();
        assert_eq!(ledger.units(), 2);
        assert_eq!(
            ledger.try_admit(
                budget(),
                DecodeClaim {
                    window_bytes: 1,
                    memory_bytes: 1,
                    ..claim
                }
            ),
            Err(ModelError::DecoderBudgetExceeded(BudgetDimension::Units))
        );

        let memory_budget = DecoderBudget {
            max_units: 3,
            max_memory_bytes: 100,
            ..budget()
        };
        let memory_claim = DecodeClaim {
            input_bytes: 1,
            output_bytes: 1,
            window_bytes: 40,
            memory_bytes: 60,
            work: 1,
        };
        let memory_ledger = DecoderLedger::default()
            .try_admit(memory_budget, memory_claim)
            .unwrap();
        assert_eq!(memory_ledger.memory_bytes(), 60);
        assert_eq!(
            memory_ledger.try_admit(memory_budget, memory_claim),
            Err(ModelError::DecoderBudgetExceeded(
                BudgetDimension::MemoryBytes
            ))
        );
    }

    #[test]
    fn read_amplification_respects_partial_final_unit() {
        let one_byte = fixed_unit_read_amplification(10_000, 4_096, 4_095, 2).unwrap();
        assert_eq!(one_byte.requested_bytes, 2);
        assert_eq!(one_byte.decoded_bytes, 8_192);
        assert_eq!(one_byte.units_touched, 2);
        assert_eq!(one_byte.factor(), 4_096.0);

        let tail = fixed_unit_read_amplification(10_000, 4_096, 9_999, 1).unwrap();
        assert_eq!(tail.decoded_bytes, 1_808);
        assert_eq!(tail.units_touched, 1);
        let empty = fixed_unit_read_amplification(10_000, 4_096, 10_000, 0).unwrap();
        assert_eq!(empty.factor(), 1.0);
    }

    #[test]
    fn read_amplification_rejects_invalid_ranges() {
        assert_eq!(
            fixed_unit_read_amplification(10, 0, 0, 1),
            Err(ModelError::ZeroUnitSize)
        );
        assert_eq!(
            fixed_unit_read_amplification(10, 4, 9, 2),
            Err(ModelError::ReadOutsideObject)
        );
        assert_eq!(
            fixed_unit_read_amplification(u64::MAX, 4, u64::MAX, 1),
            Err(ModelError::ArithmeticOverflow)
        );
    }
}
