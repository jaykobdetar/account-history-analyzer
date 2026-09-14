# PELT PR #383 comparison

Numerical results use identical input arrays and pinned CostL2. Runtime and allocation observations below are benchmark receipts, separate from `comparison.json`.

| Workload | N × D | Minimum | Same boundaries | Objective difference | Old median ms | New median ms | New/old time | Old/new traced peak KiB |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| archived_standardized_style_matrix_min3 | 29 × 31 | 3 | True | 0 | 1.945 | 2.042 | 1.050 | 14.6 / 23.4 |
| archived_standardized_style_matrix_min20 | 29 × 31 | 20 | True | 0 | 0.220 | 0.231 | 1.047 | 18.6 / 21.1 |
| constructed_stationary_n128_min3 | 128 × 8 | 3 | True | 0 | 77.950 | 79.969 | 1.026 | 36.1 / 97.0 |
| constructed_stationary_n128_min20 | 128 × 8 | 20 | True | 0 | 44.795 | 43.788 | 0.978 | 32.5 / 80.4 |
| constructed_steps_n128_min3 | 128 × 8 | 3 | True | 0 | 23.887 | 24.289 | 1.017 | 19.8 / 65.6 |
| constructed_steps_n128_min20 | 128 × 8 | 20 | True | 0 | 17.589 | 18.335 | 1.042 | 20.1 / 55.7 |
| constructed_stationary_n256_min3 | 256 × 8 | 3 | True | 0 | 392.403 | 378.263 | 0.964 | 69.3 / 192.8 |
| constructed_stationary_n256_min20 | 256 × 8 | 20 | True | 0 | 284.688 | 295.834 | 1.039 | 65.7 / 176.2 |
| constructed_steps_n256_min3 | 256 × 8 | 3 | True | 0 | 100.786 | 106.038 | 1.052 | 36.6 / 129.8 |
| constructed_steps_n256_min20 | 256 × 8 | 20 | True | 0 | 74.055 | 76.332 | 1.031 | 34.7 / 114.6 |

Five untraced timing repetitions and five separately traced allocation repetitions follow one untimed warmup in a fresh worker for each optimizer/workload (configured repetitions: 5).

Tracemalloc peaks describe allocations it tracks during a single call, excluding the already-created input. RSS is process-wide high-water memory including imports and warmup; its increase can be zero when imports set the peak. Tracing is disabled during timing.

Boundaries and objectives are exposed independently: equal objective within the explicit tolerance need not imply identical boundaries under ties. These bounded workloads are engineering observations, not asymptotic, cross-platform, or real-world detection-accuracy claims.
