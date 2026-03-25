# Paper Tables Summary

## Notes
- Source column `total_interruption_ms` is stored in milliseconds.
- All paper tables and figures report `mean_total_interruption_s`, which is `total_interruption_ms / 1000` converted to seconds.
- Therefore, `162.37` in Table 1 means `162.37 s`, which corresponds to `162,366.26 ms` in the source CSV.
- The source flight-level CSV does not contain `service_handover_count`; this report uses `handover_count` as an alias for that concept.
- `handover_failure_rate_pct` is computed as `radio_handover_failures / handover_count × 100` at flight level and `sum(radio_handover_failures) / sum(handover_attempts) × 100` at run/policy summary level.
- The latency violation summary is split into Table 3 (descriptive statistics) and Table 4 (Mann-Whitney U test result) to avoid structurally empty cells in the manuscript.

## Table 1. Overall policy comparison
| policy    | mean_total_handovers | mean_ping_pong_events | mean_total_interruption_s | mean_service_success_rate_pct | mean_throughput_mbps | mean_sinr_db | handover_attempts | radio_handover_failures | handover_failure_rate_pct |
| --------- | -------------------- | --------------------- | ------------------------- | ----------------------------- | -------------------- | ------------ | ----------------- | ----------------------- | ------------------------- |
| reactive  | 1461.46              | 917.49                | 162.37                    | 0.00                          | 10.81                | 5.19         | 157838            | 0                       | 0.00                      |
| proactive | 472.72               | 137.02                | 16.12                     | 3.86                          | 10.20                | 4.27         | 51054             | 552                     | 1.08                      |

## Table 2. Phase-wise policy comparison
| phase        | policy    | mean_total_handovers | mean_ping_pong_events | mean_total_interruption_s | mean_service_success_rate_pct | mean_throughput_mbps | mean_sinr_db |
| ------------ | --------- | -------------------- | --------------------- | ------------------------- | ----------------------------- | -------------------- | ------------ |
| introduction | reactive  | 1118.36              | 773.00                | 122.23                    | 0.00                          | 10.25                | 4.39         |
| introduction | proactive | 334.19               | 113.61                | 11.42                     | 3.62                          | 9.69                 | 3.54         |
| growth       | reactive  | 1451.28              | 930.64                | 158.31                    | 0.00                          | 11.12                | 5.88         |
| growth       | proactive | 467.19               | 150.81                | 15.82                     | 4.58                          | 10.48                | 4.95         |
| maturity     | reactive  | 1814.75              | 1048.83               | 206.56                    | 0.00                          | 11.07                | 5.31         |
| maturity     | proactive | 616.78               | 146.64                | 21.11                     | 3.37                          | 10.44                | 4.31         |

## Table 3. Latency violation descriptive statistics
| policy    | mean     | median   | std      | min     | max       | count     |
| --------- | -------- | -------- | -------- | ------- | --------- | --------- |
| proactive | 529.4289 | 443.5000 | 314.8528 | 59.0000 | 1807.0000 | 3348.0000 |
| reactive  | 558.4238 | 468.5000 | 331.9167 | 68.0000 | 1950.0000 | 3348.0000 |

## Table 4. Latency violation Mann-Whitney U test
| comparison_target     | test_name        | u_statistic  | mann_whitney_p_value | rank_biserial_effect_size | total_n |
| --------------------- | ---------------- | ------------ | -------------------- | ------------------------- | ------- |
| proactive_vs_reactive | two_sided_u_test | 5310434.5000 | 0.0002               | -0.0525                   | 6696    |

## Table 5. Top routes with proactive interruption reduction
| origin     | destination | flight_count | mean_handovers_reactive | mean_handovers_proactive | handover_reduction_pct | mean_interruption_ms_reactive | mean_interruption_ms_proactive | interruption_reduction_pct | mean_latency_violations_reactive | mean_latency_violations_proactive | latency_violation_reduction_pct |
| ---------- | ----------- | ------------ | ----------------------- | ------------------------ | ---------------------- | ----------------------------- | ------------------------------ | -------------------------- | -------------------------------- | --------------------------------- | ------------------------------- |
| GimpoHub   | Ansan       | 18           | 44.83                   | 8.83                     | 80.30                  | 5185.69                       | 309.17                         | 94.04                      | 493.83                           | 460.56                            | 6.74                            |
| Hanam      | Pangyo      | 18           | 29.83                   | 5.83                     | 80.45                  | 3126.30                       | 204.17                         | 93.47                      | 353.39                           | 330.72                            | 6.41                            |
| GimpoHub   | GimpoCity   | 36           | 9.33                    | 2.22                     | 76.19                  | 1118.36                       | 73.94                          | 93.39                      | 116.25                           | 111.11                            | 4.42                            |
| Ansan      | GimpoHub    | 18           | 38.06                   | 8.33                     | 78.10                  | 4331.07                       | 291.67                         | 93.27                      | 487.56                           | 465.33                            | 4.56                            |
| GimpoCity  | Yeouido     | 18           | 35.33                   | 9.56                     | 72.96                  | 4181.27                       | 302.50                         | 92.77                      | 444.50                           | 422.67                            | 4.91                            |
| IncheonHub | GimpoHub    | 576          | 26.22                   | 7.11                     | 72.87                  | 3153.81                       | 243.52                         | 92.28                      | 270.96                           | 251.51                            | 7.18                            |
| Hanam      | Suwon       | 18           | 49.89                   | 12.50                    | 74.94                  | 5490.50                       | 437.50                         | 92.03                      | 681.28                           | 644.94                            | 5.33                            |
| IncheonHub | Yongin      | 36           | 131.03                  | 35.83                    | 72.65                  | 15234.58                      | 1234.36                        | 91.90                      | 1394.42                          | 1310.06                           | 6.05                            |
| GimpoHub   | Bucheon     | 18           | 26.33                   | 7.67                     | 70.89                  | 3182.23                       | 258.11                         | 91.89                      | 190.67                           | 176.94                            | 7.20                            |
| Anyang     | Hanam       | 36           | 69.44                   | 18.53                    | 73.32                  | 7728.00                       | 636.33                         | 91.77                      | 766.64                           | 718.11                            | 6.33                            |
