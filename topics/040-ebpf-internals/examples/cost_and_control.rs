//! Run the narrow control-flow and capacity models.

use ebpf_internals::{
    ControlFlowError, ControlFlowProgram, EventCost, ModelInstruction, amortized_setup_nanoseconds,
    independent_binary_path_bound, per_cpu_payload_bytes, ring_fill_seconds, ring_record_bytes,
};

fn main() {
    let invalid = ControlFlowProgram::new(vec![
        ModelInstruction::JumpAlways(100),
        ModelInstruction::Exit,
    ]);
    let rejection = invalid
        .check()
        .expect_err("the jump must target instruction 101 outside the program");
    assert_eq!(
        rejection,
        ControlFlowError::JumpOutOfRange {
            instruction: 0,
            target: 101,
        }
    );

    let event = EventCost {
        hook_ns: 8,
        native_ns: 12,
        helpers_ns: 15,
        maps_ns: 18,
        export_ns: 7,
        contention_ns: 20,
    };
    let total = event
        .total_nanoseconds()
        .expect("the illustrative terms fit in u64");
    let setup_share = amortized_setup_nanoseconds(12_000_000, 6_000_000)
        .expect("the illustrative event count is nonzero");
    let per_cpu =
        per_cpu_payload_bytes(64, 1, 8).expect("the illustrative per-CPU payload fits in usize");
    let record = ring_record_bytes(56).expect("the illustrative ring record fits in usize");
    let fill = ring_fill_seconds(8_388_608, 2_000_000.0, 56, 100_000_000.0)
        .expect("the illustrative producer rate exceeds the consumer rate");
    let path_bound =
        independent_binary_path_bound(10).expect("ten independent decisions fit in u128");

    println!("invalid_jump=rejected detail={rejection}");
    println!("event_total_ns={total}");
    println!("setup_share_ns_at_6000000={setup_share:.3}");
    println!("per_cpu_payload_bytes={per_cpu}");
    println!("ring_record_bytes={record}");
    println!("ring_fill_seconds={fill:.3}");
    println!("independent_binary_path_bound_10={path_bound}");
    println!("result=PASS timing_reported=no real_ebpf_exercised=no");
}
