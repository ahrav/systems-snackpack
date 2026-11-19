"""Model one immutable catalog decision and the kernel's live-ID check."""


def select(copied_name):
    return "read-only catalog" if copied_name == b"catalog\0" else None


def deliver(selected, live):
    if not live:
        return "expired"
    return selected or "denied"


if __name__ == "__main__":
    name = bytearray(b"catalog\0")
    selected = select(bytes(name))
    name[:] = b"another\0"
    print(deliver(selected, True))
    print(deliver(select(bytes(name)), True))
    print(deliver(selected, False))
