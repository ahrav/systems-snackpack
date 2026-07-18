//! Controlled Linux mappings for translation-reach and permission-change experiments.
//!
//! The region initially owns one 2 MiB-aligned anonymous VMA. Construction
//! rejects Linux hosts whose base-page or PMD-THP geometry is not exactly the
//! 4 KiB/2 MiB geometry used by this focused experiment.
//! [`MappingMode::BasePages`] applies `MADV_NOHUGEPAGE`;
//! [`MappingMode::TransparentHugePages`] applies `MADV_HUGEPAGE`, faults every
//! 4 KiB page, and requests synchronous `MADV_COLLAPSE`. Construction validates
//! the complete VMA through `/proc/self/smaps`; later permission changes can
//! split that VMA. Inspect [`AnonymousRegion::smaps_evidence`] instead of
//! treating an advice call as proof of the current mapping.
//!
//! ```no_run
//! # #[cfg(target_os = "linux")]
//! # {
//! use systems_snackpack_topic_008::{AnonymousRegion, MappingMode};
//!
//! let mut region = AnonymousRegion::new(2 * 1024 * 1024, MappingMode::BasePages)?;
//! region.build_random_page_ring(0x5eed)?;
//! assert_eq!(region.chase_pages(0, region.page_count() as u64)?, 0);
//! # Ok::<(), Box<dyn std::error::Error>>(())?;
//! # }
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

use std::{fmt, fs, ptr::NonNull};

/// Base-page granularity used by this focused experiment.
pub const BASE_PAGE_SIZE: usize = 4 * 1024;

/// Alignment and transparent-huge-page size used by this focused experiment.
pub const PMD_PAGE_SIZE: usize = 2 * 1024 * 1024;

/// Requested Linux mapping policy.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MappingMode {
    /// Disable transparent huge pages for the VMA with `MADV_NOHUGEPAGE`.
    BasePages,
    /// Request PMD-sized transparent huge pages and synchronous collapse.
    TransparentHugePages,
}

impl MappingMode {
    /// Stable name used in process records.
    pub const fn name(self) -> &'static str {
        match self {
            Self::BasePages => "base",
            Self::TransparentHugePages => "thp",
        }
    }
}

/// A failure to create, inspect, or operate on an experiment mapping.
#[derive(Debug)]
pub enum MappingError {
    /// The requested operation is Linux-specific.
    UnsupportedPlatform,
    /// The mapping length was zero, not a 2 MiB multiple, or overflowed.
    InvalidLength(usize),
    /// Linux could not expose its PMD transparent-huge-page size.
    PageGeometryIo(std::io::Error),
    /// Linux exposed a malformed PMD transparent-huge-page size.
    PageGeometryParse(String),
    /// The host page geometry differs from this experiment's fixed geometry.
    UnsupportedPageGeometry {
        /// Base-page size reported by the Linux auxiliary vector.
        base_page_bytes: usize,
        /// PMD transparent-huge-page size reported by sysfs.
        pmd_page_bytes: usize,
    },
    /// A page index did not fall inside the mapping.
    InvalidPage(usize),
    /// A page ring must be built before it can be chased.
    RingNotBuilt,
    /// Rebuilding the ring would write through a read-only first page.
    FirstPageReadOnly,
    /// A Linux system call failed with the captured errno value.
    SystemCall {
        /// Operation that failed.
        operation: &'static str,
        /// Linux errno captured immediately after the failure.
        errno: i32,
    },
    /// `/proc/self/smaps` could not be read.
    SmapsIo(std::io::Error),
    /// `/proc/self/smaps` did not contain the required mapping evidence.
    SmapsParse(String),
    /// The live mapping did not match the requested base-page or THP policy.
    MappingMismatch(String),
    /// A CPU number exceeded the fixed Linux `cpu_set_t` representation.
    InvalidCpu(usize),
}

