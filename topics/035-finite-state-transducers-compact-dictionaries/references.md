# Primary sources and version boundaries

The papers define automaton and transducer correctness. Versioned official
documentation and source define current implementation behavior. Project-owned
performance examples do not rank these representations for another corpus.

## Construction and transducers

- [Daciuk, Mihov, Watson, and Watson, "Incremental construction of minimal
  acyclic finite state automata"](https://aclanthology.org/J00-1002/)
  defines right-language equivalence plus sorted and unsorted incremental
  construction.
- [Mohri, "Finite-State Transducers in Language and Speech
  Processing"](https://aclanthology.org/J97-2003/)
  defines sequential and subsequential transducers, output pushing, and
  minimization boundaries.
- [Skut, "Incremental Construction of Minimal Acyclic Sequential Transducers
  from Unsorted Data"](https://arxiv.org/pdf/cs/0408026)
  addresses output-bearing construction when inputs do not arrive sorted.
- [Schulz and Mihov, "Fast String Correction with Levenshtein
  Automata"](https://doi.org/10.1007/s10032-002-0082-8)
  defines Levenshtein automata and dictionary traversal controlled by their
  edit-distance states.

## Current implementations

- [Rust `fst` 0.4.7 raw documentation](https://docs.rs/fst/0.4.7/fst/raw/struct.Fst.html)
  states the bounded-registry minimality and verification boundaries.
- [Rust `fst` 0.4.7 node decoder](https://github.com/BurntSushi/fst/blob/0.4.7/src/raw/node.rs)
  defines packed transition decoding and the linear-versus-direct-index fanout
  threshold.
- [Lucene 10.4.0 `FSTCompiler`](https://lucene.apache.org/core/10_4_0/core/org/apache/lucene/util/fst/FSTCompiler.html)
  defines sorted construction and suffix-sharing controls.
- [Lucene 10.4.0 `FST`](https://lucene.apache.org/core/10_4_0/core/org/apache/lucene/util/fst/FST.html)
  documents version-tagged ordinary, fixed-length binary-search,
  direct-addressed, and continuous-label traversal cases.
- [Lucene 10.4.0 `Outputs`](https://lucene.apache.org/core/10_4_0/core/org/apache/lucene/util/fst/Outputs.html)
  defines the output operations required by construction and traversal.
- [OpenFST minimization documentation](https://openfst.org/twiki/bin/view/FST/MinimizeDoc)
  defines weighted and transducer preconditions plus the string-output-label
  representation caveat.
- [OpenFST representation guidance](https://openfst.org/twiki/bin/view/FST/FstEfficiency)
  distinguishes mutable, immutable, and compact representations.
- [MARISA 0.3.1 documentation](https://www.s-yata.jp/marisa-trie/docs/readme.en.html)
  defines static Patricia-trie search modes, cache choices, mapping, and format
  boundaries.
- [Darts-clone implementation](https://github.com/s-yata/darts-clone/blob/master/include/darts.h)
  defines the double-array representation and direct transition arithmetic.

## Text and Linux lifecycle contracts

- [Unicode Standard Annex #15](https://unicode.org/reports/tr15/)
  defines normalization forms. Exact byte equality alone does not implement
  canonical text equivalence.
- [Unicode Technical Standard #10](https://unicode.org/reports/tr10/)
  defines collation weights and tailoring separately from normalization and
  application-level key identity.
- [Linux page-cache documentation](https://www.kernel.org/doc/html/latest/mm/page_cache.html)
  describes file pages shared by buffered I/O and memory mappings.
- [Linux `mmap(2)`](https://man7.org/linux/man-pages/man2/mmap.2.html)
  defines mapping, lifetime, and signal behavior.
- [Linux `rename(2)`](https://man7.org/linux/man-pages/man2/renameat.2.html)
  defines atomic name replacement within its documented filesystem boundary.
- [Linux `fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html)
  distinguishes file-data completion from directory-entry durability.

## Model boundary

The lookup, complete-byte, enumeration, and rebuild equations in this topic are
analytical models. No cited library exposes them as a runtime estimator. The
crate measures a source-defined acceptor with no payload output and makes no
production-library performance claim.
