# Raw Topic 50 receipts

Each dated directory binds accepted host archives to one committed,
path-limited source archive. It records:

- the full source commit and source-archive SHA-256 digest;
- the runtime resolution of the `xxl` Secure Shell (SSH) alias;
- immutable Arm and x86 host-result archives;
- controller-side validation results supplied with expected host,
  architecture, commit, and archive digest; and
- an outer checksum manifest for the published receipt files.

The host archives retain all fixed-schedule attempts. A failed campaign is
preserved as rejected evidence and is never repaired by replacing individual
periods.
