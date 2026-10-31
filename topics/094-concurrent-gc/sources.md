# Primary sources

- [Go write-barrier implementation](https://go.dev/src/runtime/mbarrier.go): deletion and insertion shading, pre-publication ordering, and color-check memory-ordering costs.
- [Go GC guide](https://go.dev/doc/gc-guide): allocation rate, live heap, roots, heap targets, assists, and memory limits.
- [Hybrid-barrier design](https://github.com/golang/proposal/blob/master/design/17503-eliminate-rescan.md): stack scanning and preservation arguments.

Read 2026-10-31. The model implements separate unconditional barriers with atomic
steps. It illustrates preservation obligations without reproducing Go's collector.