impl fmt::Display for MappingError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedPlatform => formatter.write_str("operation requires Linux"),
            Self::InvalidLength(length) => write!(
                formatter,
                "mapping length {length} must be a nonzero 2 MiB multiple"
            ),
            Self::PageGeometryIo(error) => write!(
                formatter,
                "failed to read Linux PMD transparent-huge-page size: {error}"
            ),
            Self::PageGeometryParse(value) => write!(
                formatter,
                "invalid Linux PMD transparent-huge-page size: {value:?}"
            ),
            Self::UnsupportedPageGeometry {
                base_page_bytes,
                pmd_page_bytes,
            } => write!(
                formatter,
                "experiment requires 4096-byte base pages and 2097152-byte PMD THPs; host reports {base_page_bytes} and {pmd_page_bytes} bytes"
            ),
            Self::InvalidPage(page) => {
                write!(formatter, "page index {page} is outside the mapping")
            }
            Self::RingNotBuilt => formatter.write_str("build the page ring before chasing it"),
            Self::FirstPageReadOnly => {
                formatter.write_str("restore first-page writes before rebuilding the ring")
            }
            Self::SystemCall { operation, errno } => {
                write!(formatter, "{operation} failed with Linux errno {errno}")
            }
            Self::SmapsIo(error) => write!(formatter, "failed to read /proc/self/smaps: {error}"),
            Self::SmapsParse(reason) => {
                write!(formatter, "invalid /proc/self/smaps evidence: {reason}")
            }
            Self::MappingMismatch(reason) => {
                write!(formatter, "mapping policy was not materialized: {reason}")
            }
            Self::InvalidCpu(cpu) => {
                write!(formatter, "CPU {cpu} exceeds the supported CPU-set size")
            }
        }
    }
}

impl std::error::Error for MappingError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Self::PageGeometryIo(error) | Self::SmapsIo(error) => Some(error),
            _ => None,
        }
    }
}

/// Live `/proc/self/smaps` fields for the VMA containing a queried address.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct SmapsEvidence {
    /// Inclusive VMA start address.
    pub start: usize,
    /// Exclusive VMA end address.
    pub end: usize,
    /// `KernelPageSize` in KiB.
    pub kernel_page_kib: usize,
    /// `MMUPageSize` in KiB.
    pub mmu_page_kib: usize,
    /// `AnonHugePages` in KiB.
    pub anon_huge_pages_kib: usize,
    /// Tokens from the VMA's `VmFlags` line.
    pub vm_flags: Vec<String>,
}

impl SmapsEvidence {
    /// Returns whether the VMA reports the `hg` huge-page advice flag.
    pub fn has_hugepage_advice(&self) -> bool {
        self.vm_flags.iter().any(|flag| flag == "hg")
    }

    /// Returns whether the VMA reports the `nh` no-huge-page advice flag.
    pub fn has_no_hugepage_advice(&self) -> bool {
        self.vm_flags.iter().any(|flag| flag == "nh")
    }
}

/// Owned, 2 MiB-aligned anonymous Linux mapping.
pub struct AnonymousRegion {
    pointer: NonNull<u8>,
    length: usize,
    allocation_pointer: NonNull<u8>,
    allocation_length: usize,
    mode: MappingMode,
    ring_ready: bool,
    first_page_writable: bool,
}

