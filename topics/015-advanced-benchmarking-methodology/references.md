# Primary sources

- [Kalibera and Jones, *Rigorous Benchmarking in Reasonable
  Time*](https://kar.kent.ac.uk/33611/45/p63-kaliber.pdf): repetition levels,
  top-level variance, effect intervals, and cost-aware experiment design.
- [Georges, Buytaert, and Eeckhout, *Statistically Rigorous Java Performance
  Evaluation*](https://users.elis.ugent.be/~leeckhou/papers/oopsla07-stat.pdf):
  startup versus steady-state estimands and execution-level replication.
- [Mytkowicz et al., *Producing Wrong Data Without Doing Anything Obviously
  Wrong!*](https://sape.inf.usi.ch/publications/asplos09.html): layout bias,
  causal analysis, and setup randomization in the tested SPEC CPU2006 matrix.
- [NIST randomized-block
  design](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm) and
  [paired
  observations](https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm):
  block construction and analysis of within-pair differences.
- [Howard et al., *Time-uniform, nonparametric, nonasymptotic confidence
  sequences*](https://doi.org/10.1214/20-AOS1991): intervals valid over time
  under the paper's stated martingale and tail conditions.
- [Rust `black_box`
  documentation](https://doc.rust-lang.org/stable/std/hint/fn.black_box.html):
  best-effort optimizer behavior and explicit proof limits.
- [Criterion.rs analysis
  process](https://criterion-rs.github.io/book/analysis.html): warmup, batched
  samples, regression, bootstrap intervals, and comparison mechanics.
- [Linux
  `sched_setaffinity(2)`](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html):
  affinity semantics. Affinity restricts eligibility; it does not provide
  exclusive CPU isolation.
- [Schroeder, Wierman, and Harchol-Balter, *Open Versus Closed: A Cautionary
  Tale*](https://www.usenix.org/conference/nsdi-06/open-versus-closed-cautionary-tale):
  response-time differences between independent arrivals and
  completion-paced workloads.
