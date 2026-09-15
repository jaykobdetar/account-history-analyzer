# Pilot 6: bounded shared-anchor replication

9 new account-disjoint pairs supplied 36 planned main histories and 36 replay slots. The target was 10 pairs; the pre-score shortfall is 1. 36 main histories executed and 0 are unavailable. 9 pairs have all four canonical replays verified.

Each pair is one replication unit. Its four histories share the same earlier sample; replays add no new units. Source accounts are identity proxies, and distinct accounts need not represent distinct people. Pilot 5 is excluded from new-pair counts. These are descriptive results, with no population accuracy, verified-authorship, or real-takeover claim.

The frozen primary is AHAS 1.0.4 pooled-comment surface/function-word chronology, 1,000-word/eight-record windows, minimum segment length three, and the primary log(N) penalty. The constructed junction is never snapped to the grid; tolerance is inclusive at ten records. Ten records has no fixed calendar-time width; UTC brackets describe the actual spacing.

## Complete result files

[cases.json](cases.json) and [summary.json](summary.json) are byte-identical copies of the independently checked safe global outputs. [pair-availability.json](pair-availability.json) retains every provisional pair, including unscored failures and eligible pairs outside the fixed cohort. [condition-summary.json](condition-summary.json), [pair-ledgers.json](pair-ledgers.json), and [operating-costs.json](operating-costs.json) provide derived counts and costs. Input and output hashes are in [REPORT_MANIFEST.json](REPORT_MANIFEST.json).

## Per-condition denominators

Candidate, zero-candidate, and unavailable categories retain every planned slot. Localization fractions below use executed histories; the planned and unavailable denominators remain visible. For controls, localization means descriptive construction-junction alignment, not positive switch truth.

| Condition | Planned / executed / unavailable | Candidate / executed zero | Native no variation | Within 10 / executed | Exact / executed | Grid attainable / known |
|---|---:|---:|---:|---:|---:|---:|
| Continuity / same community | 9 / 9 / 0 | 0 / 9 | 0 | 0 / 9 | 0 / 9 | 9 / 9 |
| Source switch / same community | 9 / 9 / 0 | 6 / 3 | 0 | 6 / 9 | 0 / 9 | 9 / 9 |
| Continuity / changed community | 9 / 9 / 0 | 0 / 9 | 0 | 0 / 9 | 0 / 9 | 9 / 9 |
| Both switches | 9 / 9 / 0 | 5 / 4 | 0 | 4 / 9 | 0 / 9 | 9 / 9 |

## Preparation, protection and source coverage

The fixed search evaluated 505 community-pair/calendar cuts and found 76 valid unordered account-pair edges. The maximum matching contained 32 pairs; its fixed first 20 entered auditing. 11 provisional pairs were unavailable after auditing and the unchanged final gates.

The combined pool contained 8,867 original comments. Auditing purged 857, leaving 8,010. The broad candidate-pair count was 595,963, within the fixed 2,000,000 ceiling. 17 historical records remained unobservable; unknown content relationships are not treated as absent.

The selected cohort contains 18 source accounts, 2,531 distinct original comments and 228,387 retained words. 2 selected accounts had prior unscored preparation/audit exposure (1 from Pilot 3 and 1 from Pilot 4); 16 appeared only in prior eligibility metadata. Newly supplemented accounts in the final cohort: 0.

| Registered community pair | Selected replication pairs |
|---|---:|
| AskAcademia / GradSchool | 2 |
| AskPhysics / Physics | 0 |
| math / learnmath | 3 |
| linux / linuxquestions | 2 |
| programming / learnprogramming | 2 |

All preparation failure reasons and exposure counts are preserved in [study-context.json](study-context.json). Reason counts are nonexclusive; zero selected pairs remain visible. English remains a corpus-level assumption.


Successful native `no_measurable_variation` is executed zero-candidate behavior. Unavailable results retain null measurements; a missing nearest distance is not zero. Metadata grid/time resolution is separate from observed localization. The frozen `matched_candidate_count` is a one-truth 0/1 match indicator, not a count of every interval within tolerance.

## All provisional pairs

