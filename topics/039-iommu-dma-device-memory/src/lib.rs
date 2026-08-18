//! Checked model of a device-visible memory mapping.
//!
//! A central processing unit (CPU) pointer, a physical address, and an input-output
//! virtual address (IOVA) belong to separate address spaces. [`DmaMapping`] keeps
//! those spaces distinct and models the ownership transfer around a streaming
//! direct-memory-access (DMA) operation.
//!
//! # Invariants
//!
//! A live mapping covers a half-open IOVA aperture. Each IOVA page selects one
//! physical backing page. Device access requires the mapped permission, current
//! epoch, and device ownership. Completion returns ownership to the CPU. Unmap
//! requires CPU ownership and the original scatter/gather entry count, which
//! counts the input memory segments before adjacent entries are merged.
//!
//! This crate does not program an input-output memory management unit (IOMMU),
//! pin memory, maintain caches, access memory-mapped input/output registers, or
//! submit work to a device. It proves only the checks implemented by the model;
//! in particular, aperture checks cannot detect a wrong but mapped IOVA. Run
//! `cargo run --package iommu-dma-device-memory --bin dma-contract-probe` for
//! the deterministic model checks.

use std::error::Error;
use std::fmt::{self, Display, Formatter};
use std::num::{NonZeroU64, NonZeroUsize};
use std::sync::Arc;

/// An address used by CPU code.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct CpuVirtualAddress(u64);

impl CpuVirtualAddress {
    /// Creates a CPU virtual address without claiming that a device can reach it.
    #[must_use]
    pub const fn new(value: u64) -> Self {
        Self(value)
    }

    /// Returns the numeric address.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// An address in the host physical address space.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PhysicalAddress(u64);

impl PhysicalAddress {
    /// Creates a physical address for the model's supplied backing plan.
    #[must_use]
    pub const fn new(value: u64) -> Self {
        Self(value)
    }

    /// Returns the numeric address.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// An address placed in a device descriptor.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Iova(u64);

impl Iova {
    /// Creates an input-output virtual address without claiming that a map exists.
    #[must_use]
    pub const fn new(value: u64) -> Self {
        Self(value)
    }

    /// Returns the numeric address.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// Caller-supplied generation used to reject stale descriptor metadata.
///
/// Reset advances the model's epoch. Unmap instead makes the mapping inactive;
/// this crate has no remap operation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MappingEpoch(u64);

impl MappingEpoch {
    /// Creates an epoch supplied by the mapping owner.
    #[must_use]
    pub const fn new(value: u64) -> Self {
        Self(value)
    }

    /// Returns the numeric generation.
    #[must_use]
    pub const fn get(self) -> u64 {
        self.0
    }
}

/// Direction of payload movement relative to system memory.
///
/// The direction controls which [`DeviceAccess`] values [`DmaMapping::translate`]
/// accepts; it does not perform cache maintenance or synchronize real memory.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DmaDirection {
    /// The device reads bytes written by the CPU.
    ToDevice,
    /// The device writes bytes that the CPU will later read.
    FromDevice,
    /// Both CPU-to-device and device-to-CPU movement are permitted.
    Bidirectional,
}

/// Access attempted by the modelled device.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DeviceAccess {
    /// Device reads system memory.
    Read,
    /// Device writes system memory.
    Write,
}

impl DmaDirection {
    const fn permits(self, access: DeviceAccess) -> bool {
        matches!(
            (self, access),
            (Self::ToDevice, DeviceAccess::Read)
                | (Self::FromDevice, DeviceAccess::Write)
                | (Self::Bidirectional, _)
        )
    }
}

/// Classification of memory by the remaining ownership or access obligation.
///
/// These variants describe contracts; they do not allocate, map, or synchronize
/// memory.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MemoryRole {
    /// Long-lived CPU/device-visible control memory; ordering still applies.
    CoherentControl,
    /// Bulk payload whose CPU/device ownership alternates.
    StreamingPayload,
    /// Temporary device-reachable storage that adds a CPU copy.
    BounceBuffer,
    /// Device register space that requires memory-mapped I/O accessors.
    MmioRegister,
    /// Storage physically attached to a device with provider-defined CPU access.
    DeviceLocal,
}

