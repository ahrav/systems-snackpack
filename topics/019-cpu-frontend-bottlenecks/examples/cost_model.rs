//! Evaluates one frontend estimate and one cold-outlining decision.

use cpu_frontend_bottlenecks::{
    ExposedPenalty, FrontendInputs, OutliningInputs, SupplyTerm, estimate_frontend_cycles,
    evaluate_outlining, phase_cycle_floor,
};

fn main() {
    let frontend = estimate_frontend_cycles(FrontendInputs {
        cached_supply: SupplyTerm::new(600.0, 8.0),
        decode_supply: SupplyTerm::new(400.0, 5.0),
        path_switch_cycles: 3.0,
        instruction_refills: ExposedPenalty::new(2.0, 7.0),
        translation_misses: ExposedPenalty::new(1.0, 12.0),
        redirects: ExposedPenalty::new(4.0, 5.0),
    })
    .expect("example inputs satisfy the model domain");
    let phase_floor =
        phase_cycle_floor(frontend.total_cycles, 180.0).expect("finite cycle estimates");

    let outlining = evaluate_outlining(OutliningInputs {
        hot_executions: 1_000.0,
        cold_executions: 10.0,
        hot_cycles_saved_per_execution: 0.5,
        cold_cycles_added_per_execution: 20.0,
    })
    .expect("example inputs satisfy the model domain");

    println!("frontend estimate: {:.1} cycles", frontend.total_cycles);
    println!("phase lower bound: {phase_floor:.1} cycles");
    println!(
        "outlining net: {:.1} cycles; beneficial: {}",
        outlining.net_cycles_saved, outlining.beneficial
    );
}
