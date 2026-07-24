#!/usr/bin/env python3
"""Record which self-pagemap fields Linux exposes to this process."""

from __future__ import annotations

import ctypes
import mmap
import os
import struct


def main() -> None:
    page_size = os.sysconf("SC_PAGE_SIZE")
    page_count = 64
    mapping_bytes = page_count * page_size
    with mmap.mmap(-1, mapping_bytes, access=mmap.ACCESS_WRITE) as region:
        for page in range(page_count):
            region[page * page_size] = (page * 17 + 3) & 0xFF
        virtual_base = ctypes.addressof(ctypes.c_char.from_buffer(region))
        entries: list[int] = []
        # Readability of the file mode does not imply a permitted open or
        # read: Linux 4.0-4.1 returns EPERM at open for unprivileged callers,
        # and hardened kernels can deny at read time. Denial is a recordable
        # visibility outcome, not a probe failure.
        denial: str | None = None
        try:
            with open("/proc/self/pagemap", "rb", buffering=0) as pagemap:
                for page in range(page_count):
                    virtual_address = virtual_base + page * page_size
                    pagemap.seek((virtual_address // page_size) * 8)
                    encoded = pagemap.read(8)
                    if len(encoded) != 8:
                        denial = "short_read"
                        break
                    entries.append(struct.unpack("=Q", encoded)[0])
        except OSError as error:
            denial = f"errno_{error.errno}"

    if denial is not None:
        print(f"page_size={page_size}")
        print(f"mapping_bytes={mapping_bytes}")
        print(f"virtual_base=0x{virtual_base:x}")
        print("pagemap_readable=false")
        print(f"pagemap_denial={denial}")
        return

    pfn_mask = (1 << 55) - 1
    present = sum(bool(entry & (1 << 63)) for entry in entries)
    swapped = sum(bool(entry & (1 << 62)) for entry in entries)
    exclusive = sum(bool(entry & (1 << 56)) for entry in entries)
    soft_dirty = sum(bool(entry & (1 << 55)) for entry in entries)
    # Bits 0-54 hold a page frame number only for a present, non-swapped
    # entry; a swapped entry stores swap type and offset there instead.
    pfn_bearing = [
        entry for entry in entries if entry & (1 << 63) and not entry & (1 << 62)
    ]
    nonzero_pfns = sum(bool(entry & pfn_mask) for entry in pfn_bearing)
    print(f"page_size={page_size}")
    print(f"mapping_bytes={mapping_bytes}")
    print(f"virtual_base=0x{virtual_base:x}")
    print("pagemap_readable=true")
    print(f"entries={len(entries)}")
    print(f"present_entries={present}")
    print(f"swapped_entries={swapped}")
    print(f"exclusive_entries={exclusive}")
    print(f"soft_dirty_entries={soft_dirty}")
    print(f"pfn_bearing_entries={len(pfn_bearing)}")
    print(f"nonzero_pfn_entries={nonzero_pfns}")
    print(f"zero_pfn_entries={len(pfn_bearing) - nonzero_pfns}")


if __name__ == "__main__":
    main()
