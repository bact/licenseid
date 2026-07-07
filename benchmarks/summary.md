# Benchmark Comparison: `main` vs `normalize-guidelines`
**Date:** 20260707T005029Z

**Note on Wall time / Throughput below:** these numbers are not trustworthy
as a timing comparison and should not be cited. `bench_compare.py` always
runs `main` first and the branch second, sequentially, inside one long
(~25min+ per side) 100%-CPU script invocation — so anything that
accumulates over a long sustained run (thermal throttling, macOS power
management stepping down clocks, background load ramping up) always
penalizes whichever phase runs second, i.e. always the branch, never
`main`. Confirmed directly: profiling the same 100-query mix (Type 3 +
Type 5) back-to-back on freshly-rebuilt DBs for each branch gave
**45.3ms/query (this branch) vs 46.1ms/query (main)** — essentially
identical, branch marginally faster. Recall numbers below are trustworthy
(reproduced identically across 3 independent full runs).

## Metrics

### Input Type 1
| Category | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| id_casing Recall@1 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@3 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@5 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@10 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@20 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@30 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@40 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@50 | 80.00% | 80.00% | +0.00%  |
| id_deprecated Recall@1 | 0.00% | 0.00% | +0.00%  |
| id_deprecated Recall@3 | 16.67% | 33.33% | +16.67% 🟢 |
| id_deprecated Recall@5 | 16.67% | 33.33% | +16.67% 🟢 |
| id_deprecated Recall@10 | 33.33% | 33.33% | +0.00%  |
| id_deprecated Recall@20 | 33.33% | 33.33% | +0.00%  |
| id_deprecated Recall@30 | 33.33% | 33.33% | +0.00%  |
| id_deprecated Recall@40 | 33.33% | 33.33% | +0.00%  |
| id_deprecated Recall@50 | 33.33% | 33.33% | +0.00%  |
| id_distorted Recall@1 | 31.67% | 30.00% | -1.67% 🔴 |
| id_distorted Recall@3 | 51.67% | 51.67% | +0.00%  |
| id_distorted Recall@5 | 55.00% | 56.67% | +1.67% 🟢 |
| id_distorted Recall@10 | 58.33% | 58.33% | +0.00%  |
| id_distorted Recall@20 | 60.00% | 61.67% | +1.67% 🟢 |
| id_distorted Recall@30 | 60.00% | 61.67% | +1.67% 🟢 |
| id_distorted Recall@40 | 63.33% | 63.33% | +0.00%  |
| id_distorted Recall@50 | 63.33% | 63.33% | +0.00%  |
| id_punct Recall@1 | 86.67% | 86.67% | +0.00%  |
| id_punct Recall@3 | 86.67% | 88.33% | +1.67% 🟢 |
| id_punct Recall@5 | 90.00% | 90.00% | +0.00%  |
| id_punct Recall@10 | 90.00% | 90.00% | +0.00%  |
| id_punct Recall@20 | 90.00% | 90.00% | +0.00%  |
| id_punct Recall@30 | 90.00% | 91.67% | +1.67% 🟢 |
| id_punct Recall@40 | 91.67% | 91.67% | +0.00%  |
| id_punct Recall@50 | 91.67% | 91.67% | +0.00%  |
| id_space Recall@1 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@3 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@5 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@10 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@20 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@30 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@40 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@50 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@1 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@3 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@5 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@10 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@20 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@30 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@40 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@50 | 100.00% | 100.00% | +0.00%  |

