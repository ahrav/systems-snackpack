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
        with open("/proc/self/pagemap", "rb", buffering=0) as pagemap:
            for page in range(page_count):
                virtual_address = virtual_base + page * page_size
                pagemap.seek((virtual_address // page_size) * 8)
                encoded = pagemap.read(8)
                if len(encoded) != 8:
                    raise SystemExit("short read from /proc/self/pagemap")
                entries.append(struct.unpack("=Q", encoded)[0])

    pfn_mask = (1 << 55) - 1
    present = sum(bool(entry & (1 << 63)) for entry in entries)
    swapped = sum(bool(entry & (1 << 62)) for entry in entries)
    exclusive = sum(bool(entry & (1 << 56)) for entry in entries)
    soft_dirty = sum(bool(entry & (1 << 55)) for entry in entries)
    nonzero_pfns = sum(bool(entry & pfn_mask) for entry in entries)
    print(f"page_size={page_size}")
    print(f"mapping_bytes={mapping_bytes}")
    print(f"virtual_base=0x{virtual_base:x}")
    print(f"entries={len(entries)}")
    print(f"present_entries={present}")
    print(f"swapped_entries={swapped}")
    print(f"exclusive_entries={exclusive}")
    print(f"soft_dirty_entries={soft_dirty}")
    print(f"nonzero_pfn_entries={nonzero_pfns}")
    print(f"zero_pfn_entries={len(entries) - nonzero_pfns}")


if __name__ == "__main__":
    main()
