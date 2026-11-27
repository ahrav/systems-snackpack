# Correctness results

The Rust model matched SQLite on 3,125 five-event histories. The oracle compared the status and current representation after each event, for 15,625 comparisons. It enforced create-if-absent with a primary key and replacement with a guarded SQL UPDATE. Two unit tests and one doctest passed. The two lost-reply histories produced the same client observation (release 12, retry changed zero rows).

Run `python3 oracle.py` and `python3 demo.py` in this directory. The PR records final-commit host replays. This is a deterministic state experiment. It measures neither S3 request latency nor throughput. S3 status codes come from the linked service contract. The example sends no cloud requests.
