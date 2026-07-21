# Superseded candidate `4b00356`

Candidate `4b00356711a3934fd92ec62a099991a71ecd6529` used archive SHA-256
`d9952eb769dbf1d8716fa32cebca446e87fbf1948d4388645546896d60b05bc9`.
Its raw records, hashes, generated code, and summaries remain under
[`raw/4b00356`](raw/4b00356).

The Arm host selected `ISB; MRS CNTVCT_EL0; ISB`. The x86-64 host selected
`MFENCE; RDTSC; MFENCE`. A refute-first review found that the cited AMD
architecture manual describes RDTSC as nonserializing and does not establish
that sequence as a general instruction-execution boundary. The pair therefore
cannot support the artifact's stated boundary. This is a contract failure, not
a claim that the recorded arithmetic timings are numerically corrupted.

The candidate also described `time_offset + scale(cycles)` as a perf absolute
timestamp. Linux uses that delta under `cap_user_time` to update enabled/running
time. Absolute conversion instead requires the `cap_user_time_zero` contract;
short hardware clocks additionally require the `cap_user_time_short`
reconstruction. The portable helper was renamed and scoped to generic
fixed-point endpoint rounding.

The correction uses RDTSCP's prior-instruction/load boundary plus a following
serializing CPUID, captures TSC_AUX, and retains the independent CPU check. New
evidence must come from a new commit-bound archive and pass both hosts.
