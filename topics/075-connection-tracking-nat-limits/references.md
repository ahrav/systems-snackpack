# Primary sources and derived models

Accessed 2026-10-12.

- [Linux v6.12 NAT source](https://raw.githubusercontent.com/torvalds/linux/v6.12/net/netfilter/nf_nat_core.c): original/reply tuple collision checks and bounded allocation search. Our lowest-port exhaustive model is deliberately different.
- [Conntrack sysctls](https://docs.kernel.org/networking/nf_conntrack-sysctl.html): count/max entries, two hash links per flow, buckets and state-specific idle timeouts.
- [Linux v6.12 Netfilter verdict handling](https://raw.githubusercontent.com/torvalds/linux/v6.12/net/netfilter/core.c): generic NF_DROP fallback is EPERM; the errno does not uniquely identify table exhaustion.
- [Linux IP settings](https://docs.kernel.org/networking/ip-sysctl.html): local ephemeral socket-port selection is a different scope from gateway translation.
- [AWS NAT basics](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-basics.html): documented 55000 connections per IPv4 per destination IP/port/protocol. This is a service boundary, not a Linux constant.
- [AWS NAT metrics](https://docs.aws.amazon.com/vpc/latest/userguide/metrics-dimensions-nat-gateway.html): ErrorPortAllocation.
- [EC2 tracking](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-connection-tracking.html): instance tracking allowances are distinct from Linux tables and NAT gateway ports.

Derived models: mean resident flows N ≈ admitted rate λ times mean residence T
under a stable population; destination demand N_d ≤ translated addresses A times
usable ports P; total demand sum(N_d) ≤ global capacity C. These are necessary
idealized constraints, not sufficient guarantees for a bounded real allocator.
Average hash chain occupancy L ≈ 2N/B for B buckets does not halve max flows.
For 200 flows/s and 120s residence, N≈24000. One address with 20000 usable ports
cannot sustain that demand to one destination even if C=100000. With B=16384,
mean chain occupancy is approximately 2.93.

Connection reuse reduces new-flow rate, but idle pools still consume state.
Raising max does not add translated tuples. Extra translated addresses require
allocation distribution. Shorter timeouts require an idle/liveness contract.
NOTRACK is only suitable when stateful NAT/policy dependencies have been excluded.