| Pair | Stratum | Direction | Cut | Selection status | Reasons |
|---|---|---|---|---|---|
| pilot6-pair-01 | stratum-05 | programming → learnprogramming | 2018-04-01T00:00:00Z | unavailable_after_audit | five_sample_record_ratio_above_5_over_4, four_late_median_span_above_30_days |
| pilot6-pair-02 | stratum-05 | learnprogramming → programming | 2013-01-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-03 | stratum-02 | Physics → AskPhysics | 2017-10-01T00:00:00Z | unavailable_after_audit | five_sample_record_ratio_above_5_over_4, four_late_median_span_above_30_days |
| pilot6-pair-04 | stratum-03 | learnmath → math | 2013-03-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-05 | stratum-03 | learnmath → math | 2018-02-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-06 | stratum-05 | programming → learnprogramming | 2017-10-01T00:00:00Z | unavailable_after_audit | four_late_median_span_above_30_days |
| pilot6-pair-07 | stratum-01 | AskAcademia → GradSchool | 2015-05-01T00:00:00Z | unavailable_after_audit | unavailable_sample:late_BY |
| pilot6-pair-08 | stratum-04 | linuxquestions → linux | 2017-10-01T00:00:00Z | unavailable_after_audit | unavailable_sample:late_AX |
| pilot6-pair-09 | stratum-04 | linux → linuxquestions | 2013-11-01T00:00:00Z | unavailable_after_audit | five_sample_record_ratio_above_5_over_4 |
| pilot6-pair-10 | stratum-01 | GradSchool → AskAcademia | 2016-12-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-11 | stratum-01 | GradSchool → AskAcademia | 2014-12-01T00:00:00Z | unavailable_after_audit | unavailable_sample:late_AX, unavailable_sample:late_AY |
| pilot6-pair-12 | stratum-05 | learnprogramming → programming | 2011-11-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-13 | stratum-03 | math → learnmath | 2017-01-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-14 | stratum-04 | linux → linuxquestions | 2015-07-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-15 | stratum-03 | math → learnmath | 2018-03-01T00:00:00Z | unavailable_after_audit | five_sample_record_ratio_above_5_over_4 |
| pilot6-pair-16 | stratum-02 | AskPhysics → Physics | 2017-11-01T00:00:00Z | unavailable_after_audit | unavailable_sample:late_BX, unavailable_sample:late_BY |
| pilot6-pair-17 | stratum-04 | linuxquestions → linux | 2018-02-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-18 | stratum-01 | GradSchool → AskAcademia | 2016-12-01T00:00:00Z | selected_for_replication | none |
| pilot6-pair-19 | stratum-04 | linux → linuxquestions | 2014-10-01T00:00:00Z | unavailable_after_audit | five_sample_record_ratio_above_5_over_4 |
| pilot6-pair-20 | stratum-03 | math → learnmath | 2018-03-01T00:00:00Z | unavailable_after_audit | unavailable_sample:late_BX |

## pilot6-pair-02

stratum-05: learnprogramming → programming; fixed cut 2013-01-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 8 |
| Source switch / same community | yes / ok | 1; [54, 54] → 2 | 2 / 2 / 0 | yes / no | 8 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 8 |
| Both switches | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 8 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 37.450 s; 305.523 MiB; 62,998,249 bytes | attempted; exit 0; 38.206 s; 306.039 MiB; 62,998,287 bytes | yes |
| Source switch / same community | attempted; exit 0; 40.862 s; 324.977 MiB; 69,014,199 bytes | attempted; exit 0; 41.363 s; 326.152 MiB; 69,014,238 bytes | yes |
| Continuity / changed community | attempted; exit 0; 35.699 s; 293.996 MiB; 59,024,860 bytes | attempted; exit 0; 35.547 s; 294.152 MiB; 59,024,899 bytes | yes |
| Both switches | attempted; exit 0; 36.199 s; 296.539 MiB; 60,054,254 bytes | attempted; exit 0; 35.698 s; 296.789 MiB; 60,054,291 bytes | yes |

**Continuity / same community:** 114 records / 10104 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=56: 2012-12-27T16:17:33Z → 2013-01-06T04:44:08Z (822395.000 s). Nearest legal boundary: 2012-12-26T20:10:09Z → 2012-12-26T20:19:08Z (539.000 s); within-ten attainment yes. Supplied time span: 2012-12-02T11:14:33Z → 2013-02-25T10:46:35Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 115 records / 10110 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=56: 2012-12-27T16:17:33Z → 2013-01-13T07:19:07Z (1436494.000 s). Nearest legal boundary: 2012-12-26T20:10:09Z → 2012-12-26T20:19:08Z (539.000 s); within-ten attainment yes. Supplied time span: 2012-12-02T11:14:33Z → 2013-02-08T23:03:19Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 118 records / 10175 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=56: 2012-12-27T16:17:33Z → 2013-01-01T09:49:43Z (408730.000 s). Nearest legal boundary: 2012-12-26T20:10:09Z → 2012-12-26T20:19:08Z (539.000 s); within-ten attainment yes. Supplied time span: 2012-12-02T11:14:33Z → 2013-01-27T22:36:39Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 115 records / 10123 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=56: 2012-12-27T16:17:33Z → 2013-01-04T20:13:06Z (705333.000 s). Nearest legal boundary: 2012-12-26T20:10:09Z → 2012-12-26T20:19:08Z (539.000 s); within-ten attainment yes. Supplied time span: 2012-12-02T11:14:33Z → 2013-02-23T23:18:37Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-04

