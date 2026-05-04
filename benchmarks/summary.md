# Benchmark Comparison: `main` vs `license-marker`

**Date:** 20260504T092122Z

## Metrics

### Input Type 1

| Category | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| id_casing Recall@1 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@3 | 80.00% | 80.00% | +0.00%  |
| id_casing Recall@5 | 80.00% | 80.00% | +0.00%  |
| id_deprecated Recall@1 | 0.00% | 0.00% | +0.00%  |
| id_deprecated Recall@3 | 0.00% | 16.67% | +16.67% 🟢 |
| id_deprecated Recall@5 | 0.00% | 16.67% | +16.67% 🟢 |
| id_distorted Recall@1 | 33.33% | 35.00% | +1.67% 🟢 |
| id_distorted Recall@3 | 50.00% | 53.33% | +3.33% 🟢 |
| id_distorted Recall@5 | 53.33% | 56.67% | +3.33% 🟢 |
| id_punct Recall@1 | 86.67% | 86.67% | +0.00%  |
| id_punct Recall@3 | 88.33% | 88.33% | +0.00%  |
| id_punct Recall@5 | 90.00% | 90.00% | +0.00%  |
| id_space Recall@1 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@3 | 100.00% | 100.00% | +0.00%  |
| id_space Recall@5 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@1 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@3 | 100.00% | 100.00% | +0.00%  |
| id_verbatim Recall@5 | 100.00% | 100.00% | +0.00%  |

### Input Type 2

| Category | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| name_casing Recall@1 | 79.66% | 96.61% | +16.95% 🟢 |
| name_casing Recall@3 | 79.66% | 96.61% | +16.95% 🟢 |
| name_casing Recall@5 | 79.66% | 96.61% | +16.95% 🟢 |
| name_distored Recall@1 | 61.02% | 61.02% | +0.00%  |
| name_distored Recall@3 | 79.66% | 83.05% | +3.39% 🟢 |
| name_distored Recall@5 | 86.44% | 84.75% | -1.69% 🔴 |
| name_punct Recall@1 | 94.92% | 94.92% | +0.00%  |
| name_punct Recall@3 | 94.92% | 94.92% | +0.00%  |
| name_punct Recall@5 | 96.61% | 96.61% | +0.00%  |
| name_space Recall@1 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@3 | 100.00% | 100.00% | +0.00%  |
| name_space Recall@5 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@1 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@3 | 100.00% | 100.00% | +0.00%  |
| name_verbatim Recall@5 | 100.00% | 100.00% | +0.00%  |

### Input Type 3

