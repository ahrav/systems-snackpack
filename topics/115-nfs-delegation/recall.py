"""One file, one dirty writer, one reader. The clock uses model milliseconds."""
def reader_open(release, dirty="GOLD"):
    server_data = "BLUE"
    events = [(0, "B requests OPEN"), (1, "server sends CB_RECALL")]
    if release == "return":
        events += [(2, "A acknowledges"), (6, "A flushes"), (7, "DELEGRETURN")]
        server_data = dirty
    elif release == "revoke":
        events.append((31, "server revokes"))
    else:
        raise ValueError(release)
    # B has permission to read in both scenarios.
    return events[-1][0], server_data


if __name__ == "__main__":
    for release in ("return", "revoke"):
        elapsed, data = reader_open(release)
        print(f"{release}: B reads {data} at {elapsed} model ms")
