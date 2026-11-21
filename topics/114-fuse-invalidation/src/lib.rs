//! Model the attributes and one data page that Linux caches for a held FUSE descriptor.
//!
//! A cached answer changes only through [`Cache::invalidate`]. Reads between
//! notifications return cached values even after the backing file changes.
//!
//! ```
//! use topic114_fuse_invalidation::{Cache, File};
//! let mut cache = Cache::default();
//! let old = File { mode: 0o444, bytes: *b"BLUE" };
//! let new = File { mode: 0o400, bytes: *b"GOLD" };
//! assert_eq!(cache.read(old), old);
//! assert_eq!(cache.read(new), old);
//! cache.invalidate(false);
//! assert_eq!(cache.read(new), File { mode: new.mode, bytes: old.bytes });
//! cache.invalidate(true);
//! assert_eq!(cache.read(new), new);
//! ```

/// Two independently cached answers for a four-byte file.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct File {
    /// Permission bits, the value of `st_mode & 0o7777`.
    pub mode: u16,
    /// File contents.
    pub bytes: [u8; 4],
}

/// A model of cached attributes and one clean page.
#[derive(Default)]
pub struct Cache {
    mode: Option<u16>,
    bytes: Option<[u8; 4]>,
}

impl Cache {
    /// Expire attributes and optionally discard the file page.
    pub fn invalidate(&mut self, discard_pages: bool) {
        self.mode = None;
        if discard_pages {
            self.bytes = None;
        }
    }

    /// Model an fstat and pread while the backing version stays stable.
    pub fn read(&mut self, backing: File) -> File {
        File {
            mode: *self.mode.get_or_insert(backing.mode),
            bytes: *self.bytes.get_or_insert(backing.bytes),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn full_invalidation_matches_each_committed_version() {
        let mut cache = Cache::default();
        for version in 0u8..=255 {
            let backing = File {
                mode: 0o400 | u16::from(version & 0o44),
                bytes: [version; 4],
            };
            cache.invalidate(true);
            assert_eq!(cache.read(backing), backing);
        }
    }
}