impl AnonymousRegion {
    /// Creates and materializes an aligned mapping with the requested policy.
    ///
    /// `length` must be a nonzero multiple of [`PMD_PAGE_SIZE`]. The THP mode
    /// succeeds only when the complete mapping is reported as `AnonHugePages`
    /// after `MADV_COLLAPSE`; partial materialization is rejected. Before
    /// returning, the constructor also verifies that the VMA boundaries equal
    /// the requested aligned range. The experiment is defined only for 4 KiB
    /// base pages and 2 MiB PMD THPs; other Linux page geometries are rejected.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::InvalidLength`] when `length` is zero, is not a
    /// multiple of 2 MiB, or cannot include the alignment and guard padding.
    /// Returns [`MappingError::PageGeometryIo`],
    /// [`MappingError::PageGeometryParse`], or
    /// [`MappingError::UnsupportedPageGeometry`] when Linux cannot prove the
    /// required 4 KiB/2 MiB page geometry. Returns [`MappingError::SystemCall`]
    /// when Linux cannot map, advise, collapse, or trim the region. Returns
    /// [`MappingError::SmapsIo`] or
    /// [`MappingError::SmapsParse`] when live evidence is unavailable or
    /// malformed, and [`MappingError::MappingMismatch`] when its VMA boundaries
    /// or materialized policy differ from the request. Returns
    /// [`MappingError::UnsupportedPlatform`] outside Linux.
    pub fn new(length: usize, mode: MappingMode) -> Result<Self, MappingError> {
        if length == 0 || !length.is_multiple_of(PMD_PAGE_SIZE) {
            return Err(MappingError::InvalidLength(length));
        }
        platform::validate_page_geometry()?;
        let (pointer, allocation_pointer, allocation_length) = platform::map_aligned(length)?;
        let mut region = Self {
            pointer,
            length,
            allocation_pointer,
            allocation_length,
            mode,
            ring_ready: false,
            first_page_writable: true,
        };

        platform::advise(region.pointer, region.length, mode)?;
        region.fault_base_pages();
        if mode == MappingMode::TransparentHugePages {
            platform::collapse(region.pointer, region.length)?;
        }
        region.verify_requested_policy()?;
        Ok(region)
    }

    /// Returns the usable mapping length in bytes.
    pub const fn len(&self) -> usize {
        self.length
    }

    /// Returns `false`; successful construction always owns a nonempty mapping.
    pub const fn is_empty(&self) -> bool {
        self.length == 0
    }

    /// Returns the number of 4 KiB pages in the mapping.
    pub const fn page_count(&self) -> usize {
        self.length / BASE_PAGE_SIZE
    }

    /// Returns the requested mapping policy.
    pub const fn mode(&self) -> MappingMode {
        self.mode
    }

    /// Returns the first byte's virtual address for process-local diagnostics.
    pub fn start_address(&self) -> usize {
        self.pointer.as_ptr() as usize
    }

