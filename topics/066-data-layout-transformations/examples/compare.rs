//! Process-level layout comparison; invoke through scripts/run.py.
use data_layout_transformations::{
    Columns, Row, Tiles, input, oracle, permutation, row_indexed, row_narrow, row_wide,
};
use std::{hint::black_box, time::Instant};
enum Store<'a> {
    Aos(&'a [Row]),
    Soa(Columns),
    Tile(Tiles),
}
impl<'a> Store<'a> {
    fn build(name: &str, rows: &'a [Row]) -> Self {
        match name {
            "aos" => Self::Aos(rows),
            "soa" => Self::Soa(Columns::from_rows(rows)),
            "tile" => Self::Tile(Tiles::from_rows(rows)),
            _ => panic!("candidate"),
        }
    }
    fn query(&self, op: &str, order: &[usize]) -> u64 {
        match (self, op) {
            (Self::Aos(r), "narrow") => row_narrow(r),
            (Self::Aos(r), "wide") => row_wide(r),
            (Self::Aos(r), "indexed") => row_indexed(r, order),
            (Self::Soa(c), "narrow") => c.narrow(),
            (Self::Soa(c), "wide") => c.wide(),
            (Self::Soa(c), "indexed") => c.indexed(order),
            (Self::Tile(t), "narrow") => t.narrow(),
            (Self::Tile(t), "wide") => t.wide(),
            (Self::Tile(t), "indexed") => t.indexed(order),
            _ => panic!("operation"),
        }
    }
}
fn main() {
    let a: Vec<_> = std::env::args().collect();
    assert_eq!(a.len(), 5, "candidate n operation boundary");
    let (candidate, n, op, boundary) = (&a[1], a[2].parse::<usize>().unwrap(), &a[3], &a[4]);
    let rows = input(n);
    let order = permutation(n);
    let seq: Vec<_> = (0..n).collect();
    let expected = oracle(
        &rows,
        if op == "indexed" { &order } else { &seq },
        op == "narrow",
        op == "indexed",
    );
    // Correctness occurs before timing; no oracle is in a measured interval.
    assert_eq!(Store::build(candidate, &rows).query(op, &order), expected);
    let passes = match boundary.as_str() {
        "resident" => {
            if n < 64 {
                32768
            } else if n < 8192 {
                256
            } else {
                16
            }
        }
        "life1" => 1,
        "life16" => 16,
        _ => panic!("boundary"),
    };
    let batches = if boundary == "resident" {
        1
    } else if n < 64 {
        512
    } else if n < 8192 {
        32
    } else {
        1
    };
    let mut checksum = 0u64;
    let elapsed;
    if boundary == "resident" {
        let store = Store::build(candidate, &rows);
        for _ in 0..3 {
            black_box(store.query(black_box(op), black_box(&order)));
        }
        let start = Instant::now();
        for _ in 0..passes {
            checksum =
                checksum.wrapping_add(black_box(store.query(black_box(op), black_box(&order))));
        }
        elapsed = start.elapsed().as_nanos();
        black_box(&store);
    } else {
        let start = Instant::now();
        for _ in 0..batches {
            let store = Store::build(black_box(candidate), black_box(&rows));
            for _ in 0..passes {
                checksum =
                    checksum.wrapping_add(black_box(store.query(black_box(op), black_box(&order))));
            }
            drop(black_box(store));
        }
        elapsed = start.elapsed().as_nanos();
    }
    assert_eq!(checksum, expected.wrapping_mul((passes * batches) as u64));
    println!(
        "{{\"candidate\":\"{candidate}\",\"n\":{n},\"operation\":\"{op}\",\"boundary\":\"{boundary}\",\"passes\":{passes},\"batches\":{batches},\"ns_per_query\":{},\"checksum\":{checksum}}}",
        elapsed as f64 / (passes * batches) as f64
    );
}
