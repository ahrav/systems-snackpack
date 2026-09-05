# Primary references

Accessed 2026-09-05. RFC requirements are protocol contracts. Linux pages
describe implementation interfaces; verify the deployed kernel and qdisc path.

- [RFC 9293: TCP](https://www.rfc-editor.org/rfc/rfc9293.html): ordered byte
  streams and receive-window semantics; application writes are not packets.
- [RFC 9000 sections 4 and 13](https://www.rfc-editor.org/rfc/rfc9000.html):
  QUIC stream/connection flow control, packetization, and retransmission.
- [RFC 9002 sections 7 and 7.7](https://www.rfc-editor.org/rfc/rfc9002.html#section-7.7):
  congestion eligibility, pacing or bounded bursts, and ACK-only exceptions.
- [Linux fq manual](https://man7.org/linux/man-pages/man8/tc-fq.8.html):
  per-flow pacing, SO_MAX_PACING_RATE, and TCP departure timestamps since 4.20.
- [Linux TCP manual](https://man7.org/linux/man-pages/man7/tcp.7.html):
  TCP_NODELAY and TCP_INFO interface boundaries.
- [Linux IP sysctls](https://docs.kernel.org/networking/ip-sysctl.html):
  tcp_notsent_lowat and TCP Small Queues protect distinct buffering boundaries.
- [Linux segmentation offloads](https://docs.kernel.org/networking/segmentation-offloads.html):
  software objects can represent multiple eventual wire segments.

The pause trace, bucket implementation, and cost substitutions are this
artifact's model, not extracted transport implementation code.