stratum-03: learnmath → math; fixed cut 2013-03-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 9 |
| Both switches | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 41.712 s; 323.723 MiB; 68,551,107 bytes | attempted; exit 0; 41.170 s; 324.781 MiB; 68,551,144 bytes | yes |
| Source switch / same community | attempted; exit 0; 41.062 s; 321.555 MiB; 67,643,543 bytes | attempted; exit 0; 40.967 s; 322.914 MiB; 67,643,581 bytes | yes |
| Continuity / changed community | attempted; exit 0; 36.852 s; 301.527 MiB; 60,958,435 bytes | attempted; exit 0; 36.760 s; 300.945 MiB; 60,958,473 bytes | yes |
| Both switches | attempted; exit 0; 35.949 s; 297.473 MiB; 59,791,234 bytes | attempted; exit 0; 35.455 s; 297.504 MiB; 59,791,272 bytes | yes |

**Continuity / same community:** 112 records / 10058 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=58: 2013-02-28T22:27:54Z → 2013-03-03T00:06:14Z (178700.000 s). Nearest legal boundary: 2013-03-05T19:42:49Z → 2013-03-05T23:47:35Z (14686.000 s); within-ten attainment yes. Supplied time span: 2012-12-26T03:33:49Z → 2013-04-03T21:10:33Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 111 records / 10169 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=58: 2013-02-28T22:27:54Z → 2013-03-11T03:57:29Z (883775.000 s). Nearest legal boundary: 2013-03-11T04:59:38Z → 2013-03-11T21:02:13Z (57755.000 s); within-ten attainment yes. Supplied time span: 2012-12-26T03:33:49Z → 2013-03-15T22:34:48Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 111 records / 10085 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=58: 2013-02-28T22:27:54Z → 2013-03-02T17:59:25Z (156691.000 s). Nearest legal boundary: 2013-03-02T18:04:05Z → 2013-03-02T22:28:11Z (15846.000 s); within-ten attainment yes. Supplied time span: 2012-12-26T03:33:49Z → 2013-04-07T20:24:10Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 117 records / 10163 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=58: 2013-02-28T22:27:54Z → 2013-03-13T21:09:37Z (1118503.000 s). Nearest legal boundary: 2013-03-14T10:08:00Z → 2013-03-15T05:04:27Z (68187.000 s); within-ten attainment yes. Supplied time span: 2012-12-26T03:33:49Z → 2013-04-03T05:18:59Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-10

stratum-01: GradSchool → AskAcademia; fixed cut 2016-12-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 1 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 1; [55, 55] → 1 | 1 / 1 / 0 | yes / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 1 / unavailable | no / no | 9 |
| Both switches | yes / ok | 1; [43, 43] → 11 | 11 / 1 / 10 | no / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 40.560 s; 321.637 MiB; 68,294,144 bytes | attempted; exit 0; 40.862 s; 322.055 MiB; 68,294,182 bytes | yes |
| Source switch / same community | attempted; exit 0; 43.065 s; 333.723 MiB; 71,743,631 bytes | attempted; exit 0; 43.017 s; 334.223 MiB; 71,743,668 bytes | yes |
| Continuity / changed community | attempted; exit 0; 35.497 s; 296.137 MiB; 59,353,531 bytes | attempted; exit 0; 35.653 s; 295.672 MiB; 59,353,570 bytes | yes |
| Both switches | attempted; exit 0; 37.101 s; 305.609 MiB; 62,392,735 bytes | attempted; exit 0; 37.454 s; 304.438 MiB; 62,392,774 bytes | yes |

**Continuity / same community:** 107 records / 10171 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=54: 2016-11-28T06:38:13Z → 2016-12-27T03:17:02Z (2493529.000 s). Nearest legal boundary: 2016-12-27T03:17:02Z → 2016-12-27T03:27:51Z (649.000 s); within-ten attainment yes. Supplied time span: 2016-11-07T04:56:28Z → 2017-01-21T18:16:35Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 107 records / 10260 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=54: 2016-11-28T06:38:13Z → 2016-12-01T01:07:36Z (239363.000 s). Nearest legal boundary: 2016-12-01T01:07:36Z → 2016-12-01T20:23:38Z (69362.000 s); within-ten attainment yes. Supplied time span: 2016-11-07T04:56:28Z → 2017-03-15T16:33:18Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 109 records / 10124 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=54: 2016-11-28T06:38:13Z → 2017-01-06T12:56:07Z (3392274.000 s). Nearest legal boundary: 2017-01-06T12:56:07Z → 2017-01-08T02:51:07Z (136500.000 s); within-ten attainment yes. Supplied time span: 2016-11-07T04:56:28Z → 2017-02-12T21:08:34Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 113 records / 10158 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=54: 2016-11-28T06:38:13Z → 2016-12-02T21:55:47Z (400654.000 s). Nearest legal boundary: 2016-12-02T21:55:47Z → 2016-12-02T21:58:02Z (135.000 s); within-ten attainment yes. Supplied time span: 2016-11-07T04:56:28Z → 2017-02-13T03:16:04Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-14

