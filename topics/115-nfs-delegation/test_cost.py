"""Check the message order of the cost harness. Run: python3 test_cost.py"""
import socket
import unittest
from unittest import mock

import cost


class Tap:
    """Record each byte the client sends and receives."""

    def __init__(self, sock, log):
        sock.settimeout(5)  # A reply that never arrives fails the test.
        self.sock, self.log = sock, log

    def sendall(self, data):
        self.log.append("send " + data.decode())
        self.sock.sendall(data)

    def recv(self, size):
        data = self.sock.recv(size)
        self.log.append("recv " + data.decode())
        return data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.sock.close()


def events(policy, reopens):
    log = []
    socketpair = socket.socketpair

    def tapped():
        client, peer = socketpair()
        return Tap(client, log), peer

    with mock.patch.object(socket, "socketpair", tapped):
        cost.trial(policy, reopens)
    return log[2:]  # The warm-up exchange precedes the timed section.


class MessageOrder(unittest.TestCase):
    def test_delegated_open_reply_follows_the_return(self):
        for reopens in (0, 8):
            self.assertEqual(
                events("delegated", reopens),
                ["send O", "send K", "recv K", "send R", "recv R", "recv O"],
            )

    def test_plain_open_is_answered_on_arrival(self):
        self.assertEqual(events("plain", 0), ["send O", "recv O"])
        self.assertEqual(
            events("plain", 1),
            ["send O", "recv O", "send C", "recv C", "send O", "recv O"],
        )


if __name__ == "__main__":
    unittest.main()