impl MemoryRole {
    /// Reports whether the model requires an explicit CPU/device ownership handoff.
    #[must_use]
    pub const fn transfers_ownership(self) -> bool {
        matches!(self, Self::StreamingPayload | Self::BounceBuffer)
    }
}

/// Entry counts before and after a scatter/gather list is mapped.
///
/// A scatter/gather list describes one logical buffer as multiple memory
/// segments. Hardware consumes `mapped`; synchronization and unmap use
/// `original` because mapping may merge adjacent input entries.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ScatterCounts {
    original: NonZeroUsize,
    mapped: NonZeroUsize,
}

impl ScatterCounts {
    /// Records nonzero input and hardware entry counts when mapping did not add entries.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::InvalidScatterCounts`] when `mapped` exceeds
    /// `original`.
    pub const fn new(original: NonZeroUsize, mapped: NonZeroUsize) -> Result<Self, MappingError> {
        if mapped.get() > original.get() {
            return Err(MappingError::InvalidScatterCounts);
        }
        Ok(Self { original, mapped })
    }

    /// Returns the input count required by synchronization and unmap.
    #[must_use]
    pub const fn original(self) -> usize {
        self.original.get()
    }

    /// Returns the post-mapping count used to construct hardware descriptors.
    #[must_use]
    pub const fn mapped(self) -> usize {
        self.mapped.get()
    }
}

/// Failure of mapping geometry, ownership, or lifecycle validation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MappingError {
    /// IOVA range or translated physical address overflowed `u64`.
    AddressOverflow,
    /// The inclusive device address mask cannot represent the mapped aperture.
    AddressMaskExceeded,
    /// Length is not an exact multiple of the model's page size.
    MisalignedLength,
    /// Backing-page count does not cover the aperture exactly.
    BackingCoverageMismatch,
    /// Mapped scatter/gather count exceeds the original nonzero count.
    InvalidScatterCounts,
    /// Mapping has already been removed or invalidated.
    InactiveMapping,
    /// Descriptor or completion belongs to another mapping generation.
    StaleEpoch,
    /// Device direction does not permit the attempted access.
    DirectionMismatch,
    /// Device-visible range falls outside the mapped aperture.
    OutsideAperture,
    /// This model accepts one physical page per descriptor range.
    CrossesBackingPage,
    /// Operation requires CPU ownership.
    DeviceOwnsBuffer,
    /// Operation requires an in-flight device-owned buffer.
    CpuOwnsBuffer,
    /// Completion belongs to another mapping or descriptor.
    CompletionMismatch,
    /// Unmap used the mapped hardware count instead of the original input count.
    WrongUnmapCount,
}

impl Display for MappingError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::AddressOverflow => "address arithmetic overflowed",
            Self::AddressMaskExceeded => "mapping exceeds the device address mask",
            Self::MisalignedLength => "mapping length is not page aligned",
            Self::BackingCoverageMismatch => "backing pages do not cover the mapping",
            Self::InvalidScatterCounts => "mapped scatter count exceeds original count",
            Self::InactiveMapping => "mapping is inactive",
            Self::StaleEpoch => "mapping epoch is stale",
            Self::DirectionMismatch => "DMA direction rejects the device access",
            Self::OutsideAperture => "device range is outside the mapped aperture",
            Self::CrossesBackingPage => "device range crosses a backing-page boundary",
            Self::DeviceOwnsBuffer => "device still owns the buffer",
            Self::CpuOwnsBuffer => "CPU owns the buffer and no DMA is in flight",
            Self::CompletionMismatch => "completion does not match the mapping or descriptor",
            Self::WrongUnmapCount => "unmap count differs from the original scatter count",
        })
    }
}

impl Error for MappingError {}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Owner {
    Cpu,
    Device { descriptor: u64 },
}

/// Single-use submission identity checked before ownership can return to the CPU.
///
/// The token carries the private identity of its originating mapping. It does
/// not implement [`Clone`] or [`Copy`], and [`DmaMapping::complete`] consumes
/// it on success, so safe code cannot replay one completion token. A rejected
/// completion returns the token inside [`RejectedCompletion`].
#[derive(Debug)]
pub struct CompletionToken {
    mapping_identity: Arc<()>,
    descriptor: u64,
    epoch: MappingEpoch,
}

