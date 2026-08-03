//! Cost model for equal-live-byte allocator layouts.
//!
//! [`Geometry`] separates requested live payload from the logical address span
//! that contains it. This model does not predict resident set size. Page size,
//! allocator metadata, arenas, caches, purge policy, and unrelated mappings
//! remain outside it.

/// Placement of surviving allocations after the free phase.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum SurvivorLayout {
    /// Keeps the lowest consecutive allocation indices.
    Compact,
    /// Keeps one allocation at each configured spacing interval.
    Scattered,
}

/// Invalid input to [`Geometry::new`].
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum GeometryError {
    /// The allocation count, requested block size, or spacing is zero.
    Zero,
    /// The allocation count is not divisible by the spacing.
    UnevenSpacing,
}

/// Fixed allocation geometry shared by both survivor layouts.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Geometry {
    allocation_count: usize,
    requested_block_bytes: usize,
    spacing: usize,
}

impl Geometry {
    /// Builds a geometry with an equal survivor count in both layouts.
    ///
    /// # Errors
    ///
    /// Returns [`GeometryError::Zero`] when any input is zero. Returns
    /// [`GeometryError::UnevenSpacing`] when `allocation_count` is not
    /// divisible by `spacing`.
    ///
    /// # Examples
    ///
    /// ```
    /// use allocator_internals_fragmentation::{Geometry, SurvivorLayout};
    ///
    /// let geometry = Geometry::new(262_144, 256, 16).unwrap();
    /// assert_eq!(geometry.survivor_count(), 16_384);
    /// assert_eq!(geometry.requested_live_bytes(), Some(4_194_304));
    /// assert!(geometry.keeps(SurvivorLayout::Scattered, 32));
    /// ```
    pub fn new(
        allocation_count: usize,
        requested_block_bytes: usize,
        spacing: usize,
    ) -> Result<Self, GeometryError> {
        if allocation_count == 0 || requested_block_bytes == 0 || spacing == 0 {
            return Err(GeometryError::Zero);
        }
        if !allocation_count.is_multiple_of(spacing) {
            return Err(GeometryError::UnevenSpacing);
        }
        Ok(Self {
            allocation_count,
            requested_block_bytes,
            spacing,
        })
    }

    /// Returns the number of live allocations after the free phase.
    #[must_use]
    pub fn survivor_count(self) -> usize {
        self.allocation_count / self.spacing
    }

    /// Returns requested survivor bytes.
    ///
    /// The value excludes allocator metadata and pointer-table overhead.
    #[must_use]
    pub fn requested_live_bytes(self) -> Option<usize> {
        self.survivor_count()
            .checked_mul(self.requested_block_bytes)
    }

    /// Returns pointer-table bytes for a pointer width in bytes.
    #[must_use]
    pub fn pointer_table_bytes(self, pointer_bytes: usize) -> Option<usize> {
        self.allocation_count.checked_mul(pointer_bytes)
    }

    /// Returns whether `index` survives under `layout`.
    ///
    /// Indices at or beyond the allocation count return `false`.
    #[must_use]
    pub fn keeps(self, layout: SurvivorLayout, index: usize) -> bool {
        if index >= self.allocation_count {
            return false;
        }
        match layout {
            SurvivorLayout::Compact => index < self.survivor_count(),
            SurvivorLayout::Scattered => index.is_multiple_of(self.spacing),
        }
    }

    /// Returns the byte span from the first through last survivor in a
    /// fixed-stride address model.
    ///
    /// `chunk_stride` includes allocator metadata and alignment. This logical
    /// span is not resident memory and does not model page reclamation.
    #[must_use]
    pub fn logical_survivor_span(
        self,
        layout: SurvivorLayout,
        chunk_stride: usize,
    ) -> Option<usize> {
        let survivors = self.survivor_count();
        let covered_indices = match layout {
            SurvivorLayout::Compact => survivors,
            SurvivorLayout::Scattered => survivors
                .checked_sub(1)?
                .checked_mul(self.spacing)?
                .checked_add(1)?,
        };
        covered_indices.checked_mul(chunk_stride)
    }
}

#[cfg(test)]
mod tests {
    use super::{Geometry, GeometryError, SurvivorLayout};

    #[test]
    fn layouts_keep_equal_counts_and_requested_bytes() {
        let geometry = Geometry::new(262_144, 256, 16).unwrap();
        let compact = (0..262_144)
            .filter(|&index| geometry.keeps(SurvivorLayout::Compact, index))
            .count();
        let scattered = (0..262_144)
            .filter(|&index| geometry.keeps(SurvivorLayout::Scattered, index))
            .count();

        assert_eq!(compact, 16_384);
        assert_eq!(scattered, compact);
        assert_eq!(geometry.requested_live_bytes(), Some(4_194_304));
        assert_eq!(geometry.pointer_table_bytes(8), Some(2_097_152));
    }

    #[test]
    fn scattering_expands_fixed_stride_span() {
        let geometry = Geometry::new(262_144, 256, 16).unwrap();

        assert_eq!(
            geometry.logical_survivor_span(SurvivorLayout::Compact, 272),
            Some(4_456_448)
        );
        assert_eq!(
            geometry.logical_survivor_span(SurvivorLayout::Scattered, 272),
            Some(71_299_088)
        );
    }

    #[test]
    fn rejects_geometry_without_equal_spacing() {
        assert_eq!(
            Geometry::new(15, 256, 16),
            Err(GeometryError::UnevenSpacing)
        );
        assert_eq!(Geometry::new(16, 0, 16), Err(GeometryError::Zero));
    }
}
