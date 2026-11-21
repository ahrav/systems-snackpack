"""Time serial model messages over a local socket. Python 3, POSIX."""
import csv
import itertools
import socket
import subprocess
import sys
import threading
import time


def serve(sock):
    with sock:
        while True:
            message = sock.recv(1)
            if not message:
                return
            time.sleep(0.0005)
            sock.sendall(message)


def trial(policy, reopens):
    client, peer = socket.socketpair()
    worker = threading.Thread(target=serve, args=(peer,))
    worker.start()
    count = 0

    def rpc(op):
        nonlocal count
        client.sendall(op)
        if client.recv(1) != op:
            raise RuntimeError("bad reply")
        count += 1

    with client:
        rpc(b'!')  # Both paths start with a warm connection and a closed file.
        count = 0
        start = time.perf_counter_ns()
        for _ in range(reopens):
            if policy == "plain":
                rpc(b'O')
                rpc(b'C')
        conflict = time.perf_counter_ns()
        rpc(b'O')  # B requests write access.
        if policy == "delegated":
            rpc(b'K')  # Callback with reply.
            rpc(b'R')  # Clean delegation return.
        end = time.perf_counter_ns()
    worker.join()
    expected = 1 + (2 * reopens if policy == "plain" else 2)
    assert count == expected
    return count, (end - start) // 1000, (end - conflict) // 1000


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "trial":
        print(*trial(sys.argv[2], int(sys.argv[3])), sep=",")
    else:
        out = csv.writer(sys.stdout, lineterminator="\n")
        out.writerow(["pair", "reopens", "policy", "messages", "total_us", "b_open_us"])
        for pair, n in itertools.product(range(20), (0, 8)):
            policies = ["plain", "delegated"] if pair % 2 == 0 else ["delegated", "plain"]
            for policy in policies:
                row = subprocess.check_output([sys.executable, __file__, "trial", policy, str(n)], text=True)
                out.writerow([pair, n, policy, *row.strip().split(",")])