impl CompletionToken {
    /// Returns the caller-supplied descriptor identity.
    #[must_use]
    pub const fn descriptor(&self) -> u64 {
        self.descriptor
    }

    /// Returns the mapping generation captured at submission.
    #[must_use]
    pub const fn epoch(&self) -> MappingEpoch {
        self.epoch
    }
}

/// A refused completion, handing the token back to the caller.
///
/// [`DmaMapping::complete`] consumes its token only when ownership actually
/// returns to the CPU. Every rejection returns the token inside this error,
/// so a completion routed to the wrong mapping cannot strand the token's
/// rightful mapping in device ownership.
#[derive(Debug)]
pub struct RejectedCompletion {
    /// The token exactly as submitted, still valid for its own mapping.
    pub token: CompletionToken,
    /// Why the mapping refused the completion.
    pub error: MappingError,
}

/// Checked address and ownership model for one streaming DMA mapping.
///
/// The mapping joins a contiguous IOVA aperture to a caller-supplied list of
/// physical pages. It starts active and CPU-owned. [`Self::submit`] transfers
/// ownership to one descriptor, [`Self::complete`] returns ownership, and
/// [`Self::unmap`] or [`Self::invalidate_after_reset`] makes the mapping
/// inactive. None of these transitions operate on hardware or real memory.
#[derive(Debug)]
pub struct DmaMapping {
    cpu_base: CpuVirtualAddress,
    iova_base: Iova,
    length: NonZeroU64,
    page_size: NonZeroU64,
    physical_pages: Vec<PhysicalAddress>,
    dma_mask: u64,
    direction: DmaDirection,
    epoch: MappingEpoch,
    scatter: ScatterCounts,
    owner: Owner,
    active: bool,
    identity: Arc<()>,
}

