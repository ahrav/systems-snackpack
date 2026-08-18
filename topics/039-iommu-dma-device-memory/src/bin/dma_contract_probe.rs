//! Deterministic executable checks for the Topic 39 DMA mapping model.
//!
//! The output is a stable correctness contract for fresh-process replication.
//! This probe neither performs real DMA nor reports performance timing.

use std::hint::black_box;
use std::num::{NonZeroU64, NonZeroUsize};

use iommu_dma_device_memory::{
    CpuVirtualAddress, DeviceAccess, DmaDirection, DmaMapping, Iova, MappingEpoch, MappingError,
    PhysicalAddress, ScatterCounts, topic39_checked_translate, topic39_mask_allows,
};

const CPU_BASE: u64 = 0x7f20_0000_0000;
const IOVA_BASE: u64 = 0x4000_0000;
const PAGE_SIZE: u64 = 4096;
const MAPPING_LENGTH: u64 = 4 * PAGE_SIZE;

fn nonzero_u64(value: u64) -> NonZeroU64 {
    NonZeroU64::new(value).expect("probe constants are nonzero")
}

fn nonzero_usize(value: usize) -> NonZeroUsize {
    NonZeroUsize::new(value).expect("probe constants are nonzero")
}

fn require_error<T>(actual: Result<T, MappingError>, expected: MappingError, label: &str) {
    match actual {
        Err(error) if error == expected => {}
        Err(error) => panic!("{label}: expected {expected:?}, got {error:?}"),
        Ok(_) => panic!("{label}: expected {expected:?}, got success"),
    }
}

fn make_mapping(scatter: ScatterCounts) -> DmaMapping {
    DmaMapping::new(
        CpuVirtualAddress::new(CPU_BASE),
        Iova::new(IOVA_BASE),
        nonzero_u64(MAPPING_LENGTH),
        nonzero_u64(PAGE_SIZE),
        vec![
            PhysicalAddress::new(0x1_0000_0000),
            PhysicalAddress::new(0x3_0000_0000),
            PhysicalAddress::new(0x1_8000_0000),
            PhysicalAddress::new(0x5_0000_0000),
        ],
        0xffff_ffff,
        DmaDirection::FromDevice,
        MappingEpoch::new(7),
        scatter,
    )
    .expect("probe mapping must be valid")
}

