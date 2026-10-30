//! Line-oriented oracle interface and fresh-process benchmark driver.
use std::{
    hint::black_box,
    io::{self, BufRead},
    time::Instant,
};
use topic093_wire_format::{View, decode_owned, encode};

fn digest(id: u32, bytes: &[u8]) -> u64 {
    id as u64 + bytes.iter().map(|&x| x as u64).sum::<u64>()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("check") {
        for line in io::stdin().lock().lines() {
            let line = line.unwrap();
            let bytes: Vec<u8> = (0..line.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&line[i..i + 2], 16).unwrap())
                .collect();
            match View::parse(&bytes) {
                Err(_) => {
                    assert!(decode_owned(&bytes).is_err());
                    println!("ERR");
                }
                Ok(view) => {
                    let owned = decode_owned(&bytes).unwrap();
                    let mut fields = Vec::new();
                    for (i, (id, payload)) in owned.iter().enumerate() {
                        assert_eq!(view.record(i), Some((*id, payload.as_slice())));
                        let hex: String = payload.iter().map(|x| format!("{x:02x}")).collect();
                        fields.push(format!("{id}:{hex}"));
                    }
                    println!("OK {}", fields.join(","));
                }
            }
        }
        return;
    }
    assert_eq!(
        args.len(),
        7,
        "probe borrowed|owned count payload stride repeats iterations"
    );
    let mode = &args[1];
    let nums: Vec<usize> = args[2..].iter().map(|x| x.parse().unwrap()).collect();
    let (count, size, stride, repeats, iterations) = (nums[0], nums[1], nums[2], nums[3], nums[4]);
    let records: Vec<_> = (0..count)
        .map(|i| {
            (
                i as u32,
                (0..size)
                    .map(|j| ((i * 17 + j * 13) % 251) as u8)
                    .collect::<Vec<_>>(),
            )
        })
        .collect();
    let expected: u64 = records
        .iter()
        .step_by(stride)
        .map(|(id, b)| digest(*id, b))
        .sum::<u64>()
        * repeats as u64;
    let bytes = encode(&records);
    drop(records);
    let start = Instant::now();
    let mut checksum = 0u64;
    for _ in 0..iterations {
        let b = black_box(bytes.as_slice());
        let mut sum = 0;
        if mode == "borrowed" {
            let view = View::parse(b).unwrap();
            for _ in 0..repeats {
                for i in (0..count).step_by(stride) {
                    let (id, payload) = view.record(black_box(i)).unwrap();
                    sum += digest(id, payload);
                }
            }
        } else {
            assert_eq!(mode, "owned");
            let owned = decode_owned(b).unwrap();
            for _ in 0..repeats {
                for i in (0..count).step_by(stride) {
                    let (id, payload) = &owned[black_box(i)];
                    sum += digest(*id, payload);
                }
            }
            black_box(&owned);
        }
        checksum = checksum.wrapping_add(black_box(sum));
    }
    let elapsed = start.elapsed().as_nanos();
    assert_eq!(checksum, expected * iterations as u64);
    println!("{},{},{},{}", mode, elapsed, iterations, checksum);
}