stratum-04: linux → linuxquestions; fixed cut 2015-07-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 5 / unavailable | no / no | 8 |
| Source switch / same community | yes / ok | 1; [41, 41] → 5 | 5 / 5 / 0 | yes / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 5 / unavailable | no / no | 9 |
| Both switches | yes / ok | 1; [41, 41] → 5 | 5 / 5 / 0 | yes / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 41.486 s; 326.355 MiB; 69,303,927 bytes | attempted; exit 0; 41.715 s; 326.367 MiB; 69,303,965 bytes | yes |
| Source switch / same community | attempted; exit 0; 46.046 s; 348.141 MiB; 76,265,180 bytes | attempted; exit 0; 45.573 s; 348.672 MiB; 76,265,217 bytes | yes |
| Continuity / changed community | attempted; exit 0; 40.256 s; 319.598 MiB; 66,976,479 bytes | attempted; exit 0; 39.974 s; 320.156 MiB; 66,976,516 bytes | yes |
| Both switches | attempted; exit 0; 40.959 s; 325.203 MiB; 68,690,133 bytes | attempted; exit 0; 40.970 s; 325.324 MiB; 68,690,173 bytes | yes |

**Continuity / same community:** 93 records / 10040 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=46: 2015-06-30T02:27:13Z → 2015-07-01T14:24:18Z (129425.000 s). Nearest legal boundary: 2015-06-23T18:24:15Z → 2015-06-23T20:11:46Z (6451.000 s); within-ten attainment yes. Supplied time span: 2015-05-18T15:12:43Z → 2015-11-05T16:36:16Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 92 records / 10063 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=46: 2015-06-30T02:27:13Z → 2015-07-15T16:10:04Z (1345371.000 s). Nearest legal boundary: 2015-06-23T18:24:15Z → 2015-06-23T20:11:46Z (6451.000 s); within-ten attainment yes. Supplied time span: 2015-05-18T15:12:43Z → 2015-08-13T10:52:02Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 97 records / 10043 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=46: 2015-06-30T02:27:13Z → 2015-07-01T00:05:39Z (77906.000 s). Nearest legal boundary: 2015-06-23T18:24:15Z → 2015-06-23T20:11:46Z (6451.000 s); within-ten attainment yes. Supplied time span: 2015-05-18T15:12:43Z → 2015-08-05T14:25:10Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 91 records / 10186 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=46: 2015-06-30T02:27:13Z → 2015-07-05T14:47:14Z (476401.000 s). Nearest legal boundary: 2015-06-23T18:24:15Z → 2015-06-23T20:11:46Z (6451.000 s); within-ten attainment yes. Supplied time span: 2015-05-18T15:12:43Z → 2015-08-20T16:00:48Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-12

stratum-05: learnprogramming → programming; fixed cut 2011-11-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 4 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 1; [50, 50] → 7 | 7 / 7 / 0 | yes / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 4 / unavailable | no / no | 8 |
| Both switches | yes / ok | 1; [51, 51] → 8 | 8 / 8 / 0 | yes / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 41.575 s; 326.902 MiB; 69,317,785 bytes | attempted; exit 0; 41.421 s; 326.605 MiB; 69,317,823 bytes | yes |
| Source switch / same community | attempted; exit 0; 43.584 s; 338.578 MiB; 72,944,013 bytes | attempted; exit 0; 43.467 s; 337.648 MiB; 72,944,052 bytes | yes |
| Continuity / changed community | attempted; exit 0; 35.146 s; 293.211 MiB; 58,477,914 bytes | attempted; exit 0; 34.966 s; 293.105 MiB; 58,477,955 bytes | yes |
| Both switches | attempted; exit 0; 38.853 s; 313.418 MiB; 64,800,230 bytes | attempted; exit 0; 38.512 s; 313.039 MiB; 64,800,268 bytes | yes |