    /// Reads current evidence for the VMA containing the mapping's first byte.
    ///
    /// A partial `mprotect` can split the original VMA. After such a split, the
    /// returned bounds can cover only the first page rather than [`Self::len`].
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::SmapsIo`] when `/proc/self/smaps` cannot be read.
    /// Returns [`MappingError::SmapsParse`] when no VMA contains the address or
    /// the selected entry lacks a required page-size, huge-page, or flag field.
    pub fn smaps_evidence(&self) -> Result<SmapsEvidence, MappingError> {
        let contents = fs::read_to_string("/proc/self/smaps").map_err(MappingError::SmapsIo)?;
        parse_smaps(&contents, self.start_address())
    }

    /// Builds one deterministic cycle containing every 4 KiB page once.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::FirstPageReadOnly`] when a preceding permission
    /// change has not restored writes to the first page.
    pub fn build_random_page_ring(&mut self, seed: u64) -> Result<(), MappingError> {
        if !self.first_page_writable {
            return Err(MappingError::FirstPageReadOnly);
        }
        let pages = self.page_count();
        let mut order = (0..pages).collect::<Vec<_>>();
        let mut state = if seed == 0 {
            0x9e37_79b9_7f4a_7c15
        } else {
            seed
        };
        for index in (1..pages).rev() {
            let successor = (next_random(&mut state) as usize) % (index + 1);
            order.swap(index, successor);
        }
        for index in 0..pages {
            let page = order[index];
            let successor = order[(index + 1) % pages];
            // SAFETY: `page` came from `0..page_count`, each page has room for
            // a `usize`, and the owned mapping remains writable here.
            unsafe {
                self.pointer
                    .as_ptr()
                    .add(page * BASE_PAGE_SIZE)
                    .cast::<usize>()
                    .write(successor);
            }
        }
        self.ring_ready = true;
        Ok(())
    }

    /// Follows the page ring through a scalar, loop-carried load dependency.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::RingNotBuilt`] before
    /// [`Self::build_random_page_ring`] succeeds. Returns
    /// [`MappingError::InvalidPage`] when `start_page` is outside the mapping.
    pub fn chase_pages(&self, start_page: usize, steps: u64) -> Result<usize, MappingError> {
        if !self.ring_ready {
            return Err(MappingError::RingNotBuilt);
        }
        if start_page >= self.page_count() {
            return Err(MappingError::InvalidPage(start_page));
        }
        // SAFETY: Ring construction wrote an in-range successor to every page;
        // the region owns all bytes for the duration of this call.
        Ok(unsafe { topic008_chase_pages(self.pointer.as_ptr(), start_page, steps) })
    }

    /// Changes only the first 4 KiB page between read-only and read-write.
    ///
    /// Read permission remains present in both states. The shootdown workload
    /// uses this operation while other threads perform read-only volatile loads.
    /// Linux can split the original VMA at the protection boundary.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::SystemCall`] when `mprotect` fails.
    pub fn set_first_page_writable(&mut self, writable: bool) -> Result<(), MappingError> {
        if writable == self.first_page_writable {
            return Ok(());
        }
        platform::protect_first_page(self.pointer, writable)?;
        self.first_page_writable = writable;
        Ok(())
    }

    fn fault_base_pages(&mut self) {
        for offset in (0..self.length).step_by(BASE_PAGE_SIZE) {
            // SAFETY: Every offset is inside the writable owned mapping. A
            // volatile store forces first-touch allocation before collapse.
            unsafe { self.pointer.as_ptr().add(offset).write_volatile(1) };
        }
    }

    fn verify_requested_policy(&self) -> Result<(), MappingError> {
        let evidence = self.smaps_evidence()?;
        if evidence.start != self.start_address()
            || evidence.end != self.start_address() + self.length
        {
            return Err(MappingError::MappingMismatch(format!(
                "expected VMA {:x}-{:x}, observed {:x}-{:x}",
                self.start_address(),
                self.start_address() + self.length,
                evidence.start,
                evidence.end
            )));
        }
        match self.mode {
            MappingMode::BasePages => {
                if evidence.anon_huge_pages_kib != 0 || !evidence.has_no_hugepage_advice() {
                    return Err(MappingError::MappingMismatch(format!(
                        "base mode reports AnonHugePages={} KiB, VmFlags={}",
                        evidence.anon_huge_pages_kib,
                        evidence.vm_flags.join(",")
                    )));
                }
            }
            MappingMode::TransparentHugePages => {
                let expected_kib = self.length / 1024;
                if evidence.anon_huge_pages_kib != expected_kib || !evidence.has_hugepage_advice() {
                    return Err(MappingError::MappingMismatch(format!(
                        "THP mode expected {expected_kib} KiB, observed {} KiB, VmFlags={}",
                        evidence.anon_huge_pages_kib,
                        evidence.vm_flags.join(",")
                    )));
                }
            }
        }
        Ok(())
    }
}

impl Drop for AnonymousRegion {
    fn drop(&mut self) {
        // SAFETY: This object uniquely owns the complete guarded allocation
        // returned by `map_aligned`, and Drop runs once with its original
        // allocation pointer and length.
        unsafe { platform::unmap(self.allocation_pointer, self.allocation_length) };
    }
}

/// Pins the calling thread to one Linux logical CPU.
///
/// # Errors
///
/// Returns [`MappingError::InvalidCpu`] when `cpu` exceeds this crate's fixed
/// `16 * usize::BITS`-CPU mask. Returns [`MappingError::SystemCall`] when
/// `sched_setaffinity` fails and [`MappingError::UnsupportedPlatform`] outside
/// Linux.
pub fn pin_current_thread(cpu: usize) -> Result<(), MappingError> {
    platform::pin_current_thread(cpu)
}

#[inline(never)]
#[unsafe(export_name = "topic008_chase_pages")]
// SAFETY: `base` must remain readable for `steps` dependent loads. `page` and
// every stored successor must index a 4 KiB page in that mapping without offset
// overflow, and each page must begin with an aligned `usize` successor.
unsafe extern "C" fn topic008_chase_pages(
    base: *const u8,
    mut page: usize,
    mut steps: u64,
) -> usize {
    while steps != 0 {
        // SAFETY: The function contract keeps the mapping readable and every
        // loaded successor in range for the next iteration.
        page = unsafe {
            base.add(page * BASE_PAGE_SIZE)
                .cast::<usize>()
                .read_volatile()
        };
        steps -= 1;
    }
    page
}

