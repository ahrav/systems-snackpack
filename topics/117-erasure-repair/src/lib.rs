//! Full-fragment repair of systematic six-data, nine-fragment stripes.
//! Each encoding row defines one stored byte at each offset.
//!
//! ```
//! use topic117_erasure_repair::Code;
//! let plan = Code::Local.repair(0, 1).unwrap();
//! assert_eq!(plan.helpers().collect::<Vec<_>>(), [1, 2, 6]);
//! ```

type Row = [u8; 6];

fn mul(mut a: u8, mut b: u8) -> u8 {
    let mut out = 0;
    while b != 0 {
        if b & 1 != 0 {
            out ^= a;
        }
        a = (a << 1) ^ if a & 128 != 0 { 0x1d } else { 0 };
        b >>= 1;
    }
    out
}

fn inverse(a: u8) -> u8 {
    assert_ne!(a, 0);
    (1..=255).find(|&b| mul(a, b) == 1).unwrap()
}

/// Two systematic codes with six data and three parity fragments.
#[derive(Clone, Copy)]
pub enum Code {
    /// Polynomial evaluations at six data points and three extra points.
    ReedSolomon,
    /// Two group XORs and one weighted global row.
    Local,
}

impl Code {
    fn row(self, id: usize) -> Row {
        assert!(id < 9);
        let mut row = [0; 6];
        if id < 6 {
            row[id] = 1;
        } else if matches!(self, Self::Local) && id < 8 {
            let start = 3 * (id - 6);
            row[start..start + 3].fill(1);
        } else {
            // Both layouts give slot 8 the same global parity.
            let x = [7, 8, 6][id - 6];
            for (i, weight) in row.iter_mut().enumerate() {
                *weight = 1;
                for j in 0..6u8 {
                    if j != i as u8 {
                        *weight = mul(*weight, mul(x ^ j, inverse(i as u8 ^ j)));
                    }
                }
            }
        }
        row
    }

    /// Build a plan for one position, using only the available rows.
    /// Bits 0 through 8 of `missing` mark erased fragments.
    /// Returns `None` when the target lies outside the span of the survivors.
    pub fn repair(self, target: usize, missing: u16) -> Option<Plan> {
        assert!(target < 9);
        // Prefer the group XOR when all other group members survive.
        if matches!(self, Self::Local) && target != 8 {
            let group = if [0, 1, 2, 6].contains(&target) {
                [0, 1, 2, 6]
            } else {
                [3, 4, 5, 7]
            };
            let mut weights = [0; 9];
            if group
                .iter()
                .all(|&i| i == target || missing & (1 << i) == 0)
            {
                for i in group {
                    if i != target {
                        weights[i] = 1;
                    }
                }
                return Some(Plan::new(weights));
            }
        }
        // Each pivot carries its expression in the original fragment IDs.
        let mut basis = [None; 6];
        for id in [0, 1, 2, 3, 4, 5, 8, 6, 7] {
            if missing & (1 << id) != 0 {
                continue;
            }
            let mut row = self.row(id);
            let mut expr = [0u8; 9];
            expr[id] = 1;
            for pivot in 0..6 {
                let k = row[pivot];
                if k == 0 {
                    continue;
                }
                if let Some((b, e)) = &basis[pivot] {
                    add_scaled(&mut row, b, k);
                    add_scaled(&mut expr, e, k);
                } else {
                    let scale = inverse(k);
                    row.iter_mut()
                        .chain(&mut expr)
                        .for_each(|v| *v = mul(*v, scale));
                    basis[pivot] = Some((row, expr));
                    break;
                }
            }
        }
        let mut row = self.row(target);
        let mut weights = [0; 9];
        for pivot in 0..6 {
            let k = row[pivot];
            if k != 0 {
                let (b, e) = basis[pivot].as_ref()?;
                add_scaled(&mut row, b, k);
                add_scaled(&mut weights, e, k);
            }
        }
        Some(Plan::new(weights))
    }
}

fn add_scaled<const N: usize>(dest: &mut [u8; N], src: &[u8; N], k: u8) {
    for (out, &v) in dest.iter_mut().zip(src) {
        *out ^= mul(v, k);
    }
}

/// A linear combination of full helper fragments with precomputed byte tables.
pub struct Plan {
    terms: Vec<(usize, u8, [u8; 256])>,
}

impl Plan {
    fn new(weights: [u8; 9]) -> Self {
        Self {
            terms: weights
                .into_iter()
                .enumerate()
                .filter(|&(_, w)| w != 0)
                .map(|(i, w)| (i, w, std::array::from_fn(|v| mul(w, v as u8))))
                .collect(),
        }
    }

    /// Return the helper IDs requested by this plan, in read order.
    pub fn helpers(&self) -> impl Iterator<Item = usize> + '_ {
        self.terms.iter().map(|term| term.0)
    }

    /// Read each full helper once and overwrite the destination.
    /// All fragments must have equal length and belong to one verified stripe version.
    pub fn rebuild<'a>(&self, out: &mut [u8], mut read: impl FnMut(usize) -> &'a [u8]) {
        out.fill(0);
        for (id, weight, table) in &self.terms {
            let bytes = read(*id);
            assert_eq!(bytes.len(), out.len());
            if *weight == 1 {
                for (o, &v) in out.iter_mut().zip(bytes) {
                    *o ^= v;
                }
            } else {
                for (o, &v) in out.iter_mut().zip(bytes) {
                    *o ^= table[v as usize];
                }
            }
        }
    }
}

/// Encode six equally sized data fragments, preserving all six input positions.
pub fn encode(code: Code, data: [Vec<u8>; 6]) -> Vec<Vec<u8>> {
    let mut stripe = Vec::from(data);
    let n = stripe[0].len();
    assert!(stripe.iter().all(|d| d.len() == n));
    for id in 6..9 {
        let mut weights = [0; 9];
        weights[..6].copy_from_slice(&code.row(id));
        let mut parity = vec![0; n];
        Plan::new(weights).rebuild(&mut parity, |i| &stripe[i]);
        stripe.push(parity);
    }
    stripe
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn local_failure_depends_on_identity() {
        assert!(Code::Local.repair(0, 0b11 | 1 << 6).is_none());
        assert!(Code::Local.repair(0, 1 | 1 << 3 | 1 << 8).is_some());
        assert!(Code::ReedSolomon.repair(0, 0b11 | 1 << 6).is_some());
    }

    #[test]
    fn full_inputs_and_common_global_row() {
        let data = std::array::from_fn(|i| vec![i as u8; 257]);
        let rs = encode(Code::ReedSolomon, data.clone());
        let lrc = encode(Code::Local, data);
        assert_eq!(rs[8], lrc[8]);
        for (code, stripe, readers) in [(Code::Local, &lrc, 3), (Code::ReedSolomon, &rs, 6)] {
            let mut reads = vec![];
            let mut out = vec![255; 257];
            code.repair(0, 1).unwrap().rebuild(&mut out, |i| {
                assert_ne!(i, 0);
                reads.push(i);
                &stripe[i]
            });
            assert_eq!(reads.len(), readers);
            assert_eq!(out, stripe[0]);
        }
    }
}
