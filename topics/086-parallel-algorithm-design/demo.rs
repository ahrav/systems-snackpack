use std::thread;

fn scan(input: &[u64], workers: usize) -> Vec<u64> {
    assert!(workers > 0);
    let mut output = vec![0; input.len()];
    if input.is_empty() { return output; }
    let width = input.len().div_ceil(workers);
    let mut totals = vec![0u64; input.len().div_ceil(width)];
    thread::scope(|s| {
        for ((src, dst), total) in input.chunks(width)
            .zip(output.chunks_mut(width)).zip(totals.iter_mut()) {
            s.spawn(move || {
                let mut sum = 0u64;
                for (&x, y) in src.iter().zip(dst) {
                    *y = sum;
                    sum = sum.wrapping_add(x);
                }
                *total = sum;
            });
        }
    });
    let mut base = 0u64;
    for total in &mut totals {
        let next = base.wrapping_add(*total);
        *total = base;
        base = next;
    }
    thread::scope(|s| {
        for (dst, offset) in output.chunks_mut(width).zip(totals) {
            s.spawn(move || {
                for y in dst { *y = y.wrapping_add(offset); }
            });
        }
    });
    output
}

fn main() {
    let input = [3, 1, 4, 1, 5, 9, 2, 6];
    let expected = [0, 3, 4, 8, 9, 14, 23, 25];
    for workers in [1, 2, 3, 4, 16] {
        assert_eq!(scan(&input, workers), expected);
    }
    assert_eq!(scan(&[], 4), []);
    assert_eq!(scan(&[u64::MAX, 1, 2], 2), [0, u64::MAX, 0]);
    println!("{:?}", scan(&input, 4));
}