fn next_random(state: &mut u64) -> u64 {
    let mut value = *state;
    value ^= value >> 12;
    value ^= value << 25;
    value ^= value >> 27;
    *state = value;
    value.wrapping_mul(2_685_821_657_736_338_717)
}

fn parse_smaps(contents: &str, address: usize) -> Result<SmapsEvidence, MappingError> {
    let mut selected: Option<SmapsEvidence> = None;
    for line in contents.lines() {
        if let Some((start, end)) = parse_vma_header(line) {
            if selected.is_some() {
                break;
            }
            if start <= address && address < end {
                selected = Some(SmapsEvidence {
                    start,
                    end,
                    kernel_page_kib: 0,
                    mmu_page_kib: 0,
                    // This sentinel distinguishes a missing field from an
                    // explicit `AnonHugePages: 0 kB` observation.
                    anon_huge_pages_kib: usize::MAX,
                    vm_flags: Vec::new(),
                });
            }
            continue;
        }
        let Some(evidence) = selected.as_mut() else {
            continue;
        };
        if let Some(value) = parse_kib_field(line, "KernelPageSize:")? {
            evidence.kernel_page_kib = value;
        } else if let Some(value) = parse_kib_field(line, "MMUPageSize:")? {
            evidence.mmu_page_kib = value;
        } else if let Some(value) = parse_kib_field(line, "AnonHugePages:")? {
            evidence.anon_huge_pages_kib = value;
        } else if let Some(flags) = line.strip_prefix("VmFlags:") {
            evidence.vm_flags = flags.split_whitespace().map(str::to_owned).collect();
        }
    }
    let evidence = selected
        .ok_or_else(|| MappingError::SmapsParse(format!("no VMA contains address {address:#x}")))?;
    if evidence.kernel_page_kib == 0
        || evidence.mmu_page_kib == 0
        || evidence.anon_huge_pages_kib == usize::MAX
        || evidence.vm_flags.is_empty()
    {
        return Err(MappingError::SmapsParse(format!(
            "VMA {:x}-{:x} lacks page-size or VmFlags fields",
            evidence.start, evidence.end
        )));
    }
    Ok(evidence)
}

fn parse_vma_header(line: &str) -> Option<(usize, usize)> {
    let range = line.split_whitespace().next()?;
    let (start, end) = range.split_once('-')?;
    Some((
        usize::from_str_radix(start, 16).ok()?,
        usize::from_str_radix(end, 16).ok()?,
    ))
}

fn parse_kib_field(line: &str, name: &str) -> Result<Option<usize>, MappingError> {
    let Some(value) = line.strip_prefix(name) else {
        return Ok(None);
    };
    let mut fields = value.split_whitespace();
    let number = fields
        .next()
        .ok_or_else(|| MappingError::SmapsParse(format!("{name} has no value")))?
        .parse::<usize>()
        .map_err(|_| MappingError::SmapsParse(format!("{name} has a nonnumeric value")))?;
    if fields.next() != Some("kB") {
        return Err(MappingError::SmapsParse(format!("{name} does not use kB")));
    }
    Ok(Some(number))
}

#[cfg(target_os = "linux")]
mod platform {
    use super::{BASE_PAGE_SIZE, MappingError, MappingMode, PMD_PAGE_SIZE};
    use std::{ffi::c_void, fs, ptr::NonNull};

    const PROT_READ: i32 = 1;
    const PROT_WRITE: i32 = 2;
    const MAP_PRIVATE: i32 = 2;
    const MAP_ANONYMOUS: i32 = 0x20;
    const MADV_HUGEPAGE: i32 = 14;
    const MADV_NOHUGEPAGE: i32 = 15;
    const MADV_COLLAPSE: i32 = 25;
    const CPU_SET_WORDS: usize = 16;
    const AT_PAGESZ: usize = 6;
    const THP_PMD_SIZE_PATH: &str = "/sys/kernel/mm/transparent_hugepage/hpage_pmd_size";

