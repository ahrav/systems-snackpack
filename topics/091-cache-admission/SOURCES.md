# Primary sources

Read on 2026-10-28.

- Einziger, Friedman, Manes, [TinyLFU: A Highly Efficient Cache Admission
  Policy](https://arxiv.org/abs/1512.00727). Recent-frequency admission and the
  distinction between TinyLFU and the composite W-TinyLFU policy.
- Yang et al., [S3-FIFO mechanism and evaluation](https://s3fifo.com/blog/2023/08/01/fifo-queues-are-all-you-need-for-cache-eviction/).
  Probationary, main, and ghost queues; lazy retention and workload-specific evidence.
- Yang et al., [SIEVE mechanism](https://www.usenix.org/publications/loginonline/sieve-cache-eviction-can-be-simple-effective-and-scalable).
  Visited bits, insertion order, and eviction-hand behavior.
- Caffeine authors, [Design](https://github.com/ben-manes/caffeine/wiki/Design).
  Access-order mutation, buffered read records, and stronger write-record requirements.

The exact-count teaching policies and synthetic trace results are derived
from the included source. Paper performance results are not measurements of
these implementations.
