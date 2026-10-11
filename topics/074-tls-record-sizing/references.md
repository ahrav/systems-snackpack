# Primary sources

Read 2026-10-11. Protocol budgeting is separate from runtime observations.

- [RFC 9846, sections 5.1-5.4](https://datatracker.ietf.org/doc/rfc9846/): current
  TLS 1.3, 16384 content bytes, inner type/padding, 16385 inner plaintext bound,
  and the distinct 16640-byte encrypted field bound. Supersedes RFC 8446.
- [RFC 8449, sections 1 and 4](https://www.rfc-editor.org/rfc/rfc8449.html):
  authenticated-record completion and directional receive limits including
  TLS 1.3 inner type/padding.
- [OpenSSL 3.6 fragment controls](https://docs.openssl.org/3.6/man3/SSL_CTX_set_split_send_fragment/):
  local plaintext send cap, default 16384, accepted 512..16384.
- [OpenSSL 3.6 writes](https://docs.openssl.org/3.6/man3/SSL_write/): successful
  full/partial writes versus WANT_READ/WANT_WRITE retry semantics.
- [nginx SSL buffer](https://nginx.org/en/docs/http/ngx_http_ssl_module.html#ssl_buffer_size):
  sending buffer default 16k and conditional 4k time-to-first-byte suggestion.
- [RFC 9293, section 3.7](https://www.rfc-editor.org/rfc/rfc9293.html#section-3.7): TCP byte-stream boundaries.
- [RFC 9001, section 4](https://www.rfc-editor.org/rfc/rfc9001.html#section-4):
  QUIC uses TLS handshake/key derivation and its own packet protection.

Derived model: for flushed writes g_i and effective content cap R, record count
is sum(ceil(g_i/R)). With the selected 16-byte tag and zero padding, wire bytes
are sum(g_i)+22*records. This excludes TCP/IP and retransmissions. For ready
65536-byte content, caps 1024/4096/16384 use 64/16/4 records and add 1408/352/88
TLS bytes. Flushing 512 separate 128-byte writes uses 512 records at every cap.

At assumed continuous 10 Mbit/s, first-full-record serialization is
8*(R+22)/10000000 seconds: 0.837/3.294/13.125 ms. This is a calculation, not
measured latency. A fill-only policy with 1024 bytes queued and production at
65536 bytes/s waits (R-1024)/65536 seconds for larger caps: 46.875 ms at 4096
and 234.375 ms at 16384. TLS does not require that policy. Deadline coalescing
and adaptive first-small/later-large policies are not benchmarked here.