    unsafe extern "C" {
        #[link_name = "mmap"]
        fn raw_mmap(
            address: *mut c_void,
            length: usize,
            protection: i32,
            flags: i32,
            file_descriptor: i32,
            offset: isize,
        ) -> *mut c_void;
        #[link_name = "munmap"]
        fn raw_munmap(address: *mut c_void, length: usize) -> i32;
        #[link_name = "madvise"]
        fn raw_madvise(address: *mut c_void, length: usize, advice: i32) -> i32;
        #[link_name = "mprotect"]
        fn raw_mprotect(address: *mut c_void, length: usize, protection: i32) -> i32;
        fn sched_setaffinity(pid: i32, size: usize, mask: *const c_void) -> i32;
        fn getauxval(kind: usize) -> usize;
        fn __errno_location() -> *mut i32;
    }

    pub(super) fn validate_page_geometry() -> Result<(), MappingError> {
        // SAFETY: `AT_PAGESZ` requests one integer value copied from the
        // process auxiliary vector; no pointer is passed or dereferenced.
        let base_page_bytes = unsafe { getauxval(AT_PAGESZ) };
        let raw_pmd_size =
            fs::read_to_string(THP_PMD_SIZE_PATH).map_err(MappingError::PageGeometryIo)?;
        let pmd_page_bytes = raw_pmd_size
            .trim()
            .parse::<usize>()
            .map_err(|_| MappingError::PageGeometryParse(raw_pmd_size.trim().to_owned()))?;
        if base_page_bytes != BASE_PAGE_SIZE || pmd_page_bytes != PMD_PAGE_SIZE {
            return Err(MappingError::UnsupportedPageGeometry {
                base_page_bytes,
                pmd_page_bytes,
            });
        }
        Ok(())
    }

    pub(super) fn map_aligned(
        length: usize,
    ) -> Result<(NonNull<u8>, NonNull<u8>, usize), MappingError> {
        let allocation_length = length
            .checked_add(PMD_PAGE_SIZE)
            .and_then(|value| value.checked_add(2 * BASE_PAGE_SIZE))
            .ok_or(MappingError::InvalidLength(length))?;
        // Map the reservation inaccessible, then expose only the aligned
        // experiment range. The untouched pages on both sides prevent Linux
        // from merging that range with a compatible neighboring VMA.
        // SAFETY: Arguments request a new private anonymous reservation; no
        // input pointer is dereferenced and the return value is checked.
        let allocation = unsafe {
            raw_mmap(
                std::ptr::null_mut(),
                allocation_length,
                0,
                MAP_PRIVATE | MAP_ANONYMOUS,
                -1,
                0,
            )
        };
        if allocation as isize == -1 {
            return Err(system_error("mmap"));
        }
        let Some(allocation_pointer) = NonNull::new(allocation.cast::<u8>()) else {
            // Linux normally rejects address zero through `mmap_min_addr`, but
            // a successful null mapping still has to be released here.
            // SAFETY: Cleanup covers the complete live reservation.
            unsafe { raw_munmap(allocation, allocation_length) };
            return Err(MappingError::MappingMismatch(
                "mmap returned a null allocation".to_owned(),
            ));
        };
        let start = allocation as usize;
        // A successful mapping cannot wrap the process address space. The
        // reservation includes enough padding for one guard page before the
        // next 2 MiB boundary and one guard page after the usable range.
        let aligned = start
            .checked_add(BASE_PAGE_SIZE)
            .and_then(|value| value.checked_add(PMD_PAGE_SIZE - 1))
            .ok_or_else(|| {
                // SAFETY: Cleanup covers the complete live reservation.
                unsafe { raw_munmap(allocation, allocation_length) };
                MappingError::InvalidLength(length)
            })?
            & !(PMD_PAGE_SIZE - 1);
        let guarded_end = aligned
            .checked_add(length)
            .and_then(|value| value.checked_add(BASE_PAGE_SIZE));
        let allocation_end = start.checked_add(allocation_length);
        let (Some(guarded_end), Some(allocation_end)) = (guarded_end, allocation_end) else {
            // SAFETY: Cleanup covers the complete live reservation.
            unsafe { raw_munmap(allocation, allocation_length) };
            return Err(MappingError::MappingMismatch(
                "aligned mapping does not fit its guarded allocation".to_owned(),
            ));
        };
        if guarded_end > allocation_end {
            // SAFETY: Cleanup covers the complete live reservation.
            unsafe { raw_munmap(allocation, allocation_length) };
            return Err(MappingError::MappingMismatch(
                "aligned mapping does not fit its guarded allocation".to_owned(),
            ));
        }
        let pointer = NonNull::new(aligned as *mut u8).ok_or_else(|| {
            // SAFETY: Cleanup covers the complete live reservation.
            unsafe { raw_munmap(allocation, allocation_length) };
            MappingError::MappingMismatch("mmap returned a null aligned address".to_owned())
        })?;
        // SAFETY: The aligned range lies inside the inaccessible reservation.
        // One or more inaccessible pages remain before it, and at least one
        // inaccessible page remains after it.
        if unsafe { raw_mprotect(pointer.as_ptr().cast(), length, PROT_READ | PROT_WRITE) } != 0 {
            let error = system_error("mprotect aligned mapping");
            // SAFETY: Cleanup covers the complete live reservation.
            unsafe { raw_munmap(allocation, allocation_length) };
            return Err(error);
        }
        Ok((pointer, allocation_pointer, allocation_length))
    }