**Continuity / same community:** 84 records / 10358 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=43: 2011-10-31T16:50:15Z → 2011-11-01T10:37:37Z (64042.000 s). Nearest legal boundary: 2011-11-01T11:16:03Z → 2011-11-01T12:37:27Z (4884.000 s); within-ten attainment yes. Supplied time span: 2011-10-24T22:31:38Z → 2011-11-11T23:44:24Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 87 records / 10358 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=43: 2011-10-31T16:50:15Z → 2011-11-01T16:37:07Z (85612.000 s). Nearest legal boundary: 2011-11-03T16:34:15Z → 2011-11-03T16:59:20Z (1505.000 s); within-ten attainment yes. Supplied time span: 2011-10-24T22:31:38Z → 2012-01-11T01:34:53Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 90 records / 10201 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=43: 2011-10-31T16:50:15Z → 2011-11-07T02:21:18Z (552663.000 s). Nearest legal boundary: 2011-11-11T01:58:02Z → 2011-11-11T20:50:02Z (67920.000 s); within-ten attainment yes. Supplied time span: 2011-10-24T22:31:38Z → 2011-12-09T07:27:00Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 88 records / 10314 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=43: 2011-10-31T16:50:15Z → 2011-11-01T15:17:23Z (80828.000 s). Nearest legal boundary: 2011-10-29T03:17:13Z → 2011-10-29T15:13:04Z (42951.000 s); within-ten attainment yes. Supplied time span: 2011-10-24T22:31:38Z → 2012-01-25T04:28:19Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-05

stratum-03: learnmath → math; fixed cut 2018-02-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 1; [74, 74] → 3 | 3 / 3 / 0 | yes / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 9 |
| Both switches | yes / ok | 1; [74, 74] → 3 | 3 / 3 / 0 | yes / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 42.515 s; 331.457 MiB; 70,609,574 bytes | attempted; exit 0; 42.364 s; 332.254 MiB; 70,609,612 bytes | yes |
| Source switch / same community | attempted; exit 0; 44.870 s; 345.781 MiB; 74,970,664 bytes | attempted; exit 0; 44.669 s; 346.195 MiB; 74,970,701 bytes | yes |
| Continuity / changed community | attempted; exit 0; 37.404 s; 306.367 MiB; 62,291,215 bytes | attempted; exit 0; 37.555 s; 306.371 MiB; 62,291,253 bytes | yes |
| Both switches | attempted; exit 0; 38.754 s; 315.109 MiB; 65,065,366 bytes | attempted; exit 0; 39.154 s; 315.465 MiB; 65,065,404 bytes | yes |

**Continuity / same community:** 139 records / 10048 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=71: 2018-01-29T08:15:14Z → 2018-02-02T04:48:54Z (333220.000 s). Nearest legal boundary: 2018-02-04T21:51:52Z → 2018-02-04T21:53:17Z (85.000 s); within-ten attainment yes. Supplied time span: 2017-11-20T18:10:27Z → 2018-03-20T19:32:20Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 141 records / 10077 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=71: 2018-01-29T08:15:14Z → 2018-02-01T02:32:22Z (238628.000 s). Nearest legal boundary: 2018-02-01T03:35:46Z → 2018-02-01T03:36:52Z (66.000 s); within-ten attainment yes. Supplied time span: 2017-11-20T18:10:27Z → 2018-02-07T15:26:33Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 148 records / 10059 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=71: 2018-01-29T08:15:14Z → 2018-02-01T04:33:54Z (245920.000 s). Nearest legal boundary: 2018-02-01T07:33:25Z → 2018-02-01T17:11:27Z (34682.000 s); within-ten attainment yes. Supplied time span: 2017-11-20T18:10:27Z → 2018-02-21T08:39:11Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 144 records / 10116 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=71: 2018-01-29T08:15:14Z → 2018-02-01T03:39:50Z (242676.000 s). Nearest legal boundary: 2018-02-01T22:12:58Z → 2018-02-01T22:21:34Z (516.000 s); within-ten attainment yes. Supplied time span: 2017-11-20T18:10:27Z → 2018-03-06T21:57:24Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-17

stratum-04: linuxquestions → linux; fixed cut 2018-02-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 4 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 0; none | unavailable / 2 / unavailable | no / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 1 / unavailable | no / no | 9 |
| Both switches | yes / ok | 1; [73, 73] → 1 | 1 / 1 / 0 | yes / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 39.561 s; 316.012 MiB; 65,945,455 bytes | attempted; exit 0; 40.016 s; 316.258 MiB; 65,945,494 bytes | yes |
| Source switch / same community | attempted; exit 0; 42.565 s; 331.715 MiB; 70,454,434 bytes | attempted; exit 0; 43.919 s; 332.176 MiB; 70,454,472 bytes | yes |
| Continuity / changed community | attempted; exit 0; 36.901 s; 304.074 MiB; 61,634,817 bytes | attempted; exit 0; 37.400 s; 302.938 MiB; 61,634,854 bytes | yes |
| Both switches | attempted; exit 0; 37.251 s; 305.176 MiB; 62,013,962 bytes | attempted; exit 0; 37.249 s; 304.855 MiB; 62,013,999 bytes | yes |

