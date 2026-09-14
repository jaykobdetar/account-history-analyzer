# Natural-text operating check before new full-history scoring

This is a previously exposed 400-comment Cornell pilot sample, explicitly reserved as development evidence. It is not an untouched confirmation case and is not a complete Reddit account history. Its original inputs/results remain unchanged. AHAS implementation: `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`.

| Execution | Wall seconds | Peak RSS MiB | Scope |
| --- | ---: | ---: | --- |
| Full analysis with cProfile | 195.994 | 458.930 | Includes instrumentation overhead; not ordinary throughput |
| Separate unprofiled full verification/recomputation | 74.462 | 454.242 | Includes artifact reading, full analysis and byte comparison |

`results.json` is 98,663,593 bytes (94.093 MiB); complete output is 106,739,210 bytes (101.794 MiB). All 14 canonical artifacts reproduce byte-for-byte in the reference environment under socket denial. Operational receipts are excluded from canonical identity.

The cProfile trace attributes 115.536 cumulative seconds to canonical serialization (`io.py:canonical_chunks`), with nested time in the recursive token emitter. Cumulative times overlap and include profiler overhead; they must not be summed into an end-to-end cost decomposition. The raw trace and complete sorted summaries are supplied for reproducible inspection. No optimization, truncation, representation change or resource-limit change was made.

The next chronological sampling frame selects complete available three-corpus histories of 200–400 comments before scoring, rather than truncating larger accounts. This is an explicit resource/selection limitation, not a universal performance bound. Run at most two full-history jobs at once; per-case actual RAM, time, output size and failures remain observations. Paired comparisons use fixed subset-only operational chunks. Corpus metadata/preprocessing costs are recorded separately in the inventory.