    pub(super) fn advise(
        pointer: NonNull<u8>,
        length: usize,
        mode: MappingMode,
    ) -> Result<(), MappingError> {
        let advice = match mode {
            MappingMode::BasePages => MADV_NOHUGEPAGE,
            MappingMode::TransparentHugePages => MADV_HUGEPAGE,
        };
        // SAFETY: The pointer and length describe the live owned mapping.
        if unsafe { raw_madvise(pointer.as_ptr().cast(), length, advice) } != 0 {
            return Err(system_error("madvise mapping policy"));
        }
        Ok(())
    }

    pub(super) fn collapse(pointer: NonNull<u8>, length: usize) -> Result<(), MappingError> {
        // SAFETY: The pointer and length describe the live, populated mapping.
        if unsafe { raw_madvise(pointer.as_ptr().cast(), length, MADV_COLLAPSE) } != 0 {
            return Err(system_error("madvise MADV_COLLAPSE"));
        }
        Ok(())
    }

    pub(super) fn protect_first_page(
        pointer: NonNull<u8>,
        writable: bool,
    ) -> Result<(), MappingError> {
        let protection = PROT_READ | if writable { PROT_WRITE } else { 0 };
        // SAFETY: The first 4 KiB lies inside the live page-aligned mapping.
        if unsafe { raw_mprotect(pointer.as_ptr().cast(), super::BASE_PAGE_SIZE, protection) } != 0
        {
            return Err(system_error("mprotect first page"));
        }
        Ok(())
    }

    pub(super) fn pin_current_thread(cpu: usize) -> Result<(), MappingError> {
        let bits = usize::BITS as usize;
        if cpu >= CPU_SET_WORDS * bits {
            return Err(MappingError::InvalidCpu(cpu));
        }
        let mut mask = [0_usize; CPU_SET_WORDS];
        mask[cpu / bits] |= 1_usize << (cpu % bits);
        // SAFETY: The mask pointer references its complete initialized byte
        // representation; pid zero selects only the calling thread.
        if unsafe { sched_setaffinity(0, std::mem::size_of_val(&mask), mask.as_ptr().cast()) } != 0
        {
            return Err(system_error("sched_setaffinity"));
        }
        Ok(())
    }