impl DmaMapping {
    /// Creates an active, CPU-owned mapping after validating its geometry.
    ///
    /// `dma_mask` is the greatest device address the mapping may use. The
    /// backing list contains one physical base for each model page.
    ///
    /// # Errors
    ///
    /// - [`MappingError::MisalignedLength`] if `length` is not an exact multiple
    ///   of `page_size`.
    /// - [`MappingError::BackingCoverageMismatch`] if `physical_pages` does not
    ///   contain exactly one entry per model page.
    /// - [`MappingError::AddressOverflow`] if the CPU virtual range, the IOVA
    ///   aperture, or any physical backing page extends beyond `u64::MAX`.
    /// - [`MappingError::AddressMaskExceeded`] if the last IOVA exceeds
    ///   `dma_mask`.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        cpu_base: CpuVirtualAddress,
        iova_base: Iova,
        length: NonZeroU64,
        page_size: NonZeroU64,
        physical_pages: Vec<PhysicalAddress>,
        dma_mask: u64,
        direction: DmaDirection,
        epoch: MappingEpoch,
        scatter: ScatterCounts,
    ) -> Result<Self, MappingError> {
        let length_value = length.get();
        let page_value = page_size.get();
        if !length_value.is_multiple_of(page_value) {
            return Err(MappingError::MisalignedLength);
        }
        let page_count = length_value / page_value;
        if usize::try_from(page_count).ok() != Some(physical_pages.len()) {
            return Err(MappingError::BackingCoverageMismatch);
        }
        cpu_base
            .get()
            .checked_add(length_value - 1)
            .ok_or(MappingError::AddressOverflow)?;
        let last_iova = iova_base
            .get()
            .checked_add(length_value - 1)
            .ok_or(MappingError::AddressOverflow)?;
        if last_iova > dma_mask {
            return Err(MappingError::AddressMaskExceeded);
        }
        for page in &physical_pages {
            page.get()
                .checked_add(page_value - 1)
                .ok_or(MappingError::AddressOverflow)?;
        }
        Ok(Self {
            cpu_base,
            iova_base,
            length,
            page_size,
            physical_pages,
            dma_mask,
            direction,
            epoch,
            scatter,
            owner: Owner::Cpu,
            active: true,
            identity: Arc::new(()),
        })
    }

    /// Returns the CPU address without treating it as device-visible evidence.
    #[must_use]
    pub const fn cpu_base(&self) -> CpuVirtualAddress {
        self.cpu_base
    }

    /// Returns the first device-visible address.
    #[must_use]
    pub const fn iova_base(&self) -> Iova {
        self.iova_base
    }

    /// Returns the current mapping generation.
    #[must_use]
    pub const fn epoch(&self) -> MappingEpoch {
        self.epoch
    }

    /// Returns the validated scatter/gather counts.
    #[must_use]
    pub const fn scatter_counts(&self) -> ScatterCounts {
        self.scatter
    }

    /// Returns the inclusive device address mask used at construction.
    #[must_use]
    pub const fn dma_mask(&self) -> u64 {
        self.dma_mask
    }

    /// Transfers ownership from the CPU to one descriptor.
    ///
    /// The returned token is the only completion identity accepted for this
    /// in-flight operation.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::InactiveMapping`] after invalidation or
    /// [`MappingError::DeviceOwnsBuffer`] while another descriptor is in flight.
    pub fn submit(&mut self, descriptor: u64) -> Result<CompletionToken, MappingError> {
        if !self.active {
            return Err(MappingError::InactiveMapping);
        }
        if !matches!(self.owner, Owner::Cpu) {
            return Err(MappingError::DeviceOwnsBuffer);
        }
        self.owner = Owner::Device { descriptor };
        Ok(CompletionToken {
            mapping_identity: Arc::clone(&self.identity),
            descriptor,
            epoch: self.epoch,
        })
    }

    /// Translates one device-owned IOVA range through the supplied backing plan.
    ///
    /// A wrong offset inside the aperture remains translatable. The IOMMU model
    /// rejects only geometry outside its map; a payload canary must detect an
    /// in-aperture descriptor bug.
    ///
    /// # Errors
    ///
    /// - [`MappingError::InactiveMapping`] if reset or unmap invalidated the map.
    /// - [`MappingError::StaleEpoch`] if `epoch` does not name the current map.
    /// - [`MappingError::CpuOwnsBuffer`] if no descriptor is in flight.
    /// - [`MappingError::DirectionMismatch`] if `access` conflicts with the
    ///   mapping direction.
    /// - [`MappingError::OutsideAperture`] if the requested half-open range is
    ///   not wholly inside the IOVA aperture or its endpoint overflows.
    /// - [`MappingError::CrossesBackingPage`] if the range spans two model pages.
    /// - [`MappingError::AddressOverflow`] if adding the in-page offset to the
    ///   selected physical page overflows.
    pub fn translate(
        &self,
        iova: Iova,
        length: NonZeroU64,
        access: DeviceAccess,
        epoch: MappingEpoch,
    ) -> Result<PhysicalAddress, MappingError> {
        if !self.active {
            return Err(MappingError::InactiveMapping);
        }
        if epoch != self.epoch {
            return Err(MappingError::StaleEpoch);
        }
        if !matches!(self.owner, Owner::Device { .. }) {
            return Err(MappingError::CpuOwnsBuffer);
        }
        if !self.direction.permits(access) {
            return Err(MappingError::DirectionMismatch);
        }
        let offset = iova
            .get()
            .checked_sub(self.iova_base.get())
            .ok_or(MappingError::OutsideAperture)?;
        if offset >= self.length.get() || length.get() > self.length.get() - offset {
            return Err(MappingError::OutsideAperture);
        }
        let page_size = self.page_size.get();
        let page_index = offset / page_size;
        let in_page = offset % page_size;
        if length.get() > page_size - in_page {
            return Err(MappingError::CrossesBackingPage);
        }
        let physical = self.physical_pages[page_index as usize]
            .get()
            .checked_add(in_page)
            .ok_or(MappingError::AddressOverflow)?;
        Ok(PhysicalAddress::new(physical))
    }

    /// Returns ownership to the CPU for the matching completion token.
    ///
    /// `reported_descriptor` is the descriptor identity the device reported
    /// with the completion. It is a separate argument because the device
    /// supplies it, while `token` is the driver's own unforgeable submission
    /// record: a device or provider can report a descriptor the driver does
    /// not have in flight, and the model must reject that.
    ///
    /// # Errors
    ///
    /// Every rejection returns [`RejectedCompletion`], which carries the
    /// unconsumed token alongside the reason:
    ///
    /// - [`MappingError::InactiveMapping`] if reset or unmap invalidated the map.
    /// - [`MappingError::StaleEpoch`] if the token names another map generation.
    /// - [`MappingError::CpuOwnsBuffer`] if no descriptor is in flight. Safe
    ///   code cannot reach this: a token exists only while its submission is
    ///   in flight, and a successful completion consumes it, so single-use
    ///   tokens prove the no-double-completion invariant at compile time.
    ///   The arm remains as a defensive guard on the model's own state.
    /// - [`MappingError::CompletionMismatch`] if the token belongs to another
    ///   mapping, or `reported_descriptor` does not name the descriptor this
    ///   mapping has in flight.
    pub fn complete(
        &mut self,
        token: CompletionToken,
        reported_descriptor: u64,
    ) -> Result<(), RejectedCompletion> {
        if !self.active {
            return Err(RejectedCompletion {
                token,
                error: MappingError::InactiveMapping,
            });
        }
        if !Arc::ptr_eq(&token.mapping_identity, &self.identity) {
            return Err(RejectedCompletion {
                token,
                error: MappingError::CompletionMismatch,
            });
        }
        if token.epoch != self.epoch {
            return Err(RejectedCompletion {
                token,
                error: MappingError::StaleEpoch,
            });
        }
        match self.owner {
            Owner::Cpu => Err(RejectedCompletion {
                token,
                error: MappingError::CpuOwnsBuffer,
            }),
            Owner::Device { descriptor } if descriptor != reported_descriptor => {
                Err(RejectedCompletion {
                    token,
                    error: MappingError::CompletionMismatch,
                })
            }
            Owner::Device { .. } => {
                self.owner = Owner::Cpu;
                Ok(())
            }
        }
    }

    /// Confirms that an active mapping is CPU-owned.
    ///
    /// This check models an ownership precondition; it does not invalidate CPU
    /// caches or wait for hardware.
    ///
    /// # Errors
    ///
    /// Returns [`MappingError::InactiveMapping`] after invalidation or
    /// [`MappingError::DeviceOwnsBuffer`] while DMA is in flight.
    pub const fn check_cpu_access(&self) -> Result<(), MappingError> {
        if !self.active {
            return Err(MappingError::InactiveMapping);
        }
        match self.owner {
            Owner::Cpu => Ok(()),
            Owner::Device { .. } => Err(MappingError::DeviceOwnsBuffer),
        }
    }

    /// Makes a CPU-owned mapping inactive when given its original input count.
    ///
    /// # Errors
    ///
    /// - [`MappingError::InactiveMapping`] if the map is already inactive.
    /// - [`MappingError::DeviceOwnsBuffer`] if a descriptor is still in flight.
    /// - [`MappingError::WrongUnmapCount`] if `original_nents` differs from the
    ///   pre-mapping scatter/gather count. The post-mapping hardware count may be
    ///   smaller because mapping can merge entries.
    pub fn unmap(&mut self, original_nents: usize) -> Result<(), MappingError> {
        self.check_cpu_access()?;
        if original_nents != self.scatter.original() {
            return Err(MappingError::WrongUnmapCount);
        }
        self.active = false;
        Ok(())
    }

    /// Makes the mapping inactive and invalidates its outstanding token after reset.
    ///
    /// The model treats reset as quiescence supplied by the caller. It returns
    /// CPU ownership, increments the epoch, and removes the prior mapping.
    pub fn invalidate_after_reset(&mut self) {
        self.owner = Owner::Cpu;
        self.active = false;
        self.epoch = MappingEpoch(self.epoch.get().wrapping_add(1));
    }
}

