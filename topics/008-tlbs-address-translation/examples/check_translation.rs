//! Validates whole-VMA base-page and PMD-THP evidence, chases one page ring,
//! then records live `/proc/self/smaps` fields for the unchanged mapping.

#[cfg(target_os = "linux")]
use systems_snackpack_topic_008::{AnonymousRegion, MappingMode, PMD_PAGE_SIZE};

#[cfg(not(target_os = "linux"))]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("CHECK status=skipped reason=linux_required");
    Ok(())
}

#[cfg(target_os = "linux")]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    for mode in [MappingMode::BasePages, MappingMode::TransparentHugePages] {
        let mut region = AnonymousRegion::new(32 * PMD_PAGE_SIZE, mode)?;
        region.build_random_page_ring(0x746c_622d_7269_6e67)?;
        let pages = region.page_count();
        let steps = pages.checked_mul(2).expect("page step count overflow") as u64;
        let final_page = region.chase_pages(0, steps)?;
        assert_eq!(final_page, 0);
        let evidence = region.smaps_evidence()?;
        println!(
            "CHECK status=ok variant={} bytes={} start={:#x} vma={:#x}-{:#x} anon_huge_kib={} kernel_page_kib={} mmu_page_kib={} vm_flags={}",
            mode.name(),
            region.len(),
            region.start_address(),
            evidence.start,
            evidence.end,
            evidence.anon_huge_pages_kib,
            evidence.kernel_page_kib,
            evidence.mmu_page_kib,
            evidence.vm_flags.join(",")
        );
    }
    Ok(())
}