**Continuity / same community:** 139 records / 10061 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=72: 2018-01-31T16:53:56Z → 2018-02-01T18:02:18Z (90502.000 s). Nearest legal boundary: 2018-02-08T20:07:11Z → 2018-02-08T20:37:51Z (1840.000 s); within-ten attainment yes. Supplied time span: 2017-12-12T00:11:16Z → 2018-03-15T18:34:46Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 141 records / 10107 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=72: 2018-01-31T16:53:56Z → 2018-02-03T18:44:21Z (265825.000 s). Nearest legal boundary: 2018-02-03T18:46:43Z → 2018-02-08T21:57:32Z (443449.000 s); within-ten attainment yes. Supplied time span: 2017-12-12T00:11:16Z → 2018-03-30T03:32:41Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 143 records / 10056 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=72: 2018-01-31T16:53:56Z → 2018-02-01T22:20:16Z (105980.000 s). Nearest legal boundary: 2018-02-01T22:20:16Z → 2018-02-07T16:58:08Z (499072.000 s); within-ten attainment yes. Supplied time span: 2017-12-12T00:11:16Z → 2018-05-24T22:17:58Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 136 records / 10107 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=72: 2018-01-31T16:53:56Z → 2018-02-02T18:27:14Z (178398.000 s). Nearest legal boundary: 2018-02-02T18:27:14Z → 2018-02-02T20:53:24Z (8770.000 s); within-ten attainment yes. Supplied time span: 2017-12-12T00:11:16Z → 2018-04-18T04:20:13Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-18

stratum-01: GradSchool → AskAcademia; fixed cut 2016-12-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 1; [43, 43] → 5 | 5 / 3 / 2 | yes / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 4 / unavailable | no / no | 9 |
| Both switches | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 8 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 41.060 s; 322.676 MiB; 68,228,920 bytes | attempted; exit 0; 41.674 s; 322.609 MiB; 68,228,958 bytes | yes |
| Source switch / same community | attempted; exit 0; 44.767 s; 341.703 MiB; 74,313,257 bytes | attempted; exit 0; 44.282 s; 341.902 MiB; 74,313,294 bytes | yes |
| Continuity / changed community | attempted; exit 0; 35.999 s; 298.934 MiB; 60,491,141 bytes | attempted; exit 0; 36.201 s; 299.188 MiB; 60,491,178 bytes | yes |
| Both switches | attempted; exit 0; 35.395 s; 293.484 MiB; 58,896,060 bytes | attempted; exit 0; 35.046 s; 293.527 MiB; 58,896,098 bytes | yes |

**Continuity / same community:** 99 records / 10172 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=48: 2016-11-30T19:06:21Z → 2016-12-02T19:29:06Z (174165.000 s). Nearest legal boundary: 2016-12-05T10:18:02Z → 2016-12-06T16:44:16Z (109574.000 s); within-ten attainment yes. Supplied time span: 2016-11-03T10:50:55Z → 2017-02-25T11:32:52Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 89 records / 10110 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=48: 2016-11-30T19:06:21Z → 2016-12-01T14:13:40Z (68839.000 s). Nearest legal boundary: 2016-12-11T21:45:15Z → 2016-12-11T23:30:25Z (6310.000 s); within-ten attainment yes. Supplied time span: 2016-11-03T10:50:55Z → 2017-02-06T01:23:19Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 89 records / 10125 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=48: 2016-11-30T19:06:21Z → 2016-12-01T16:44:24Z (77883.000 s). Nearest legal boundary: 2016-12-03T15:03:40Z → 2016-12-04T12:25:32Z (76912.000 s); within-ten attainment yes. Supplied time span: 2016-11-03T10:50:55Z → 2017-02-18T22:05:17Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 90 records / 10050 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=48: 2016-11-30T19:06:21Z → 2016-12-05T22:10:04Z (443023.000 s). Nearest legal boundary: 2016-12-12T19:52:11Z → 2016-12-13T17:32:16Z (78005.000 s); within-ten attainment yes. Supplied time span: 2016-11-03T10:50:55Z → 2017-02-23T20:30:37Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.


## pilot6-pair-13

stratum-03: math → learnmath; fixed cut 2017-01-01T00:00:00Z. All four histories use the identical earlier anchor.

| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |
|---|---|---|---|---|---:|
| Continuity / same community | yes / ok | 0; none | unavailable / 3 / unavailable | no / no | 9 |
| Source switch / same community | yes / ok | 0; none | unavailable / 1 / unavailable | no / no | 9 |
| Continuity / changed community | yes / ok | 0; none | unavailable / 1 / unavailable | no / no | 9 |
| Both switches | yes / ok | 0; none | unavailable / 4 / unavailable | no / no | 9 |

Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. Errors use the unsnapped junction. Continuity rows report control-junction alignment.

| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |
|---|---|---|---|
| Continuity / same community | attempted; exit 0; 42.026 s; 327.207 MiB; 69,388,022 bytes | attempted; exit 0; 41.660 s; 327.719 MiB; 69,388,059 bytes | yes |
| Source switch / same community | attempted; exit 0; 42.082 s; 326.758 MiB; 69,271,915 bytes | attempted; exit 0; 41.912 s; 328.355 MiB; 69,271,953 bytes | yes |
| Continuity / changed community | attempted; exit 0; 37.170 s; 302.676 MiB; 61,468,045 bytes | attempted; exit 0; 37.256 s; 302.969 MiB; 61,468,083 bytes | yes |
| Both switches | attempted; exit 0; 37.873 s; 309.125 MiB; 63,237,517 bytes | attempted; exit 0; 38.357 s; 308.797 MiB; 63,237,555 bytes | yes |

**Continuity / same community:** 124 records / 10123 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=61: 2016-12-23T03:34:59Z → 2017-01-03T04:22:58Z (953279.000 s). Nearest legal boundary: 2017-01-03T22:01:32Z → 2017-01-05T16:01:32Z (151200.000 s); within-ten attainment yes. Supplied time span: 2016-11-06T21:49:13Z → 2017-02-23T19:04:02Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Source switch / same community:** 115 records / 10240 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=61: 2016-12-23T03:34:59Z → 2017-01-13T15:45:06Z (1858207.000 s). Nearest legal boundary: 2017-01-13T15:45:06Z → 2017-01-13T15:54:07Z (541.000 s); within-ten attainment yes. Supplied time span: 2016-11-06T21:49:13Z → 2017-03-26T23:50:11Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Continuity / changed community:** 125 records / 10203 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=61: 2016-12-23T03:34:59Z → 2017-01-03T20:00:09Z (1009510.000 s). Nearest legal boundary: 2017-01-03T20:00:09Z → 2017-01-03T20:52:26Z (3137.000 s); within-ten attainment yes. Supplied time span: 2016-11-06T21:49:13Z → 2017-02-15T15:20:26Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

**Both switches:** 125 records / 10402 retained words; normalized status ok; reasons none; window verification all_primary_memberships_counts_positions_verified. Full module statuses: activity: ok (no reasons); ai_text_detection: not_run (not_implemented_in_v1); coverage: ok (no reasons); interactions: ok (no reasons); links: ok (no reasons); reuse: ok (no reasons); style: ok (no reasons); text: ok (no reasons).

Junction k=61: 2016-12-23T03:34:59Z → 2017-01-17T19:06:16Z (2215877.000 s). Nearest legal boundary: 2017-01-19T21:06:49Z → 2017-01-20T20:46:16Z (85167.000 s); within-ten attainment yes. Supplied time span: 2016-11-06T21:49:13Z → 2017-06-01T11:47:13Z. Complete candidate UTC brackets and all legal boundaries remain in cases.json.

## Operating cost and stopping

Elapsed time from first analyzer dispatch: 1500.409 seconds. Global stop reason: unavailable. Execution artifact bytes before final aggregate reports: 4,755,150,025.

Recorded main case wall-time sum: 1426.106 seconds across 36 receipted histories. Replay case wall-time sum: 1427.464 seconds across 36 receipted histories. These sums are separate from elapsed study duration because cases run in parallel. Peak RSS values are per-process maxima and are not summed.

Every discovered study receipt, including failed and synthetic attempts, is listed below. Receipts can overlap or contain nested phases; their wall times must not be added to case times or interpreted as unique elapsed study duration. Resource thresholds trigger termination; retained oversized evidence remains recorded. Canonical replay excludes exactly ingest_receipt.json and run_receipt.json.

