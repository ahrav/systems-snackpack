# Primary sources

Checked 2026-09-29. Envoy implementation statements below are pinned to 1.39.0.
Later or deployed versions require their own configuration and source checks.

- [Mitzenmacher, The Power of Two Choices in Randomized Load Balancing (2001)](https://www.eecs.harvard.edu/~michaelm/postscripts/tpds2001.pdf): equal-server queueing model, Poisson arrivals, exponential service, and current queue observations. Its bounds are not claims about this finite burst or a production fleet.
- [Marc Brooker, The power of two random choices](https://brooker.co.za/blog/2012/01/17/two-random.html): original simulation of cached load information and herding. Its numerical crossover belongs to its stated workload.
- [Envoy 1.39.0 least-request API](https://www.envoyproxy.io/docs/envoy/v1.39.0/api-v3/extensions/load_balancing_policies/least_request/v3/least_request.proto): sampled and full-scan modes, default two choices, unequal-weight bias, and two-host miss example.
- [Envoy 1.39.0 implementation](https://github.com/envoyproxy/envoy/blob/v1.39.0/source/extensions/load_balancing_policies/least_request/least_request_lb.cc): sampling with replacement, randomized full-scan ties, optional pending counts, and effective weights.
- [Envoy 1.39.0 slow start](https://www.envoyproxy.io/docs/envoy/v1.39.0/intro/arch_overview/upstream/load_balancing/slow_start): relative ramp, all-new fleet limitation, and one-endpoint spillover.
- [HTTP/2, RFC 9113 section 5](https://www.rfc-editor.org/rfc/rfc9113.html#section-5): concurrent streams per connection.
- [NGINX load balancing](https://nginx.org/en/docs/http/load_balancing.html): round robin, weights, least connections, and affinity.
- [Envoy panic threshold](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/panic_threshold): health fallback and priority interactions; current documentation, not an executed configuration.
- [Envoy circuit breaking](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/circuit_breaking): separate request and retry limits; current documentation, not an executed configuration.