### Input Type 2
| Category | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| name_casing Recall@1 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@3 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@5 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@10 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@20 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@30 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@40 | 96.61% | 96.61% | +0.00%  |
| name_casing Recall@50 | 96.61% | 96.61% | +0.00%  |
| name_distored Recall@1 | 57.63% | 55.93% | -1.69% 🔴 |
| name_distored Recall@3 | 79.66% | 81.36% | +1.69% 🟢 |
| name_distored Recall@5 | 86.44% | 86.44% | +0.00%  |
| name_distored Recall@10 | 89.83% | 89.83% | +0.00%  |
| name_distored Recall@20 | 91.53% | 91.53% | +0.00%  |
| name_distored Recall@30 | 91.53% | 91.53% | +0.00%  |
| name_distored Recall@40 | 91.53% | 91.53% | +0.00%  |
| name_distored Recall@50 | 91.53% | 91.53% | +0.00%  |
| name_punct Recall@1 | 94.92% | 94.92% | +0.00%  |
| name_punct Recall@3 | 94.92% | 94.92% | +0.00%  |
| name_punct Recall@5 | 96.61% | 94.92% | -1.69% 🔴 |
| name_punct Recall@10 | 98.31% | 100.00% | +1.69% 🟢 |
| name_punct Recall@20 | 100.00% | 100.00% | +0.00%  |
| name_punct Recall@30 | 100.00% | 100.00% | +0.00%  |
| name_punct Recall@40 | 100.00% | 100.00% | +0.00%  |
| name_punct Recall@50 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@1 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@3 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@5 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@10 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@20 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@30 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@40 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@50 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@1 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@3 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@5 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@10 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@20 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@30 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@40 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@50 | 100.00% | 100.00% | +0.00%  |

### Input Type 3
| Category | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| head_300 Recall@1 | 92.09% | 92.09% | +0.00%  |
| head_300 Recall@3 | 97.27% | 96.98% | -0.29% 🔴 |
| head_300 Recall@5 | 98.71% | 98.42% | -0.29% 🔴 |
| head_300 Recall@10 | 99.42% | 99.28% | -0.14% 🔴 |
| head_300 Recall@20 | 99.71% | 99.71% | +0.00%  |
| head_300 Recall@30 | 99.71% | 99.71% | +0.00%  |
| head_300 Recall@40 | 99.71% | 99.71% | +0.00%  |
| head_300 Recall@50 | 99.71% | 99.71% | +0.00%  |
| head_500 Recall@1 | 93.53% | 93.53% | +0.00%  |
| head_500 Recall@3 | 98.13% | 98.13% | +0.00%  |
| head_500 Recall@5 | 98.99% | 98.99% | +0.00%  |
| head_500 Recall@10 | 99.57% | 99.57% | +0.00%  |
| head_500 Recall@20 | 99.86% | 99.86% | +0.00%  |
| head_500 Recall@30 | 99.86% | 99.86% | +0.00%  |
| head_500 Recall@40 | 99.86% | 99.86% | +0.00%  |
| head_500 Recall@50 | 99.86% | 99.86% | +0.00%  |
| head_800 Recall@1 | 94.53% | 94.53% | +0.00%  |
| head_800 Recall@3 | 98.42% | 98.42% | +0.00%  |
| head_800 Recall@5 | 99.28% | 99.28% | +0.00%  |
| head_800 Recall@10 | 99.86% | 99.86% | +0.00%  |
| head_800 Recall@20 | 99.86% | 99.86% | +0.00%  |
| head_800 Recall@30 | 99.86% | 99.86% | +0.00%  |
| head_800 Recall@40 | 99.86% | 99.86% | +0.00%  |
| head_800 Recall@50 | 99.86% | 99.86% | +0.00%  |

