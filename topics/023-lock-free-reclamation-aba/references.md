# Primary sources

- Maged M. Michael, [“Hazard Pointers: Safe Memory Reclamation for Lock-Free Objects”](https://research.ibm.com/publications/hazard-pointers-safe-memory-reclamation-for-lock-free-objects), IEEE TPDS, 2004.
- WG21 P2530R3, [“Hazard Pointers for C++26”](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2023/p2530r3.pdf), including the protect-validation protocol and two-slot traversal.
- Keir Fraser, [*Practical Lock-Freedom*](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-579.pdf), section 5.2.3 on three-epoch reclamation and stalled participants.
- Trevor Brown, [“Reclaiming Memory for Lock-Free Data Structures”](https://mc.uwaterloo.ca/pubs/debra/paper.podc15.pdf), on EBR fault tolerance and retained-memory bounds.
- Linux kernel documentation, [“A Tour Through RCU's Requirements”](https://docs.kernel.org/RCU/Design/Requirements/Requirements.html), for grace-period and publish-subscribe guarantees.
- Rust standard library, [`AtomicPtr::compare_exchange`](https://doc.rust-lang.org/std/sync/atomic/struct.AtomicPtr.html#method.compare_exchange), for equality-versus-identity and ABA.
- Crossbeam Epoch 0.9.20, [crate documentation](https://docs.rs/crossbeam-epoch/0.9.20/crossbeam_epoch/), for the current guard and deferred-destruction boundary.
- Maurice Herlihy, [“Wait-Free Synchronization”](https://cs.brown.edu/~mph/Herlihy91/p124-herlihy.pdf), for progress guarantees.
