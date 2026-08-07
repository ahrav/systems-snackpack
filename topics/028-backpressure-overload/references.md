# Primary references

## Retry amplification and overload control

- [Amazon Builders' Library, *Timeouts, retries, and backoff with
  jitter*](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
  explains why retries are selfish load, why retry budgets cap amplification,
  and why jitter spreads synchronized retries. It motivates the controls; it
  does not validate this artifact's counts or timing.
- [Google SRE, *Addressing Cascading
  Failures*](https://sre.google/sre-book/addressing-cascading-failures/)
  describes retry-driven positive feedback, bounded queues, load shedding, and
  randomized exponential backoff. The chapter concerns production systems;
  this artifact isolates one synthetic miss wave.
- [Google SRE, *Handling
  Overload*](https://sre.google/sre-book/handling-overload/)
  covers fast rejection, client-side throttling, per-request and per-client
  retry budgets, and the distinction between local and global overload. It
  supports the need for layered bounds, not the numeric defaults chosen here.
- [AWS Architecture Blog, *Exponential Backoff and
  Jitter*](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
  demonstrates that deterministic capped backoff preserves clusters of
  contending clients while jitter reduces synchronized work. This is why the
  focused experiment omits fixed backoff rather than presenting it as a
  production remedy.
- [Go `singleflight` package](https://pkg.go.dev/golang.org/x/sync/singleflight)
  defines duplicate call suppression in which one execution runs for a key and
  duplicate callers receive the shared result. It is a reference for the
  mechanism, not a dependency or proof of this Rust implementation.

## DNS boundary

- [Amazon Builders' Library, *Caching challenges and
  strategies*](https://aws.amazon.com/builders-library/caching-challenges-and-strategies/)
  connects cold or expired caches to downstream traffic surges and describes
  request coalescing, negative caching, soft/hard TTLs, backpressure, and load
  shedding. This artifact isolates coalescing and hard bounds; it implements no
  cache state or expiry policy.
- [RFC 1034, *Domain Names: Concepts and
  Facilities*](https://www.rfc-editor.org/rfc/rfc1034) and [RFC 1035, *Domain
  Names: Implementation and Specification*](https://www.rfc-editor.org/rfc/rfc1035)
  define DNS names, caches, resolver behavior, messages, and TTL semantics.
  None of those protocol mechanisms is implemented by this artifact.
- [RFC 2308, *Negative Caching of DNS Queries*](https://www.rfc-editor.org/rfc/rfc2308)
  defines negative answers and negative-cache TTL handling.
- [RFC 9520, *Negative Caching of DNS Resolution
  Failures*](https://www.rfc-editor.org/rfc/rfc9520.html) updates failure-caching
  requirements. Real failure caching can suppress repeated resolver work; this
  experiment contains no cache or TTL.
- [RFC 8767, *Serving Stale Data to Improve DNS
  Resiliency*](https://www.rfc-editor.org/rfc/rfc8767.html) defines how recursive
  resolvers may use expired cached data when refresh fails. Serve-stale can
  avoid an origin miss wave; this experiment begins after a synthetic miss and
  does not evaluate freshness or stale-answer policy.
- [CoreDNS `cache` plugin](https://coredns.io/plugins/cache/) documents success
  and denial caches, capacity, TTL controls, prefetch, `serve_stale`, SERVFAIL
  caching, and metrics. Those controls materially change real miss traffic and
  are outside the synthetic one-key state machine.
- Kubernetes [DNS for Services and
  Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
  defines cluster DNS names and Pod resolver policy. [NodeLocal
  DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)
  documents the per-node caching path, upstream forwarding, negative caching,
  concurrency-related memory demand, and observability. The artifact models
  neither Kubernetes routing nor a NodeLocal/CoreDNS deployment.

## Rust synchronization contracts

- Rust's [`Barrier`](https://doc.rust-lang.org/std/sync/struct.Barrier.html)
  defines the rendezvous used to release a synchronized wave and freeze the
  admission population before work begins.
- Rust's [`Condvar`](https://doc.rust-lang.org/std/sync/struct.Condvar.html)
  documents predicate-based waiting, notification, mutex reacquisition, and
  spurious wakeups. Controlled followers recheck the terminal predicate while
  holding the flight mutex.
- Rust's [`Mutex`](https://doc.rust-lang.org/std/sync/struct.Mutex.html),
  [`AtomicUsize`](https://doc.rust-lang.org/std/sync/atomic/struct.AtomicUsize.html),
  and [`Instant`](https://doc.rust-lang.org/std/time/struct.Instant.html)
  define the state protection, peak counters, and monotonic process-local
  timestamps used in receipts. Nanosecond units do not imply nanosecond timer
  resolution or cross-host clock equivalence.
