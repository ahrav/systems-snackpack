//! Analysis primitives for the Topic 17 dynamic-binding experiment.
//!
//! The experiment treats one complete `ABBA` or `BAAB` block as an independent
//! observation. Calls inside a process and positions inside a block remain
//! subsamples.

/// Summary of positive block ratios in log space.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RatioEstimate {
    /// Number of complete blocks in the estimate.
    pub blocks: usize,
    /// Geometric mean of the numerator/denominator block ratios.
    pub geometric_mean: f64,
    /// Sample standard deviation across the block log contrasts.
    pub log_ratio_sd: f64,
    /// Lower endpoint of the two-sided 95% interval.
    pub t95_low: f64,
    /// Upper endpoint of the two-sided 95% interval.
    pub t95_high: f64,
}

/// Returns the log contrast for one balanced four-position block.
///
/// `labels` must contain two `A` and two `B` entries. The result is the log of
/// the geometric `B/A` ratio. This definition works for both `ABBA` and `BAAB`
/// without treating the four positions as independent observations.
///
/// Returns `None` when a label is invalid, a duration is non-finite or
/// non-positive, or either label does not occur twice.
pub fn block_log_contrast(labels: [char; 4], durations: [f64; 4]) -> Option<f64> {
    let mut a = Vec::with_capacity(2);
    let mut b = Vec::with_capacity(2);

    for (label, duration) in labels.into_iter().zip(durations) {
        if !duration.is_finite() || duration <= 0.0 {
            return None;
        }
        match label {
            'A' => a.push(duration.ln()),
            'B' => b.push(duration.ln()),
            _ => return None,
        }
    }

    if a.len() != 2 || b.len() != 2 {
        return None;
    }
    Some((b[0] + b[1] - a[0] - a[1]) / 2.0)
}

/// Summarizes independent block log contrasts.
///
/// The 95% interval uses a Student-t critical value for 2 through 31 blocks and
/// the normal critical value above 31 blocks. The interval covers variation
/// among the supplied blocks. It does not cover other builds, hosts, workloads,
/// or run windows.
///
/// Returns `None` for fewer than two blocks or any non-finite contrast.
pub fn summarize_log_contrasts(contrasts: &[f64]) -> Option<RatioEstimate> {
    if contrasts.len() < 2 || contrasts.iter().any(|value| !value.is_finite()) {
        return None;
    }

    let blocks = contrasts.len();
    let mean = contrasts.iter().sum::<f64>() / blocks as f64;
    let variance = contrasts
        .iter()
        .map(|value| {
            let delta = value - mean;
            delta * delta
        })
        .sum::<f64>()
        / (blocks - 1) as f64;
    let log_ratio_sd = variance.sqrt();
    let half_width = t95_critical(blocks - 1) * log_ratio_sd / (blocks as f64).sqrt();

    Some(RatioEstimate {
        blocks,
        geometric_mean: mean.exp(),
        log_ratio_sd,
        t95_low: (mean - half_width).exp(),
        t95_high: (mean + half_width).exp(),
    })
}

fn t95_critical(degrees_of_freedom: usize) -> f64 {
    const VALUES: [f64; 30] = [
        12.706_205, 4.302_653, 3.182_446, 2.776_445, 2.570_582, 2.446_912, 2.364_624, 2.306_004,
        2.262_157, 2.228_139, 2.200_985, 2.178_813, 2.160_369, 2.144_787, 2.131_45, 2.119_905,
        2.109_816, 2.100_922, 2.093_024, 2.085_963, 2.079_614, 2.073_873, 2.068_658, 2.063_899,
        2.059_539, 2.055_529, 2.051_831, 2.048_407, 2.045_23, 2.042_272,
    ];
    VALUES
        .get(degrees_of_freedom.saturating_sub(1))
        .copied()
        .unwrap_or(1.959_964)
}

#[cfg(test)]
mod tests {
    use super::{block_log_contrast, summarize_log_contrasts};

    #[test]
    fn abba_and_baab_have_the_same_contrast() {
        let abba = block_log_contrast(['A', 'B', 'B', 'A'], [10.0, 20.0, 20.0, 10.0])
            .expect("valid ABBA block");
        let baab = block_log_contrast(['B', 'A', 'A', 'B'], [20.0, 10.0, 10.0, 20.0])
            .expect("valid BAAB block");
        assert!((abba.exp() - 2.0).abs() < 8.0 * f64::EPSILON);
        assert!((abba - baab).abs() < f64::EPSILON);
    }

    #[test]
    fn malformed_blocks_are_rejected() {
        assert_eq!(block_log_contrast(['A', 'A', 'A', 'B'], [1.0; 4]), None);
        assert_eq!(
            block_log_contrast(['A', 'B', 'B', 'A'], [1.0, 0.0, 1.0, 1.0]),
            None
        );
    }

    #[test]
    fn constant_ratios_have_a_zero_width_interval() {
        let contrasts = [2.0_f64.ln(); 12];
        let estimate = summarize_log_contrasts(&contrasts).expect("twelve blocks");
        assert_eq!(estimate.blocks, 12);
        assert!((estimate.geometric_mean - 2.0).abs() < f64::EPSILON);
        assert!((estimate.t95_low - 2.0).abs() < f64::EPSILON);
        assert!((estimate.t95_high - 2.0).abs() < f64::EPSILON);
    }

    #[test]
    fn summary_requires_two_finite_blocks() {
        assert_eq!(summarize_log_contrasts(&[0.0]), None);
        assert_eq!(summarize_log_contrasts(&[0.0, f64::NAN]), None);
    }
}
