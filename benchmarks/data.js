window.BENCHMARK_DATA = {
  "lastUpdate": 1612141895473,
  "repoUrl": "https://github.com/owais/opentelemetry-python",
  "entries": {
    "OpenTelemetry Python Benchmarks - Python 3.7 - propagator": [
      {
        "commit": {
          "author": {
            "email": "enowell@amazon.com",
            "name": "(Eliseo) Nathaniel Ruiz Nowell",
            "username": "NathanielRN"
          },
          "committer": {
            "email": "noreply@github.com",
            "name": "GitHub",
            "username": "web-flow"
          },
          "distinct": true,
          "id": "5bc23b0b027208e45c80f04ab6d983a9803607b5",
          "message": "Add resource usage performance tests for creating a span (#1499)",
          "timestamp": "2021-01-31T10:01:13-08:00",
          "tree_id": "c5f78b0abff1aeb01ed325b19c1c8d54e441b18d",
          "url": "https://github.com/owais/opentelemetry-python/commit/5bc23b0b027208e45c80f04ab6d983a9803607b5"
        },
        "date": 1612141894037,
        "tool": "pytest",
        "benches": [
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_extract_single_header",
            "value": 70589.7299227533,
            "unit": "iter/sec",
            "range": "stddev: 0.000009801025607542125",
            "extra": "mean: 14.166366709354254 usec\nrounds: 10627"
          },
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_inject_empty_context",
            "value": 148393.98178117684,
            "unit": "iter/sec",
            "range": "stddev: 0.000011218894452949438",
            "extra": "mean: 6.738817760646178 usec\nrounds: 67115"
          }
        ]
      }
    ]
  }
}