| Category | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| license_text_short_head_1000 Recall@1 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_1000 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_1000 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_1000_tail_1000 Recall@1 | 61.67% | 63.33% | +1.67% 🟢 |
| license_text_short_head_1000_tail_1000 Recall@3 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_head_1000_tail_1000 Recall@5 | 81.67% | 80.00% | -1.67% 🔴 |
| license_text_short_head_1000_tail_1500 Recall@1 | 68.33% | 70.00% | +1.67% 🟢 |
| license_text_short_head_1000_tail_1500 Recall@3 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_head_1000_tail_1500 Recall@5 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_1000_tail_2000 Recall@1 | 70.00% | 71.67% | +1.67% 🟢 |
| license_text_short_head_1000_tail_2000 Recall@3 | 75.00% | 78.33% | +3.33% 🟢 |
| license_text_short_head_1000_tail_2000 Recall@5 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_head_1000_tail_300 Recall@1 | 75.00% | 73.33% | -1.67% 🔴 |
| license_text_short_head_1000_tail_300 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_1000_tail_300 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_1000_tail_500 Recall@1 | 71.67% | 71.67% | +0.00%  |
| license_text_short_head_1000_tail_500 Recall@3 | 85.00% | 90.00% | +5.00% 🟢 |
| license_text_short_head_1000_tail_500 Recall@5 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_1000_tail_700 Recall@1 | 66.67% | 68.33% | +1.67% 🟢 |
| license_text_short_head_1000_tail_700 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_1000_tail_700 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_1500 Recall@1 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_1500 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_1500 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_1500_tail_1000 Recall@1 | 65.00% | 68.33% | +3.33% 🟢 |
| license_text_short_head_1500_tail_1000 Recall@3 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_head_1500_tail_1000 Recall@5 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_1500_tail_1500 Recall@1 | 58.33% | 61.67% | +3.33% 🟢 |
| license_text_short_head_1500_tail_1500 Recall@3 | 66.67% | 70.00% | +3.33% 🟢 |
| license_text_short_head_1500_tail_1500 Recall@5 | 68.33% | 71.67% | +3.33% 🟢 |
| license_text_short_head_1500_tail_300 Recall@1 | 61.67% | 61.67% | +0.00%  |
| license_text_short_head_1500_tail_300 Recall@3 | 71.67% | 75.00% | +3.33% 🟢 |
| license_text_short_head_1500_tail_300 Recall@5 | 75.00% | 81.67% | +6.67% 🟢 |
| license_text_short_head_1500_tail_500 Recall@1 | 68.33% | 70.00% | +1.67% 🟢 |
| license_text_short_head_1500_tail_500 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_1500_tail_500 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_1500_tail_700 Recall@1 | 65.00% | 70.00% | +5.00% 🟢 |
| license_text_short_head_1500_tail_700 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_1500_tail_700 Recall@5 | 86.67% | 88.33% | +1.67% 🟢 |
| license_text_short_head_2000 Recall@1 | 80.00% | 80.00% | +0.00%  |
| license_text_short_head_2000 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_2000 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_2000_tail_1000 Recall@1 | 66.67% | 73.33% | +6.67% 🟢 |
| license_text_short_head_2000_tail_1000 Recall@3 | 76.67% | 80.00% | +3.33% 🟢 |
| license_text_short_head_2000_tail_1000 Recall@5 | 78.33% | 81.67% | +3.33% 🟢 |
| license_text_short_head_2000_tail_300 Recall@1 | 65.00% | 66.67% | +1.67% 🟢 |
| license_text_short_head_2000_tail_300 Recall@3 | 70.00% | 71.67% | +1.67% 🟢 |
| license_text_short_head_2000_tail_300 Recall@5 | 76.67% | 80.00% | +3.33% 🟢 |
| license_text_short_head_2000_tail_500 Recall@1 | 75.00% | 76.67% | +1.67% 🟢 |
| license_text_short_head_2000_tail_500 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_2000_tail_500 Recall@5 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_2000_tail_700 Recall@1 | 75.00% | 76.67% | +1.67% 🟢 |
| license_text_short_head_2000_tail_700 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_2000_tail_700 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_2300_tail_700 Recall@1 | 73.33% | 75.00% | +1.67% 🟢 |
| license_text_short_head_2300_tail_700 Recall@3 | 78.33% | 81.67% | +3.33% 🟢 |
| license_text_short_head_2300_tail_700 Recall@5 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_2500_tail_500 Recall@1 | 56.67% | 60.00% | +3.33% 🟢 |
| license_text_short_head_2500_tail_500 Recall@3 | 71.67% | 73.33% | +1.67% 🟢 |
| license_text_short_head_2500_tail_500 Recall@5 | 73.33% | 75.00% | +1.67% 🟢 |
| license_text_short_head_2700_tail_300 Recall@1 | 70.00% | 73.33% | +3.33% 🟢 |
| license_text_short_head_2700_tail_300 Recall@3 | 75.00% | 78.33% | +3.33% 🟢 |
| license_text_short_head_2700_tail_300 Recall@5 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_head_300 Recall@1 | 76.67% | 76.67% | +0.00%  |
| license_text_short_head_300 Recall@3 | 85.00% | 86.67% | +1.67% 🟢 |
| license_text_short_head_300 Recall@5 | 88.33% | 88.33% | +0.00%  |
| license_text_short_head_3000 Recall@1 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_head_3000 Recall@3 | 78.33% | 81.67% | +3.33% 🟢 |
| license_text_short_head_3000 Recall@5 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_300_tail_1000 Recall@1 | 73.33% | 73.33% | +0.00%  |
| license_text_short_head_300_tail_1000 Recall@3 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_300_tail_1000 Recall@5 | 83.33% | 83.33% | +0.00%  |
| license_text_short_head_300_tail_1500 Recall@1 | 68.33% | 70.00% | +1.67% 🟢 |
| license_text_short_head_300_tail_1500 Recall@3 | 81.67% | 81.67% | +0.00%  |
| license_text_short_head_300_tail_1500 Recall@5 | 83.33% | 83.33% | +0.00%  |
| license_text_short_head_300_tail_2000 Recall@1 | 65.00% | 65.00% | +0.00%  |
| license_text_short_head_300_tail_2000 Recall@3 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_head_300_tail_2000 Recall@5 | 83.33% | 83.33% | +0.00%  |
| license_text_short_head_300_tail_300 Recall@1 | 51.67% | 53.33% | +1.67% 🟢 |
| license_text_short_head_300_tail_300 Recall@3 | 75.00% | 76.67% | +1.67% 🟢 |
| license_text_short_head_300_tail_300 Recall@5 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_head_300_tail_500 Recall@1 | 66.67% | 66.67% | +0.00%  |
| license_text_short_head_300_tail_500 Recall@3 | 83.33% | 83.33% | +0.00%  |
| license_text_short_head_300_tail_500 Recall@5 | 83.33% | 83.33% | +0.00%  |
| license_text_short_head_300_tail_700 Recall@1 | 68.33% | 68.33% | +0.00%  |
| license_text_short_head_300_tail_700 Recall@3 | 80.00% | 80.00% | +0.00%  |
| license_text_short_head_300_tail_700 Recall@5 | 81.67% | 81.67% | +0.00%  |
| license_text_short_head_500 Recall@1 | 78.33% | 80.00% | +1.67% 🟢 |
| license_text_short_head_500 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_500 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_500_tail_1000 Recall@1 | 71.67% | 75.00% | +3.33% 🟢 |
| license_text_short_head_500_tail_1000 Recall@3 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_500_tail_1000 Recall@5 | 81.67% | 85.00% | +3.33% 🟢 |
| license_text_short_head_500_tail_1500 Recall@1 | 71.67% | 71.67% | +0.00%  |
| license_text_short_head_500_tail_1500 Recall@3 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_500_tail_1500 Recall@5 | 85.00% | 86.67% | +1.67% 🟢 |
| license_text_short_head_500_tail_2000 Recall@1 | 73.33% | 75.00% | +1.67% 🟢 |
| license_text_short_head_500_tail_2000 Recall@3 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_500_tail_2000 Recall@5 | 85.00% | 86.67% | +1.67% 🟢 |
| license_text_short_head_500_tail_300 Recall@1 | 68.33% | 70.00% | +1.67% 🟢 |
| license_text_short_head_500_tail_300 Recall@3 | 86.67% | 90.00% | +3.33% 🟢 |
| license_text_short_head_500_tail_300 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_500_tail_500 Recall@1 | 53.33% | 50.00% | -3.33% 🔴 |
| license_text_short_head_500_tail_500 Recall@3 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_head_500_tail_500 Recall@5 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_head_500_tail_700 Recall@1 | 70.00% | 70.00% | +0.00%  |
| license_text_short_head_500_tail_700 Recall@3 | 81.67% | 83.33% | +1.67% 🟢 |
| license_text_short_head_500_tail_700 Recall@5 | 83.33% | 85.00% | +1.67% 🟢 |
| license_text_short_head_700 Recall@1 | 78.33% | 80.00% | +1.67% 🟢 |
| license_text_short_head_700 Recall@3 | 85.00% | 88.33% | +3.33% 🟢 |
| license_text_short_head_700 Recall@5 | 88.33% | 90.00% | +1.67% 🟢 |
| license_text_short_head_700_tail_1000 Recall@1 | 70.00% | 73.33% | +3.33% 🟢 |
| license_text_short_head_700_tail_1000 Recall@3 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_head_700_tail_1000 Recall@5 | 83.33% | 85.00% | +1.67% 🟢 |
| license_text_short_head_700_tail_1500 Recall@1 | 70.00% | 71.67% | +1.67% 🟢 |
| license_text_short_head_700_tail_1500 Recall@3 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_700_tail_1500 Recall@5 | 85.00% | 86.67% | +1.67% 🟢 |
| license_text_short_head_700_tail_2000 Recall@1 | 73.33% | 75.00% | +1.67% 🟢 |
| license_text_short_head_700_tail_2000 Recall@3 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_700_tail_2000 Recall@5 | 85.00% | 86.67% | +1.67% 🟢 |
| license_text_short_head_700_tail_300 Recall@1 | 68.33% | 66.67% | -1.67% 🔴 |
| license_text_short_head_700_tail_300 Recall@3 | 81.67% | 86.67% | +5.00% 🟢 |
| license_text_short_head_700_tail_300 Recall@5 | 86.67% | 88.33% | +1.67% 🟢 |
| license_text_short_head_700_tail_500 Recall@1 | 63.33% | 63.33% | +0.00%  |
| license_text_short_head_700_tail_500 Recall@3 | 83.33% | 86.67% | +3.33% 🟢 |
| license_text_short_head_700_tail_500 Recall@5 | 86.67% | 88.33% | +1.67% 🟢 |
| license_text_short_head_700_tail_700 Recall@1 | 50.00% | 53.33% | +3.33% 🟢 |
| license_text_short_head_700_tail_700 Recall@3 | 75.00% | 78.33% | +3.33% 🟢 |
| license_text_short_head_700_tail_700 Recall@5 | 80.00% | 83.33% | +3.33% 🟢 |
| license_text_short_tail_1000 Recall@1 | 71.67% | 73.33% | +1.67% 🟢 |
| license_text_short_tail_1000 Recall@3 | 80.00% | 80.00% | +0.00%  |
| license_text_short_tail_1000 Recall@5 | 80.00% | 80.00% | +0.00%  |
| license_text_short_tail_1500 Recall@1 | 66.67% | 68.33% | +1.67% 🟢 |
| license_text_short_tail_1500 Recall@3 | 73.33% | 75.00% | +1.67% 🟢 |
| license_text_short_tail_1500 Recall@5 | 75.00% | 75.00% | +0.00%  |
| license_text_short_tail_2000 Recall@1 | 75.00% | 73.33% | -1.67% 🔴 |
| license_text_short_tail_2000 Recall@3 | 83.33% | 85.00% | +1.67% 🟢 |
| license_text_short_tail_2000 Recall@5 | 85.00% | 85.00% | +0.00%  |
| license_text_short_tail_300 Recall@1 | 53.33% | 53.33% | +0.00%  |
| license_text_short_tail_300 Recall@3 | 65.00% | 66.67% | +1.67% 🟢 |
| license_text_short_tail_300 Recall@5 | 66.67% | 66.67% | +0.00%  |
| license_text_short_tail_3000 Recall@1 | 76.67% | 78.33% | +1.67% 🟢 |
| license_text_short_tail_3000 Recall@3 | 78.33% | 81.67% | +3.33% 🟢 |
| license_text_short_tail_3000 Recall@5 | 80.00% | 81.67% | +1.67% 🟢 |
| license_text_short_tail_500 Recall@1 | 58.33% | 58.33% | +0.00%  |
| license_text_short_tail_500 Recall@3 | 70.00% | 71.67% | +1.67% 🟢 |
| license_text_short_tail_500 Recall@5 | 71.67% | 71.67% | +0.00%  |
| license_text_short_tail_700 Recall@1 | 61.67% | 61.67% | +0.00%  |
| license_text_short_tail_700 Recall@3 | 75.00% | 75.00% | +0.00%  |
| license_text_short_tail_700 Recall@5 | 75.00% | 75.00% | +0.00%  |