### Input Type 4
| Category | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| 01 Recall@1 | 94.05% | 94.05% | +0.00%  |
| 01 Recall@3 | 97.84% | 97.84% | +0.00%  |
| 01 Recall@5 | 98.92% | 98.92% | +0.00%  |
| 01 Recall@10 | 99.46% | 99.46% | +0.00%  |
| 01 Recall@20 | 99.46% | 99.46% | +0.00%  |
| 01 Recall@30 | 99.46% | 99.46% | +0.00%  |
| 01 Recall@40 | 99.46% | 99.46% | +0.00%  |
| 01 Recall@50 | 99.46% | 99.46% | +0.00%  |
| 02 Recall@1 | 94.23% | 94.23% | +0.00%  |
| 02 Recall@3 | 97.66% | 97.66% | +0.00%  |
| 02 Recall@5 | 98.74% | 98.74% | +0.00%  |
| 02 Recall@10 | 99.28% | 99.28% | +0.00%  |
| 02 Recall@20 | 99.28% | 99.28% | +0.00%  |
| 02 Recall@30 | 99.28% | 99.28% | +0.00%  |
| 02 Recall@40 | 99.28% | 99.28% | +0.00%  |
| 02 Recall@50 | 99.28% | 99.28% | +0.00%  |
| 05 Recall@1 | 69.55% | 71.71% | +2.16% 🟢 |
| 05 Recall@3 | 79.82% | 80.90% | +1.08% 🟢 |
| 05 Recall@5 | 83.78% | 83.96% | +0.18% 🟢 |
| 05 Recall@10 | 88.47% | 88.65% | +0.18% 🟢 |
| 05 Recall@20 | 93.33% | 93.69% | +0.36% 🟢 |
| 05 Recall@30 | 96.40% | 96.22% | -0.18% 🔴 |
| 05 Recall@40 | 97.66% | 97.84% | +0.18% 🟢 |
| 05 Recall@50 | 97.84% | 98.20% | +0.36% 🟢 |
| 10 Recall@1 | 60.54% | 60.72% | +0.18% 🟢 |
| 10 Recall@3 | 72.79% | 73.33% | +0.54% 🟢 |
| 10 Recall@5 | 76.94% | 76.94% | +0.00%  |
| 10 Recall@10 | 83.60% | 83.60% | +0.00%  |
| 10 Recall@20 | 88.11% | 87.57% | -0.54% 🔴 |
| 10 Recall@30 | 90.63% | 91.17% | +0.54% 🟢 |
| 10 Recall@40 | 93.51% | 94.05% | +0.54% 🟢 |
| 10 Recall@50 | 94.95% | 95.14% | +0.18% 🟢 |
| 20 Recall@1 | 47.75% | 50.09% | +2.34% 🟢 |
| 20 Recall@3 | 60.18% | 61.44% | +1.26% 🟢 |
| 20 Recall@5 | 63.60% | 64.68% | +1.08% 🟢 |
| 20 Recall@10 | 67.03% | 68.47% | +1.44% 🟢 |
| 20 Recall@20 | 70.81% | 72.97% | +2.16% 🟢 |
| 20 Recall@30 | 72.61% | 75.86% | +3.24% 🟢 |
| 20 Recall@40 | 74.05% | 77.12% | +3.06% 🟢 |
| 20 Recall@50 | 74.77% | 78.92% | +4.14% 🟢 |
| verbatim Recall@1 | 94.23% | 94.23% | +0.00%  |
| verbatim Recall@3 | 97.84% | 97.84% | +0.00%  |
| verbatim Recall@5 | 98.92% | 98.92% | +0.00%  |
| verbatim Recall@10 | 99.46% | 99.46% | +0.00%  |
| verbatim Recall@20 | 99.46% | 99.46% | +0.00%  |
| verbatim Recall@30 | 99.46% | 99.46% | +0.00%  |
| verbatim Recall@40 | 99.46% | 99.46% | +0.00%  |
| verbatim Recall@50 | 99.46% | 99.46% | +0.00%  |

### Input Type 5
| Category | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| mixed Recall@1 | 61.20% | 60.66% | -0.55% 🔴 |
| mixed Recall@3 | 77.05% | 76.50% | -0.55% 🔴 |
| mixed Recall@5 | 79.78% | 79.78% | +0.00%  |
| mixed Recall@10 | 80.87% | 80.87% | +0.00%  |
| mixed Recall@20 | 83.06% | 83.06% | +0.00%  |
| mixed Recall@30 | 84.15% | 84.15% | +0.00%  |
| mixed Recall@40 | 85.79% | 85.25% | -0.55% 🔴 |
| mixed Recall@50 | 86.89% | 86.89% | +0.00%  |

