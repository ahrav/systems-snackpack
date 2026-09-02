//! Demonstrates independent cancellation, target, and resource-retirement
//! obligations alongside checked completion-visibility and CQ-size bounds.

use std::num::NonZeroU64;

use io_uring_lifetimes::{
    OperationToken, RequestLifecycle, TargetCompletion, required_cq_entries,
    visible_completion_bound_us,
};

fn main() {
    let target = OperationToken::new(7, 11);
    let cancel = OperationToken::new(8, 3);
    let resource_tag = NonZeroU64::new(44).unwrap();
    let mut request = RequestLifecycle::submitted(target, Some(resource_tag));
    request.request_cancel(cancel).unwrap();

    request.observe_cancel(cancel, 0).unwrap();
    println!("after_cancel={:?}", request.obligations());
    request
        .observe_target(target, -125, TargetCompletion::Terminal)
        .unwrap();
    println!("after_target={:?}", request.obligations());
    request.observe_resource_retirement(resource_tag).unwrap();
    println!("fully_retired={}", request.fully_retired());

    let visibility = visible_completion_bound_us(200, 500, 50).unwrap();
    let cq_entries = required_cq_entries(128, 50_000, 2_000, 24, 32).unwrap();
    println!("visibility_bound_us={visibility}");
    println!("required_cq_entries={cq_entries}");
}
