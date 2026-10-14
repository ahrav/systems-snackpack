# Primary sources

Checked 2026-10-14.

- [etcd API](https://etcd.io/docs/v3.7/learning/api/): snapshot revision,
  inclusive watch start, range selection, and compacted-history cancellation.
- [etcd API guarantees](https://etcd.io/docs/v3.7/learning/api_guarantees/):
  ordered complete-revision watch delivery within available history; watch
  delay does not have a fixed upper bound. Filtered watches may skip global
  revisions, and one revision can contain several key events.
- [GIGA+](https://www.pdl.cmu.edu/PDL-FTP/PDSI/fast2011-gigaplus_abs.shtml):
  incremental partitioning and stale client routing repair.
- [IndexFS](https://www.pdl.cmu.edu/PDL-FTP/FS/IndexFS-SC14.pdf): directory
  partitioning, metadata caching, and bulk insertion address different costs.

The dense single-epoch protocol and constant-rate catch-up calculation are
teaching models. Neither reproduces a production service or its throughput.
