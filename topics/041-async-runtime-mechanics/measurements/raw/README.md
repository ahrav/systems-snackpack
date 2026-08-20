# Raw evidence

Each retained directory binds one committed source candidate to:

- its Git-created source archive and Secure Hash Algorithm 256-bit (SHA-256)
  digest;
- the runtime resolution of the `xxl` alias;
- one result archive from the literal Arm host;
- one result archive from the resolved x86-64 host; and
- a local receipt manifest and validation record.

Generated binaries are evidence for their named compiler and host. They are not
stable Rust application binary interfaces or architecture-wide performance
claims.
