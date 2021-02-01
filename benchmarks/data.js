window.BENCHMARK_DATA = {
  "lastUpdate": 1612141909291,
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
    ],
    "OpenTelemetry Python Benchmarks - Python 3.6 - propagator": [
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
        "date": 1612141897101,
        "tool": "pytest",
        "benches": [
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_extract_single_header",
            "value": 60666.81200230463,
            "unit": "iter/sec",
            "range": "stddev: 0.0000023351898630410335",
            "extra": "mean: 16.48347699500036 usec\nrounds: 8780"
          },
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_inject_empty_context",
            "value": 128169.05493732859,
            "unit": "iter/sec",
            "range": "stddev: 0.0000015050953565398604",
            "extra": "mean: 7.8021953153120664 usec\nrounds: 58137"
          }
        ]
      }
    ],
    "OpenTelemetry Python Benchmarks - Python 3.5 - propagator": [
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
        "date": 1612141905214,
        "tool": "pytest",
        "benches": [
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_extract_single_header",
            "value": 48522.07195251328,
            "unit": "iter/sec",
            "range": "stddev: 7.897248727184175e-7",
            "extra": "mean: 20.609177633194687 usec\nrounds: 7994"
          },
          {
            "name": "propagator/opentelemetry-propagator-b3/tests/performance/benchmarks/trace/propagation/test_benchmark_b3_format.py::test_inject_empty_context",
            "value": 112042.81756305185,
            "unit": "iter/sec",
            "range": "stddev: 3.8630199479174583e-7",
            "extra": "mean: 8.92515934309892 usec\nrounds: 46949"
          }
        ]
      }
    ]
  }
}