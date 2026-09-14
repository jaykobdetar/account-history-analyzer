# Local evaluation of account-history measurements

Suite: **synthetic**. Status: **passed**.

Engineering checks and constructed signals do not establish real-world authorship, automation or AI-detection accuracy.
No confidence intervals are inferred from correlated observations. All source data and labels are supplied locally.

The complete observations, denominators, hashes, protocols and missingness reasons are in evaluation.json.

Real-world validation: **not_established**. External data: **not_evaluated**.
Truth sidecars describe construction operations only; the analyzer does not consume them.

Indexed cases: 6. Shipped-scenario coverage complete: true. Missing scenarios: none.
Check outcomes: {"failed": 0, "not&#95;evaluated": 0, "passed": 67}. A not-evaluated check is not a pass.

| Constructed case | Check outcomes | Analysis exit code |
| --- | --- | --- |
| arithmetic | {"failed": 0, "not&#95;evaluated": 0, "passed": 22} | 0 |
| constructed&#95;style&#95;shift | {"failed": 0, "not&#95;evaluated": 0, "passed": 5} | 0 |
| constructed&#95;topic&#95;shift | {"failed": 0, "not&#95;evaluated": 0, "passed": 4} | 0 |
| edge&#95;cases | {"failed": 0, "not&#95;evaluated": 0, "passed": 5} | 0 |
| empty | {"failed": 0, "not&#95;evaluated": 0, "passed": 4} | 0 |
| stable&#95;constructed&#95;style | {"failed": 0, "not&#95;evaluated": 0, "passed": 4} | 0 |

| Numerical check | Outcome | Expected | Observed |
| --- | --- | --- | --- |
| cosine&#95;0 | passed | 0 | 0.0 |
| cosine&#95;1 | passed | 1 | 1.0 |
| cosine&#95;2 | passed | 0.29289321881345254 | 0.29289321881345254 |
| jensen&#95;shannon&#95;0 | passed | 0 | 0.0 |
| jensen&#95;shannon&#95;1 | passed | 1 | 1.0 |
| cosine&#95;zero&#95;norm&#95;abstention | passed | None | None |
| jensen&#95;shannon&#95;zero&#95;mass&#95;abstention | passed | None | None |
| shingles&#95;set&#95;size&#95;a | passed | 3 | 3 |
| shingles&#95;set&#95;size&#95;b | passed | 3 | 3 |
| shingles&#95;intersection | passed | 2 | 2 |
| shingles&#95;union | passed | 4 | 4 |
| shingles&#95;jaccard | passed | 0.5 | 0.5 |
| shingles&#95;containment&#95;a&#95;in&#95;b | passed | 0.6666666666666666 | 0.6666666666666666 |
| shingles&#95;containment&#95;b&#95;in&#95;a | passed | 0.6666666666666666 | 0.6666666666666666 |
| empty&#95;shingles&#95;abstention | passed | None | None |
| classic&#95;delta&#95;toy&#95;arithmetic | passed | 2 | 2.0 |
| pelt&#95;internal&#95;boundaries | passed | &#91;4&#93; | &#91;4&#93; |
| pelt&#95;objective | passed | 1 | 1.0 |
| pelt&#95;no&#95;change&#95;objective | passed | 200 | 200.0 |
| pelt&#95;terminal&#95;endpoint&#95;is&#95;not&#95;change | passed | 8 | 8 |
| fixture&#95;index&#95;integrity | passed | True | True |

Construction boundary observations for constructed&#95;style&#95;shift: {"definition": "operation&#95;begins&#95;at&#95;zero&#95;based&#95;record&#95;position", "neighbor&#95;definition": "construction&#95;adjacent&#95;record&#95;inside&#95;either&#95;candidate&#95;adjacent&#95;window", "position": 160, "record&#95;interval": &#91;159, 160&#93;, "streams": &#91;{"candidates": &#91;{"boundary&#95;id": "boundary&#95;17e2c107014612bbeb4bc22b", "left&#95;record&#95;id": "constructed&#95;style&#95;shift&#95;165", "neighboring&#95;window": true, "record&#95;interval": &#91;164, 165&#93;, "record&#95;position&#95;gap": 4, "relation": "separated", "right&#95;record&#95;id": "constructed&#95;style&#95;shift&#95;166"}&#93;, "status": "ok", "stream&#95;id": "stream&#95;afcd4487c70e271f21def39c"}, {"candidates": &#91;&#93;, "status": "insufficient&#95;data", "stream&#95;id": "stream&#95;2349e53d835468c7fb3f9cb5"}, {"candidates": &#91;{"boundary&#95;id": "boundary&#95;29623d69477e9038dac69957", "left&#95;record&#95;id": "constructed&#95;style&#95;shift&#95;165", "neighboring&#95;window": true, "record&#95;interval": &#91;164, 165&#93;, "record&#95;position&#95;gap": 4, "relation": "separated", "right&#95;record&#95;id": "constructed&#95;style&#95;shift&#95;166"}&#93;, "status": "ok", "stream&#95;id": "stream&#95;e57b9dae79b466adc8b0929a"}, {"candidates": &#91;&#93;, "status": "insufficient&#95;data", "stream&#95;id": "stream&#95;71c5017ba31773903f90a371"}&#93;}.

Construction boundary observations for constructed&#95;topic&#95;shift: {"definition": "operation&#95;begins&#95;at&#95;zero&#95;based&#95;record&#95;position", "neighbor&#95;definition": "construction&#95;adjacent&#95;record&#95;inside&#95;either&#95;candidate&#95;adjacent&#95;window", "position": 160, "record&#95;interval": &#91;159, 160&#93;, "streams": &#91;{"candidates": &#91;&#93;, "status": "no&#95;measurable&#95;variation", "stream&#95;id": "stream&#95;afcd4487c70e271f21def39c"}, {"candidates": &#91;&#93;, "status": "insufficient&#95;data", "stream&#95;id": "stream&#95;2349e53d835468c7fb3f9cb5"}, {"candidates": &#91;&#93;, "status": "no&#95;measurable&#95;variation", "stream&#95;id": "stream&#95;e57b9dae79b466adc8b0929a"}, {"candidates": &#91;&#93;, "status": "insufficient&#95;data", "stream&#95;id": "stream&#95;71c5017ba31773903f90a371"}&#93;}.