/// Translates within one contiguous aperture for generated-code inspection.
///
/// Returns [`u64::MAX`] for zero length, overflow of the translated range, an
/// out-of-aperture range, or a translated start of [`u64::MAX`], which the
/// failure sentinel reserves. It uses `physical_base + offset` only to expose
/// the bounds checks for linked image inspection; [`DmaMapping::translate`]
/// owns the page-list model. A wrong but in-aperture `iova` succeeds because
/// bounds checks cannot prove descriptor intent.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic39_checked_translate(
    iova_base: u64,
    aperture_len: u64,
    iova: u64,
    range_len: u64,
    physical_base: u64,
) -> u64 {
    if range_len == 0 {
        return u64::MAX;
    }
    let Some(offset) = iova.checked_sub(iova_base) else {
        return u64::MAX;
    };
    if offset >= aperture_len || range_len > aperture_len - offset {
        return u64::MAX;
    }
    let Some(start) = physical_base.checked_add(offset) else {
        return u64::MAX;
    };
    // u64::MAX is this hook's failure sentinel, so it cannot also name a
    // successful translation. DmaMapping::new already rejects a backing page
    // whose last byte overflows, so the model never needs that address.
    if start == u64::MAX || start.checked_add(range_len - 1).is_none() {
        return u64::MAX;
    }
    start
}