| Receipt | Status / exit | Wall seconds | Peak child RSS MiB |
|---|---|---:|---:|
| receipt-root-01/buffer-independent-check-01.receipt.json | completed / 0 | 9.370 | 172.445 |
| receipt-root-01/buffer-preparation-01.receipt.json | completed / 0 | 114.956 | 147.785 |
| receipt-root-01/cohort-preparation-01.receipt.json | completed / 0 | 0.850 | 179.090 |
| receipt-root-01/combined-study-tests-01.receipt.json | completed / 0 | 11.960 | 101.816 |
| receipt-root-01/content-audit-01.receipt.json | completed / 0 | 161.315 | 2533.648 |
| receipt-root-01/execution-registration-01.receipt.json | completed / 0 | 10.924 | 144.574 |
| receipt-root-01/historical-extension-01.receipt.json | completed / 0 | 0.499 | 79.484 |
| receipt-root-01/intake-supplement-01.receipt.json | completed / 0 | 468.661 | 1311.266 |
| receipt-root-01/intake-supplement-synthetic-01.receipt.json | completed / 0 | 0.382 | 40.961 |
| receipt-root-01/metadata-check-synthetic-01.invocation-error.json | failed / 2 | unavailable | unavailable |
| receipt-root-01/metadata-check-synthetic-02.receipt.json | completed / 0 | 0.812 | 41.027 |
| receipt-root-01/metadata-feasibility-01.receipt.json | failed / 1 | 1.343 | 56.613 |
| receipt-root-01/metadata-feasibility-02.receipt.json | completed / 0 | 38.657 | 964.148 |
| receipt-root-01/metadata-independent-check-02.receipt.json | failed / 1 | 0.478 | 19.520 |
| receipt-root-01/metadata-independent-check-03.receipt.json | completed / 0 | 20.407 | 300.680 |
| receipt-root-01/metadata-independent-synthetic-01.receipt.json | failed / 1 | 0.412 | 40.430 |
| receipt-root-01/metadata-independent-synthetic-02.receipt.json | completed / 0 | 0.389 | 40.285 |
| receipt-root-01/metadata-independent-synthetic-03.receipt.json | completed / 0 | 0.366 | 40.578 |
| receipt-root-01/metadata-null-compatibility-synthetic-01.receipt.json | completed / 0 | 0.948 | 40.727 |
| receipt-root-01/metadata-tests-01.receipt.json | failed / 2 | 0.371 | 41.168 |
| receipt-root-01/metadata-tests-02.receipt.json | completed / 0 | 0.287 | 40.367 |
| receipt-root-01/preparation-tests-01.receipt.json | completed / 0 | 0.323 | 40.812 |
| receipt-root-01/preparation-tests-02.receipt.json | completed / 0 | 0.358 | 40.770 |
| receipt-root-01/preparation-tests-03.receipt.json | completed / 0 | 0.354 | 40.605 |
| receipt-root-01/prepared-checker-synthetic-01.receipt.json | completed / 0 | 5.199 | 99.180 |
| receipt-root-01/prepared-checker-synthetic-02.receipt.json | completed / 0 | 5.850 | 99.543 |
| receipt-root-01/prepared-independent-check-01.receipt.json | completed / 0 | 11.008 | 218.078 |
| receipt-root-01/prior-preparation-exposure-01.receipt.json | completed / 0 | 5.911 | 33.777 |
| receipt-root-01/privacy-preflight-01.receipt.json | completed / 0 | 1.409 | 215.520 |
| receipt-root-01/replication-01.receipt.json | completed / 0 | 1503.139 | 446.773 |
| receipt-root-01/report-synthetic-01.receipt.json | completed / 0 | 0.583 | 40.277 |
| receipt-root-01/report-synthetic-02.receipt.json | completed / 0 | 0.427 | 40.434 |
| receipt-root-01/report-synthetic-03.receipt.json | completed / 0 | 0.517 | 40.207 |
| receipt-root-01/results-independent-check-01.receipt.json | completed / 0 | 55.326 | 445.473 |
| receipt-root-02/preservation-synthetic-01.receipt.json | completed / 0 | 0.301 | 40.199 |
| receipt-root-02/result-checker-synthetic-01.receipt.json | failed / 1 | 2.970 | 42.254 |
| receipt-root-02/result-checker-synthetic-02.receipt.json | completed / 0 | 3.214 | 42.250 |
| receipt-root-02/result-checker-synthetic-03.receipt.json | completed / 0 | 5.248 | 43.086 |
| receipt-root-02/result-checker-synthetic-04.receipt.json | completed / 0 | 5.230 | 42.656 |
| receipt-root-02/runner-synthetic-01.receipt.json | failed / 1 | 1.973 | 41.648 |
| receipt-root-02/runner-synthetic-02.receipt.json | completed / 0 | 1.997 | 41.887 |
| receipt-root-02/runner-synthetic-03.receipt.json | completed / 0 | 2.095 | 41.750 |
| receipt-root-02/runner-synthetic-04.receipt.json | completed / 0 | 2.184 | 41.812 |
| receipt-root-03/preservation-baseline-01.receipt.json | completed / 0 | 8.383 | 84.148 |
| receipt-root-03/preservation-final-01.receipt.json | completed / 0 | 9.496 | 84.238 |
