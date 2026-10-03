# Primary sources and claim boundaries

Retrieved 2026-09-28. These papers define mathematical models. The repository's
mixer and service-cost inputs do not claim to satisfy or measure every premise.

- [Bloom (1970)](https://courses.cs.washington.edu/courses/csep521/21wi/readings/bloom_cacm.pdf):
  membership prefilter, allowable false positives, space/time tradeoff.
- [Kirsch and Mitzenmacher, Building a Better Bloom Filter](https://www.eecs.harvard.edu/~michaelm/postscripts/tr-02-05.pdf):
  Section 2, occupancy approximation and optimal probe/space calculation.
- [Cormode and Muthukrishnan, Count-Min](https://www.cs.ox.ac.uk/people/graham.cormode/pubs/papers/cm-full.pdf):
  Sections 2-4, signed-stream distinctions, dimensions, nonnegative point-query
  bound, independent rows with suitable within-row collision bounds, linearity.
- [Flajolet et al. (2007)](https://algo.inria.fr/flajolet/Publications/FlFuGaMe07.pdf):
  register maxima and classical asymptotic relative standard error.
- [Apache HLL implementation documentation](https://datasketches.apache.org/docs/HLL/HllSketches.html):
  implementation-specific estimators and non-Gaussian error boundaries. This is
  not a version-pinned API claim, nor an implementation used by this experiment.
- [Fan et al. (2014)](https://www.cs.cmu.edu/~dga/papers/cuckoo-conext2014.pdf):
  Sections 3.3-3.4, insertion failure and deletion only for inserted items.
- [Graf and Lemire (2020)](https://arxiv.org/abs/1912.08258):
  XOR filters for static sets, construction versus lookup tradeoffs.

Measured claims belong only to the exact experiment and hosts named in the
measurement receipt. Service cost, expiry policy, and publication fallback are
explicit engineering deductions, not reported measurements from these sources.
