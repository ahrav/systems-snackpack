# Primary sources and version boundaries

The executable example uses a deliberately small nearest-rank definition and
fixed interval counts. Product implementations can use different quantile
definitions, interpolation rules, schemas, or sketches. Those choices are part
of the data contract and must not be mixed silently.

## Histograms and telemetry contracts

- [Prometheus: histograms and summaries](https://prometheus.io/docs/practices/histograms/)
  explains why precomputed client quantiles are not aggregatable and why bucket
  counts can be summed before applying `histogram_quantile`.
- [Prometheus query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/)
  defines `histogram_quantile`, interpolation behavior, required classic bucket
  labels, and mixed classic/native handling for current Prometheus releases.
- [Prometheus native histogram specification](https://prometheus.io/docs/specs/native_histograms/)
  defines standard schemas, resolution reduction, custom buckets, reset hints,
  and merge compatibility. Native histograms are stable in Prometheus 3.8; an
  installation still controls ingestion through its scrape configuration.
- [OpenTelemetry metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/)
  defines histogram and exponential-histogram points, aggregation temporality,
  point kinds, and reset handling. Histogram, exponential histogram, and
  temporality are stable; some reset and gap details remain marked Development.
- [OpenTelemetry Metrics software development kit](https://opentelemetry.io/docs/specs/otel/metrics/sdk/)
  defines aggregation selection and explicit or exponential bucket behavior.

## Mergeable distributions and sketches

- [HdrHistogram implementation and documentation](https://github.com/HdrHistogram/HdrHistogram)
  defines its configurable value range, significant-digit precision, constant
  relative precision, and coordinated-omission correction boundary.
- [HdrHistogram Java 2.2.2 merge implementation](https://github.com/HdrHistogram/HdrHistogram/blob/HdrHistogram-2.2.2/src/main/java/org/HdrHistogram/AbstractHistogram.java#L1698-L1745)
  directly adds compatible layouts and otherwise re-records representative
  values. Auto-resize and representable-range behavior are implementation
  configuration, not universal histogram properties.
- [DDSketch paper](https://www.vldb.org/pvldb/vol12/p2195-masson.pdf)
  derives a mergeable quantile sketch with a relative value-error guarantee for
  supported positive values under a compatible logarithmic mapping.
- [DDSketch Java implementation](https://github.com/DataDog/sketches-java/blob/master/src/main/java/com/datadoghq/sketch/ddsketch/DDSketch.java)
  requires compatible index mappings for merge in the referenced implementation.
- [Apache DataSketches: order sensitivity](https://datasketches.apache.org/docs/Architecture/OrderSensitivity.html)
  documents that input order can change an approximate sketch's result while
  the result remains inside the documented error distribution.

## Quantile definitions and statistical uncertainty

- [Hyndman and Fan: Sample Quantiles in Statistical Packages](https://robjhyndman.com/papers/sample_quantiles.pdf)
  classifies common sample-quantile definitions. A label such as p99 is
  incomplete without the selected definition for small samples and ties.
- [NIST Technical Note 2119: Quantile confidence intervals](https://doi.org/10.6028/NIST.TN.2119)
  gives distribution-free and other interval methods for quantiles. Sampling
  uncertainty is separate from histogram approximation error.
- [wrk2](https://github.com/giltene/wrk2)
  documents constant-throughput load generation and corrected latency recording
  for coordinated omission. Correct aggregation cannot repair observations that
  were never sampled.
