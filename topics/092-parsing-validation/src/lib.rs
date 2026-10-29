//! Whole-batch parsing of canonical decimal u32 records terminated by LF.
//!
//! Empty input is valid. On failure, output is empty. Capacity is retained.
//! All parsers enforce the same byte grammar and numeric range.
//!
//! ```
//! use parsing_validation::{parse, Strategy};
//! let mut output = Vec::new();
//! let mut offsets = Vec::new();
//! parse(b"12\n0\n4294967295\n", Strategy::Fused, &mut output, &mut offsets).unwrap();
//! assert_eq!(output, [12, 0, u32::MAX]);
//! ```

/// Implementations with identical acceptance and output contracts.
#[derive(Clone, Copy, Debug)]
pub enum Strategy {
    /// One byte scan combines validation, conversion and record detection.
    Fused,
    /// UTF-8 validation, string splitting and standard u32 conversion.
    Split,
    /// Scalar delimiter indexing followed by conversion of each record.
    Indexed,
}

/// Input violates the byte grammar, record framing or u32 range.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Invalid;

/// Parse a complete batch, replacing `output` and reusing its capacity.
///
/// A record is `0\n` or `[1-9][0-9]*\n`, with value at most `u32::MAX`.
/// Errors clear all output. Scratch offsets have no public meaning after return.
/// Resource limits are the caller's responsibility before invoking this function.
/// The input is borrowed only for this call; all successful values are owned.
pub fn parse(
    input: &[u8],
    strategy: Strategy,
    output: &mut Vec<u32>,
    offsets: &mut Vec<usize>,
) -> Result<(), Invalid> {
    output.clear();
    offsets.clear();
    let result = match strategy {
        Strategy::Fused => fused(input, output),
        Strategy::Split => split(input, output),
        Strategy::Indexed => indexed(input, output, offsets),
    };
    if result.is_err() {
        output.clear();
    }
    result
}

fn fused(input: &[u8], output: &mut Vec<u32>) -> Result<(), Invalid> {
    let mut value = 0u32;
    let mut digits = 0usize;
    for &byte in input {
        match byte {
            b'\n' if digits != 0 => {
                output.push(value);
                value = 0;
                digits = 0;
            }
            b'0'..=b'9' => {
                if digits != 0 && value == 0 {
                    return Err(Invalid);
                }
                value = value
                    .checked_mul(10)
                    .and_then(|v| v.checked_add(u32::from(byte - b'0')))
                    .ok_or(Invalid)?;
                digits += 1;
            }
            _ => return Err(Invalid),
        }
    }
    if digits == 0 { Ok(()) } else { Err(Invalid) }
}

fn split(input: &[u8], output: &mut Vec<u32>) -> Result<(), Invalid> {
    let text = std::str::from_utf8(input).map_err(|_| Invalid)?;
    if !text.is_empty() && !text.ends_with('\n') {
        return Err(Invalid);
    }
    for field in text.split_terminator('\n') {
        let bytes = field.as_bytes();
        // Standard unsigned conversion accepts '+'. This protocol does not.
        if bytes.is_empty() || !bytes[0].is_ascii_digit() || (bytes.len() > 1 && bytes[0] == b'0') {
            return Err(Invalid);
        }
        output.push(field.parse::<u32>().map_err(|_| Invalid)?);
    }
    Ok(())
}

fn indexed(input: &[u8], output: &mut Vec<u32>, offsets: &mut Vec<usize>) -> Result<(), Invalid> {
    if !input.is_empty() && input.last() != Some(&b'\n') {
        return Err(Invalid);
    }
    for (index, &byte) in input.iter().enumerate() {
        if byte == b'\n' {
            offsets.push(index);
        }
    }
    let mut start = 0;
    for &end in offsets.iter() {
        let field = &input[start..end];
        if field.is_empty() || (field.len() > 1 && field[0] == b'0') {
            return Err(Invalid);
        }
        let mut value = 0u32;
        for &byte in field {
            if !byte.is_ascii_digit() {
                return Err(Invalid);
            }
            value = value
                .checked_mul(10)
                .and_then(|v| v.checked_add(u32::from(byte - b'0')))
                .ok_or(Invalid)?;
        }
        output.push(value);
        start = end + 1;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    const STRATEGIES: [Strategy; 3] = [Strategy::Fused, Strategy::Split, Strategy::Indexed];

    #[test]
    fn canonical_values_and_empty_batch() {
        for strategy in STRATEGIES {
            let mut output = vec![999];
            let mut scratch = vec![999];
            parse(b"0\n1\n4294967295\n", strategy, &mut output, &mut scratch).unwrap();
            assert_eq!(output, [0, 1, u32::MAX]);
            parse(b"", strategy, &mut output, &mut scratch).unwrap();
            assert!(output.is_empty());
        }
    }

    #[test]
    fn rejects_framing_spelling_encoding_and_range() {
        let bad: &[&[u8]] = &[
            b"\n",
            b"00\n",
            b"01\n",
            b"+1\n",
            b"-0\n",
            b" 1\n",
            b"1 \n",
            b"1\r\n",
            b"1",
            b"4294967296\n",
            b"999999999999999999999\n",
            b"1\n\n",
            b"1\n2",
            b"1\n\xff\n",
            b"1\n\0\n",
            "١\n".as_bytes(),
        ];
        for strategy in STRATEGIES {
            for &input in bad {
                let mut output = vec![123];
                assert_eq!(
                    parse(input, strategy, &mut output, &mut Vec::new()),
                    Err(Invalid)
                );
                assert!(output.is_empty(), "failed batch leaked output");
            }
        }
    }

    #[test]
    fn boundary_values_round_trip() {
        let mut values = vec![0, 1, u32::MAX - 1, u32::MAX];
        for power in 1..=9 {
            let n = 10u32.pow(power);
            values.extend([n - 1, n, n + 1]);
        }
        for n in 0..10_000u32 {
            values.push(n.wrapping_mul(2_654_435_761));
        }
        let input: String = values.iter().map(|n| format!("{n}\n")).collect();
        for strategy in STRATEGIES {
            let mut output = Vec::new();
            parse(input.as_bytes(), strategy, &mut output, &mut Vec::new()).unwrap();
            assert_eq!(output, values);
        }
    }

    #[test]
    fn every_byte_at_every_record_position() {
        let valid = b"12\n0\n4294967295\n";
        for index in 0..valid.len() {
            for byte in 0..=255 {
                let mut input = valid.to_vec();
                input[index] = byte;
                let mut expected = Vec::new();
                let expected_result =
                    parse(&input, Strategy::Split, &mut expected, &mut Vec::new());
                for strategy in [Strategy::Fused, Strategy::Indexed] {
                    let mut output = Vec::new();
                    assert_eq!(
                        parse(&input, strategy, &mut output, &mut Vec::new()),
                        expected_result
                    );
                    assert_eq!(output, expected);
                }
            }
        }
    }
}
