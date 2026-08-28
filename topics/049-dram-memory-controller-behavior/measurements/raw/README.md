# Raw receipt contract

Each published host bundle must contain the complete immutable receipt emitted
from the same path-limited source archive:

- controller-supplied archive digest, expected hostname, and architecture;
- host, topology, page, toolchain, build, PMU, and load metadata;
- source, script, analyzer, validator, and binary SHA-256 digests;
- the retained native binary, build identifier, runtime libraries, and linked
  disassembly;
- every chronological process attempt, pre-launch/final journal event, and its
  standard output and error;
- the fixed schedule, analysis, and independent validation reports;
- an inner manifest generated on the host.

The standalone validator receives the expected source commit and archive
SHA-256 from the controller. It freezes the schedule, treatment signs,
statistical formulas, result invariants, and exact raw filename set without
importing the acquisition runner or analyzer.

The publication directory adds the original compressed host bundles and an
outer SHA-256 manifest. A clean extraction must pass the same validator before
publication.
