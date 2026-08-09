# Idempotency under concurrency

A timeout on a mutating request does not prove failure. The request may never
have arrived, or the effect may have committed while the reply was lost. A safe
retry contract makes every attempt for one caller-named intent converge on one
effect and one replayable receipt.

This crate models the contract in memory. It is not a durable database or
network implementation.

## One running example

`CreateCharge(order-42, 2000 cents)` carries key `K`. The key means that every
attempt carrying `K` belongs to one logical charge. A different key represents
a different intent even when the order and amount match.

```text
ABSENT --conditional claim--> IN_PROGRESS(generation)
IN_PROGRESS --effect + receipt in one commit--> COMPLETE(resource)

same key, same fingerprint:
  IN_PROGRESS -> conflict, wait, or status lookup
  COMPLETE    -> replay the retained result

same key, changed fingerprint:
  PARAMETER_MISMATCH
```

A fingerprint validates key reuse. It does not infer identity from equal
parameters.

## Safety conditions

- The lookup key includes caller or tenant, operation, service scope, and the
  caller-generated key.
- One conditional claim selects the in-progress owner.
- The local effect and completed receipt share one atomic commit.
- A takeover increments a generation and rejects stale completion.
- The API documents key retention and late-retry behavior.
- A remote effect accepts the same logical key or uses an outbox and an
  idempotent consumer.

The model's `Mutex` supplies process-local serialization. It does not supply
durability, cross-process exclusion, expiry, or remote-effect atomicity.

## Cost model

Let `lambda` be new intents per second, `T` the retention interval, `b` stored
bytes per receipt including indexes, `k` the physical storage multiplier, and
`R` the mean retries after the first attempt.

```text
retained receipts       ~= lambda * T
physical receipt bytes  ~= lambda * T * b * k
attempt rate            ~= lambda * (1 + R)
```

Idempotency keeps committed effects at one per retained key. It does not remove
retry traffic. Concurrent attempts for one key also serialize at its receipt
record.

## Failure boundaries

- Effect before receipt can duplicate the effect after a crash and retry.
- Receipt before effect can replay success for work that never happened.
- Parameter-hash deduplication merges distinct identical intents.
- Expiry without generation fencing permits a slow old owner to finish after a
  takeover.
- A unique database row does not cover an email, payment processor, broker, or
  other external system.
- Broker transactions cover only their documented transaction domain.

## Run locally

From the repository root:

```bash
cargo test --locked --package idempotency-concurrency
cargo build --locked --release --package idempotency-concurrency \
  --bin idempotency-probe

target/release/idempotency-probe --self-check

python3 topics/030-idempotency-concurrency/experiment/run_processes.py \
  target/release/idempotency-probe \
  /tmp/topic30-local

python3 topics/030-idempotency-concurrency/experiment/validate_receipts.py \
  /tmp/topic30-local \
  target/release/idempotency-probe
```

The output directory must not exist. The runner launches eight fresh processes
and records every exit, output, and digest. The validator recomputes the result
without trusting the summary. No timing metric is reported because an in-memory
lock does not estimate durable transaction or network cost.

See [`rounds/01.md`](rounds/01.md) for the acceptance contract,
[`measurements/README.md`](measurements/README.md) for exact-source promotion,
and [`references.md`](references.md) for source boundaries.
