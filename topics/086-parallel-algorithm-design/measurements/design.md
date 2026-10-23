# Fixed experiment design, before collection

Compare three correct scans modulo 2^64: serial, local scan then add, chunk totals
then rescan. The question is complete-operation cost at each size and requested
worker count on each named host, not production or architecture-wide performance.

Inputs are the sequence 1..=n, n=4096,262144,4194304. Every output and total is
checked against the triangular-number formula outside timing. Independent Python
arbitrary-precision prefix slicing tests random full-width integers and boundaries.

Per host: one native Rust1.93.1 build, opt3, one CGU, no LTO, unwind. Six complete
blocks contain all six orders of the three candidates. Size/worker cell order is
reversed in odd blocks. No randomized assignment; the exact deterministic schedule
is in run.py. Each of 162 measured processes has two warmups and 16/8/4 calls for
small/medium/large. Two additional identical-artifact serial processes check the
A/A path mechanically, not calibration. No variance pilot, power target, confidence
interval, significance test, or population inference is claimed. Fixed effort
supports descriptive comparisons only. No optional stopping, retries of measurement
failures, or discarded outliers. Failed attempts are retained and stop the campaign.

A process receives a treatment; a complete ordered block is the pairing unit.
Calls inside a process are subsamples. Six blocks are repetitions in one shared-host
window, not proof of independence. Cache, thermal, scheduler and background-load
interference remain. Initial input/output allocation and serial first-touch,
correctness and printing are outside timing. Scratch Vec allocation, two waves of
thread spawn/join, serial summary scan, all data passes, and dispatch are inside.
Serial ignores worker count but is repeated in every matched cell. Parallel variants
spawn min(requested workers, n) threads per wave; the caller coordinates separately.

Linux runner affinity is CPU0..7 for every candidate and inherited by children.
Record allowed masks and topology; CPUs must be distinct visible cores in one node.
Workers are not individually pinned, so migration within this set remains possible.
No cache flush, NUMA policy change, host tuning or exclusive-host reservation.

Report per-cell median/min/max ns per element and all six paired ratios for every
candidate pair. A wins only when every A/B ratio is below 1/1.05; B wins only when
every ratio exceeds1.05. All ratios inside [1/1.05,1.05] are a practical tie;
otherwise unresolved. This is a descriptive rule with no familywise error guarantee.
Do not turn minimum median into a declared winner if paired evidence is unresolved.
Logical source-level byte counts do not measure memory bandwidth or prove cause.
