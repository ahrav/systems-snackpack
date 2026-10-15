"""Select eight distinct physical cores on one socket from the allowed CPU affinity."""
import os
import subprocess
import sys

NEEDED = 8


def select_cores(rows, allowed, needed=NEEDED):
    """Return `needed` CPUs on one socket with distinct cores, or None.

    `rows` is `lscpu -p=CPU,CORE,SOCKET` text. Comment rows and rows with a
    blank or non-numeric topology field are skipped. Every socket is searched;
    the first socket with `needed` eligible cores wins, in lscpu order.
    """
    cores_by_socket = {}
    for line in rows.splitlines():
        fields = line.split(',')
        if len(fields) != 3 or not all(field.isdigit() for field in fields):
            continue
        cpu, core, sock = map(int, fields)
        cores = cores_by_socket.setdefault(sock, {})
        if cpu in allowed and core not in cores:
            cores[core] = cpu
    for cores in cores_by_socket.values():
        if len(cores) >= needed:
            return list(cores.values())[:needed]
    return None


if __name__ == '__main__':
    rows = subprocess.check_output(['lscpu', '-p=CPU,CORE,SOCKET'], text=True)
    selected = select_cores(rows, os.sched_getaffinity(0))
    if selected is None:
        sys.exit('campaign requires eight available physical cores on one socket')
    print(','.join(map(str, selected)))
