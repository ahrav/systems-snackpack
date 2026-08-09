# Primary references

## Request identity and replay

- [RFC 9110 section 9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
  defines HTTP method idempotency as the same intended server effect. It does
  not require identical responses or suppress per-attempt logging.
- Malcolm Featonby, [*Making retries safe with idempotent
  APIs*](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/),
  specifies caller-provided request identity, atomic receipt and mutation,
  changed-parameter rejection, and semantically equivalent retry responses.
- [Google AIP-155](https://google.aip.dev/155) places `request_id` on the
  request, recommends UUID version 4, permits service-defined retention, and
  allows a current resource state to replace an unavailable historical reply.
- [Stripe API v1 idempotency](https://docs.stripe.com/api/idempotent_requests)
  retains the first result after endpoint execution begins. [Stripe API
  v2](https://docs.stripe.com/api-v2-overview#idempotency) has different method,
  scope, retention, and failed-work behavior. Claims must name the API version.
- [EC2 idempotency](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-idempotency.html)
  documents regional and zonal token scopes. [ECS
  idempotency](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_Idempotency.html)
  documents per-cluster scope and operation-specific retention.

## Atomic and message boundaries

- PostgreSQL 18 [unique-index
  checks](https://www.postgresql.org/docs/18/index-unique-checks.html),
  [`INSERT ... ON CONFLICT`](https://www.postgresql.org/docs/18/sql-insert.html),
  and [Read Committed
  behavior](https://www.postgresql.org/docs/18/transaction-iso.html) define the
  concurrency boundary for a local unique receipt. They do not cover external
  effects.
- [AWS transactional-outbox
  guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
  writes business state and an outbox record in one transaction. The relay can
  publish duplicates, so consumers still need durable message identity.
- [Debezium's Outbox Event
  Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
  exposes the outbox event identifier for downstream deduplication.
- [Kafka 4.1 delivery
  semantics](https://kafka.apache.org/41/design/design/#message-delivery-semantics)
  scope atomic offset and output commits to Kafka transactions. External
  destinations must cooperate or remain idempotent.

## Knowledge boundary

- Saltzer, Reed, and Clark, [*End-To-End Arguments in System
  Design*](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.pdf),
  explains why lower-layer duplicate suppression cannot replace application
  identity and validation.
- Halpern and Moses, [*Knowledge and Common Knowledge in a Distributed
  Environment*](https://groups.csail.mit.edu/tds/papers/Halpern/JACM90.pdf),
  establishes the common-knowledge limit under unreliable communication.
- Fischer, Lynch, and Paterson,
  [*Impossibility of Distributed Consensus with One Faulty
  Process*](https://groups.csail.mit.edu/tds/papers/Lynch/jacm85.pdf), concerns
  deterministic consensus termination in an asynchronous crash model. It does
  not prove that every scoped exactly-one effect is impossible.

## Artifact boundary

The sources justify protocol contracts and failure boundaries. Unit tests,
fresh-process receipts, source and binary hashes, and generated-code records
validate this in-memory artifact only. They do not validate a durable database,
network protocol, external payment system, or production authorization model.
