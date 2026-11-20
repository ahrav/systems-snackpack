"""Model one warm descriptor across a same-length external overwrite."""
backing = (0o444, b"BLUE")
mode, pages = backing
backing = (0o400, b"GOLD")
for discard_pages in (False, True):
    mode = backing[0]
    if discard_pages:
        pages = backing[1]
    print(f"{mode:04o}", pages.decode())