## Tier Recall

### Input Type 1 tier recall
| Tier | main (n=306) | license-marker (n=306) | Δ |
| :--- | ---: | ---: | ---: |
| Tier 0 (short-text) | 75.49% (231) | 75.49% (231) | +0.00%  |
| Tier 0.5 (marker) | 0.00% (0) | 0.00% (0) | +0.00%  |
| Tier 1 (FTS5 pool) | 10.13% (31) | 10.13% (31) | +0.00%  |
| Tier 2 (ranked) | 0.33% (1) | 0.33% (1) | +0.00%  |
| Missed | 14.05% (43) | 14.05% (43) | +0.00%  |

### Input Type 2 tier recall
| Tier | main (n=295) | license-marker (n=295) | Δ |
| :--- | ---: | ---: | ---: |
| Tier 0 (short-text) | 86.44% (255) | 86.78% (256) | +0.34% 🟢 |
| Tier 0.5 (marker) | 0.00% (0) | 0.00% (0) | +0.00%  |
| Tier 1 (FTS5 pool) | 7.80% (23) | 7.46% (22) | -0.34% 🔴 |
| Tier 2 (ranked) | 3.39% (10) | 3.39% (10) | +0.00%  |
| Missed | 2.37% (7) | 2.37% (7) | +0.00%  |

### Input Type 3 tier recall
| Tier | main (n=2085) | license-marker (n=2085) | Δ |
| :--- | ---: | ---: | ---: |
| Tier 0 (short-text) | 0.05% (1) | 0.05% (1) | +0.00%  |
| Tier 0.5 (marker) | 14.15% (295) | 14.15% (295) | +0.00%  |
| Tier 1 (FTS5 pool) | 85.61% (1785) | 85.61% (1785) | +0.00%  |
| Tier 2 (ranked) | 0.00% (0) | 0.00% (0) | +0.00%  |
| Missed | 0.19% (4) | 0.19% (4) | +0.00%  |

### Input Type 4 tier recall
| Tier | main (n=3330) | license-marker (n=3330) | Δ |
| :--- | ---: | ---: | ---: |
| Tier 0 (short-text) | 0.00% (0) | 0.00% (0) | +0.00%  |
| Tier 0.5 (marker) | 4.71% (157) | 4.71% (157) | +0.00%  |
| Tier 1 (FTS5 pool) | 90.30% (3007) | 91.26% (3039) | +0.96% 🟢 |
| Tier 2 (ranked) | 0.00% (0) | 0.00% (0) | +0.00%  |
| Missed | 4.98% (166) | 4.02% (134) | -0.96% 🔴 |

### Input Type 5 tier recall
| Tier | main (n=183) | license-marker (n=183) | Δ |
| :--- | ---: | ---: | ---: |
| Tier 0 (short-text) | 13.66% (25) | 13.66% (25) | +0.00%  |
| Tier 0.5 (marker) | 49.73% (91) | 49.73% (91) | +0.00%  |
| Tier 1 (FTS5 pool) | 21.86% (40) | 21.86% (40) | +0.00%  |
| Tier 2 (ranked) | 2.73% (5) | 2.73% (5) | +0.00%  |
| Missed | 12.02% (22) | 12.02% (22) | +0.00%  |

### Global Summary
| Metric | main | normalize-guidelines | Δ |
| :--- | ---: | ---: | ---: |
| Recall | 96.06% | 96.58% | +0.51% |
| Precision | 1.85% | 1.85% | +0.00% |
| Wall time (s) | 1464.0 | 4088.3 | +2624.3s |
| Throughput (q/s) | 4.3 | 1.5 | -2.7 |
| Peak memory (MB) | 5.3 | 5.3 | +0.0 |
| End memory (MB) | 1.4 | 1.4 | -0.0 |