### Input Type 4

| Category | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| 01 Recall@1 | 93.15% | 93.15% | +0.00%  |
| 01 Recall@3 | 96.58% | 96.76% | +0.18% 🟢 |
| 01 Recall@5 | 97.66% | 97.84% | +0.18% 🟢 |
| 02 Recall@1 | 93.33% | 93.51% | +0.18% 🟢 |
| 02 Recall@3 | 96.76% | 96.76% | +0.00%  |
| 02 Recall@5 | 97.84% | 97.84% | +0.00%  |
| 05 Recall@1 | 72.25% | 70.63% | -1.62% 🔴 |
| 05 Recall@3 | 81.26% | 80.90% | -0.36% 🔴 |
| 05 Recall@5 | 84.68% | 84.86% | +0.18% 🟢 |
| 10 Recall@1 | 59.10% | 59.28% | +0.18% 🟢 |
| 10 Recall@3 | 72.25% | 72.61% | +0.36% 🟢 |
| 10 Recall@5 | 75.32% | 75.86% | +0.54% 🟢 |
| 20 Recall@1 | 45.41% | 43.96% | -1.44% 🔴 |
| 20 Recall@3 | 55.14% | 55.14% | +0.00%  |
| 20 Recall@5 | 57.12% | 58.02% | +0.90% 🟢 |
| verbatim Recall@1 | 93.33% | 93.69% | +0.36% 🟢 |
| verbatim Recall@3 | 96.76% | 97.12% | +0.36% 🟢 |
| verbatim Recall@5 | 97.84% | 98.20% | +0.36% 🟢 |

### Input Type 5

| Category | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| mixed Recall@1 | 20.22% | 66.12% | +45.90% 🟢 |
| mixed Recall@3 | 24.59% | 68.85% | +44.26% 🟢 |
| mixed Recall@5 | 27.32% | 69.95% | +42.62% 🟢 |

### Global Summary

| Metric | main | license-marker | Δ |
| :--- | ---: | ---: | ---: |
| Recall | 88.53% | 90.36% | +1.83% |
| Precision | 1.92% | 1.94% | +0.02% |
| Wall time (s) | 9775.4 | 9805.2 | +29.7s |
| Throughput (q/s) | 0.7 | 0.7 | -0.0 |
| Peak memory (MB) | 3.9 | 6.0 | +2.1 |
| End memory (MB) | 1.1 | 1.2 | +0.1 |