fn main() {
    let scatter = ScatterCounts::new(nonzero_usize(4), nonzero_usize(2))
        .expect("mapped entries cannot exceed original entries");
    let mut mapping = make_mapping(scatter);

    assert_ne!(mapping.cpu_base().get(), mapping.iova_base().get());
    require_error(
        mapping.translate(
            mapping.iova_base(),
            nonzero_u64(1),
            DeviceAccess::Write,
            mapping.epoch(),
        ),
        MappingError::CpuOwnsBuffer,
        "translation before submission",
    );

    let token = mapping
        .submit(41)
        .expect("CPU-owned mapping can be submitted");
    require_error(
        mapping.check_cpu_access(),
        MappingError::DeviceOwnsBuffer,
        "CPU access while descriptor is in flight",
    );
    require_error(
        mapping.unmap(scatter.original()),
        MappingError::DeviceOwnsBuffer,
        "unmap while descriptor is in flight",
    );
    require_error(
        mapping.translate(
            mapping.iova_base(),
            nonzero_u64(1),
            DeviceAccess::Read,
            mapping.epoch(),
        ),
        MappingError::DirectionMismatch,
        "from-device mapping cannot be read by the device",
    );
    require_error(
        mapping.translate(
            mapping.iova_base(),
            nonzero_u64(1),
            DeviceAccess::Write,
            MappingEpoch::new(6),
        ),
        MappingError::StaleEpoch,
        "stale descriptor epoch",
    );

    let selected = mapping
        .translate(
            Iova::new(IOVA_BASE + PAGE_SIZE + 64),
            nonzero_u64(32),
            DeviceAccess::Write,
            mapping.epoch(),
        )
        .expect("second IOVA page must select the noncontiguous second backing page");
    assert_eq!(selected, PhysicalAddress::new(0x3_0000_0000 + 64));

    let wrong_inside = mapping
        .translate(
            Iova::new(IOVA_BASE + PAGE_SIZE + 3072),
            nonzero_u64(1),
            DeviceAccess::Write,
            mapping.epoch(),
        )
        .expect("an incorrect offset inside the aperture remains address-valid");
    assert_eq!(wrong_inside, PhysicalAddress::new(0x3_0000_0000 + 3072));
    require_error(
        mapping.translate(
            Iova::new(IOVA_BASE + MAPPING_LENGTH),
            nonzero_u64(1),
            DeviceAccess::Write,
            mapping.epoch(),
        ),
        MappingError::OutsideAperture,
        "first byte beyond half-open aperture",
    );

    let mut unrelated_mapping = make_mapping(scatter);
    let unrelated_token = unrelated_mapping
        .submit(99)
        .expect("independent mapping can issue an unrelated token");
    let rejected = mapping
        .complete(unrelated_token)
        .expect_err("completion from an unrelated descriptor is rejected");
    assert_eq!(rejected.error, MappingError::CompletionMismatch);
    unrelated_mapping
        .complete(rejected.token)
        .expect("returned token still completes its own mapping");
    mapping
        .complete(token)
        .expect("matching completion returns ownership to the CPU");
    mapping
        .check_cpu_access()
        .expect("CPU access is allowed after completion");
    require_error(
        mapping.unmap(scatter.mapped()),
        MappingError::WrongUnmapCount,
        "unmap with mapped hardware count",
    );
    mapping
        .unmap(scatter.original())
        .expect("unmap requires the original scatter/gather count");

    let hook_inside = topic39_checked_translate(
        black_box(IOVA_BASE),
        black_box(MAPPING_LENGTH),
        black_box(IOVA_BASE + PAGE_SIZE + 64),
        black_box(32),
        black_box(0x1_0000_0000),
    );
    let hook_outside = topic39_checked_translate(
        black_box(IOVA_BASE),
        black_box(MAPPING_LENGTH),
        black_box(IOVA_BASE + MAPPING_LENGTH),
        black_box(1),
        black_box(0x1_0000_0000),
    );
    let mask_ok = topic39_mask_allows(
        black_box(IOVA_BASE),
        black_box(MAPPING_LENGTH),
        black_box(0xffff_ffff),
    );
    let mask_boundary = topic39_mask_allows(
        black_box(IOVA_BASE),
        black_box(MAPPING_LENGTH),
        black_box(IOVA_BASE + MAPPING_LENGTH - 2),
    );
    let mask_overflow =
        topic39_mask_allows(black_box(u64::MAX - 10), black_box(32), black_box(u64::MAX));
    assert_eq!(hook_inside, 0x1_0000_0000 + PAGE_SIZE + 64);
    assert_eq!(hook_outside, u64::MAX);
    assert!(mask_ok);
    assert!(!mask_boundary);
    assert!(!mask_overflow);

    println!("contract=cpu_physical_iova_are_distinct result=PASS");
    println!(
        "address_spaces cpu=0x{CPU_BASE:x} iova=0x{IOVA_BASE:x} translated=0x{:x}",
        selected.get()
    );
    println!(
        "aperture wrong_inside=accepted translated=0x{:x} outside=rejected",
        wrong_inside.get()
    );
    println!("direction from_device_write=accepted from_device_read=rejected");
    println!(
        "lifecycle stale_epoch=rejected early_unmap=rejected unrelated_completion=rejected returned_token_completes_own_mapping=accepted cpu_during_dma=rejected cpu_after_completion=accepted"
    );
    println!(
        "scatter original={} mapped={} unmap_mapped=rejected unmap_original=accepted",
        scatter.original(),
        scatter.mapped()
    );
    println!(
        "linked_hooks in_aperture=accepted outside=rejected mask_boundary=rejected mask_overflow=rejected"
    );
    println!("result=PASS timing_reported=no real_dma_exercised=no");
}