    // SAFETY: `pointer` and `length` must identify the one live mapping, and no
    // access to that range may occur after this call.
    pub(super) unsafe fn unmap(pointer: NonNull<u8>, length: usize) {
        // SAFETY: The caller transfers the one live mapping to this cleanup.
        let _ = unsafe { raw_munmap(pointer.as_ptr().cast(), length) };
    }

    fn system_error(operation: &'static str) -> MappingError {
        // SAFETY: glibc exposes a thread-local errno pointer valid for an
        // immediate read on the calling thread.
        let errno = unsafe { *__errno_location() };
        MappingError::SystemCall { operation, errno }
    }
}

#[cfg(not(target_os = "linux"))]
mod platform {
    use super::{MappingError, MappingMode};
    use std::ptr::NonNull;

    pub(super) fn validate_page_geometry() -> Result<(), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    pub(super) fn map_aligned(
        _length: usize,
    ) -> Result<(NonNull<u8>, NonNull<u8>, usize), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    pub(super) fn advise(
        _pointer: NonNull<u8>,
        _length: usize,
        _mode: MappingMode,
    ) -> Result<(), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    pub(super) fn collapse(_pointer: NonNull<u8>, _length: usize) -> Result<(), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    pub(super) fn protect_first_page(
        _pointer: NonNull<u8>,
        _writable: bool,
    ) -> Result<(), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    pub(super) fn pin_current_thread(_cpu: usize) -> Result<(), MappingError> {
        Err(MappingError::UnsupportedPlatform)
    }

    // SAFETY: No caller obligations apply because this unsupported-platform
    // stub cannot receive a mapping created by this module.
    pub(super) unsafe fn unmap(_pointer: NonNull<u8>, _length: usize) {}
}

#[cfg(test)]
mod tests {
    use super::{
        AnonymousRegion, MappingError, MappingMode, PMD_PAGE_SIZE, next_random, parse_smaps,
    };

    const COMPLETE_SMAPS: &str = "1000-3000 rw-p 00000000 00:00 0\n\
KernelPageSize:        4 kB\n\
MMUPageSize:           4 kB\n\
AnonHugePages:         0 kB\n\
VmFlags: rd wr mr mw me ac sd nh\n";

    #[test]
    fn rejects_invalid_lengths_before_platform_dispatch() {
        assert!(matches!(
            AnonymousRegion::new(0, MappingMode::BasePages),
            Err(MappingError::InvalidLength(0))
        ));
        assert!(matches!(
            AnonymousRegion::new(PMD_PAGE_SIZE - 1, MappingMode::BasePages),
            Err(MappingError::InvalidLength(_))
        ));
    }

    #[test]
    fn random_stream_is_repeatable_and_nonconstant() {
        let mut left = 17;
        let mut right = 17;
        let values = (0..8)
            .map(|_| {
                let next = next_random(&mut left);
                assert_eq!(next, next_random(&mut right));
                next
            })
            .collect::<Vec<_>>();
        assert!(values.windows(2).any(|pair| pair[0] != pair[1]));
    }

    #[test]
    fn smaps_parser_preserves_an_explicit_zero_huge_page_count() {
        let evidence = parse_smaps(COMPLETE_SMAPS, 0x1800).unwrap();
        assert_eq!(evidence.anon_huge_pages_kib, 0);
        assert!(evidence.has_no_hugepage_advice());
    }

    #[test]
    fn smaps_parser_rejects_a_missing_huge_page_count() {
        let incomplete = COMPLETE_SMAPS.replace("AnonHugePages:         0 kB\n", "");
        assert!(matches!(
            parse_smaps(&incomplete, 0x1800),
            Err(MappingError::SmapsParse(_))
        ));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn base_mapping_builds_one_complete_ring() {
        let mut region = AnonymousRegion::new(PMD_PAGE_SIZE, MappingMode::BasePages).unwrap();
        region.build_random_page_ring(0x5eed).unwrap();
        assert_eq!(
            region.chase_pages(0, region.page_count() as u64).unwrap(),
            0
        );
        let evidence = region.smaps_evidence().unwrap();
        assert_eq!(evidence.anon_huge_pages_kib, 0);
        assert!(evidence.has_no_hugepage_advice());
    }
}