/// Checks a half-open IOVA range against an inclusive device address mask.
///
/// Returns `false` for zero length, endpoint overflow, or an endpoint greater
/// than `dma_mask`. This arithmetic hook does not query a device or an IOMMU.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn topic39_mask_allows(iova: u64, length: u64, dma_mask: u64) -> bool {
    length != 0
        && iova
            .checked_add(length - 1)
            .is_some_and(|last| last <= dma_mask)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn mapping(direction: DmaDirection) -> DmaMapping {
        DmaMapping::new(
            CpuVirtualAddress::new(0x7f20_0000_0000),
            Iova::new(0x4000_0000),
            NonZeroU64::new(16 * 1024).unwrap(),
            NonZeroU64::new(4096).unwrap(),
            vec![
                PhysicalAddress::new(0x1_0000_0000),
                PhysicalAddress::new(0x3_0000_0000),
                PhysicalAddress::new(0x1_8000_0000),
                PhysicalAddress::new(0x5_0000_0000),
            ],
            u64::MAX,
            direction,
            MappingEpoch::new(7),
            ScatterCounts::new(NonZeroUsize::new(4).unwrap(), NonZeroUsize::new(2).unwrap())
                .unwrap(),
        )
        .unwrap()
    }

    #[test]
    fn contiguous_iova_selects_noncontiguous_backing() {
        let mut map = mapping(DmaDirection::Bidirectional);
        map.submit(10).unwrap();
        let physical = map
            .translate(
                Iova::new(0x4000_0000 + 4096 + 64),
                NonZeroU64::new(32).unwrap(),
                DeviceAccess::Read,
                MappingEpoch::new(7),
            )
            .unwrap();
        assert_eq!(physical, PhysicalAddress::new(0x3_0000_0000 + 64));
    }

    #[test]
    fn aperture_rejects_outside_but_accepts_wrong_inside_offset() {
        let mut map = mapping(DmaDirection::FromDevice);
        map.submit(10).unwrap();
        assert_eq!(
            map.translate(
                Iova::new(0x4000_0000 + 16 * 1024),
                NonZeroU64::new(1).unwrap(),
                DeviceAccess::Write,
                MappingEpoch::new(7),
            ),
            Err(MappingError::OutsideAperture)
        );
        assert!(
            map.translate(
                Iova::new(0x4000_0000 + 4096 + 3072),
                NonZeroU64::new(1).unwrap(),
                DeviceAccess::Write,
                MappingEpoch::new(7),
            )
            .is_ok()
        );
    }

    #[test]
    fn direction_epoch_and_ownership_are_checked() {
        let mut map = mapping(DmaDirection::ToDevice);
        assert_eq!(
            map.translate(
                map.iova_base(),
                NonZeroU64::new(1).unwrap(),
                DeviceAccess::Read,
                map.epoch(),
            ),
            Err(MappingError::CpuOwnsBuffer)
        );
        let token = map.submit(10).unwrap();
        assert_eq!(map.check_cpu_access(), Err(MappingError::DeviceOwnsBuffer));
        assert_eq!(
            map.translate(
                map.iova_base(),
                NonZeroU64::new(1).unwrap(),
                DeviceAccess::Write,
                map.epoch(),
            ),
            Err(MappingError::DirectionMismatch)
        );
        assert_eq!(
            map.translate(
                map.iova_base(),
                NonZeroU64::new(1).unwrap(),
                DeviceAccess::Read,
                MappingEpoch::new(6),
            ),
            Err(MappingError::StaleEpoch)
        );
        let mut unrelated = mapping(DmaDirection::ToDevice);
        let unrelated_token = unrelated.submit(10).unwrap();
        let rejected = map.complete(unrelated_token, 10).unwrap_err();
        assert_eq!(rejected.error, MappingError::CompletionMismatch);
        unrelated.complete(rejected.token, 10).unwrap();
        let misreported = map.complete(token, 11).unwrap_err();
        assert_eq!(misreported.error, MappingError::CompletionMismatch);
        map.complete(misreported.token, 10).unwrap();
        map.check_cpu_access().unwrap();
    }

    #[test]
    fn early_unmap_and_mapped_count_are_rejected() {
        let mut map = mapping(DmaDirection::FromDevice);
        let token = map.submit(10).unwrap();
        assert_eq!(map.unmap(4), Err(MappingError::DeviceOwnsBuffer));
        map.complete(token, 10).unwrap();
        assert_eq!(map.unmap(2), Err(MappingError::WrongUnmapCount));
        map.unmap(4).unwrap();
        assert_eq!(map.check_cpu_access(), Err(MappingError::InactiveMapping));
    }

    #[test]
    fn reset_invalidates_inflight_completion() {
        let mut map = mapping(DmaDirection::FromDevice);
        let token = map.submit(10).unwrap();
        map.invalidate_after_reset();
        assert_eq!(
            map.complete(token, 10).unwrap_err().error,
            MappingError::InactiveMapping
        );
        assert_eq!(map.epoch(), MappingEpoch::new(8));
    }

    #[test]
    fn geometry_rejects_overflow_mask_and_bad_counts() {
        assert_eq!(
            ScatterCounts::new(NonZeroUsize::new(2).unwrap(), NonZeroUsize::new(3).unwrap(),),
            Err(MappingError::InvalidScatterCounts)
        );
        assert!(!topic39_mask_allows(0xffff_fff0, 32, u32::MAX as u64));
        assert!(!topic39_mask_allows(u64::MAX - 10, 32, u64::MAX));
        assert_eq!(
            DmaMapping::new(
                CpuVirtualAddress::new(u64::MAX - 4095),
                Iova::new(0x4000_0000),
                NonZeroU64::new(16 * 1024).unwrap(),
                NonZeroU64::new(4096).unwrap(),
                vec![
                    PhysicalAddress::new(0x1_0000_0000),
                    PhysicalAddress::new(0x3_0000_0000),
                    PhysicalAddress::new(0x1_8000_0000),
                    PhysicalAddress::new(0x5_0000_0000),
                ],
                u64::MAX,
                DmaDirection::FromDevice,
                MappingEpoch::new(7),
                ScatterCounts::new(NonZeroUsize::new(4).unwrap(), NonZeroUsize::new(2).unwrap())
                    .unwrap(),
            )
            .err(),
            Some(MappingError::AddressOverflow)
        );
        assert_eq!(
            topic39_checked_translate(0x1000, 0x1000, 0x1fff, 2, 0x8000),
            u64::MAX
        );
        assert_eq!(
            topic39_checked_translate(0x1000, 0x1000, 0x1001, 1, u64::MAX),
            u64::MAX
        );
        assert_eq!(
            topic39_checked_translate(0, 16, 0, 3, u64::MAX - 1),
            u64::MAX
        );
        assert_eq!(
            topic39_checked_translate(0, 16, 0, 2, u64::MAX - 1),
            u64::MAX - 1
        );
        assert_eq!(topic39_checked_translate(0, 16, 0, 1, u64::MAX), u64::MAX);
    }

    #[test]
    fn memory_roles_do_not_conflate_visibility_and_ownership() {
        assert!(!MemoryRole::CoherentControl.transfers_ownership());
        assert!(MemoryRole::StreamingPayload.transfers_ownership());
        assert!(MemoryRole::BounceBuffer.transfers_ownership());
        assert!(!MemoryRole::MmioRegister.transfers_ownership());
        assert!(!MemoryRole::DeviceLocal.transfers_ownership());
    }
}
