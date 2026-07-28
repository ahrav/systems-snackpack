//! Statistics for the Topic 18 profile-conditioned binary experiment.
//!
//! The experiment treats each four-process `ABBA` or `BAAB` block as one
//! observation. Loop iterations and positions inside a block do not increase
//! the replication count.

/// Geometric ratio estimate over independent process blocks.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct RatioEstimate {
    /// Number of process blocks in the estimate.
    pub blocks: usize,
    /// Geometric mean of the candidate/control block ratios.
    pub geometric_mean: f64,
    /// Sample standard deviation of the block log ratios.
    pub log_ratio_sd: f64,
    /// Lower endpoint of the two-sided 95% Student-t interval.
    pub t95_low: f64,
    /// Upper endpoint of the two-sided 95% Student-t interval.
    pub t95_high: f64,
}

/// Summarizes positive candidate/control ratios in log space.
///
/// The interval covers variation among the supplied blocks. It does not cover
/// other binaries, machines, workloads, or run windows.
///
/// # Examples
///
/// ```
/// use pgo_post_link_optimization::summarize_ratios;
///
/// let estimate = summarize_ratios(&[1.02, 1.02, 1.02]).expect("three valid blocks");
/// assert!((estimate.geometric_mean - 1.02).abs() < 1e-12);
/// ```
///
/// Returns `None` outside the supported range of 2 through 31 blocks or for any
/// non-positive or non-finite ratio.
pub fn summarize_ratios(ratios: &[f64]) -> Option<RatioEstimate> {
    if !(2..=31).contains(&ratios.len())
        || ratios
            .iter()
            .any(|ratio| !ratio.is_finite() || *ratio <= 0.0)
    {
        return None;
    }

    let blocks = ratios.len();
    let logs: Vec<f64> = ratios.iter().map(|ratio| ratio.ln()).collect();
    let mean = logs.iter().sum::<f64>() / blocks as f64;
    let variance = logs
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
    use super::summarize_ratios;

    #[test]
    fn constant_ratios_have_zero_width() {
        let estimate = summarize_ratios(&[1.25; 12]).expect("twelve positive ratios");
        assert_eq!(estimate.blocks, 12);
        assert!((estimate.geometric_mean - 1.25).abs() < f64::EPSILON);
        assert!((estimate.t95_low - 1.25).abs() < f64::EPSILON);
        assert!((estimate.t95_high - 1.25).abs() < f64::EPSILON);
    }

    #[test]
    fn invalid_samples_are_rejected() {
        assert_eq!(summarize_ratios(&[1.0]), None);
        assert_eq!(summarize_ratios(&[1.0; 32]), None);
        assert_eq!(summarize_ratios(&[1.0, 0.0]), None);
        assert_eq!(summarize_ratios(&[1.0, f64::NAN]), None);
    }

    #[test]
    fn geometric_mean_uses_log_space() {
        let estimate = summarize_ratios(&[0.5, 2.0]).expect("two positive ratios");
        assert!((estimate.geometric_mean - 1.0).abs() < f64::EPSILON);
        assert!(estimate.t95_low < 1.0);
        assert!(estimate.t95_high > 1.0);
    }
}
