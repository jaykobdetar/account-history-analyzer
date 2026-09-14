# Independent score-free source check

Before any new style score, independently verify a deterministic sample of 100
previously preprocessed nonexcluded records from the completed census metadata.
Rank original record IDs by SHA256(`ahas-pilot3-source-check-v1:` + original ID).
Do not rank by text, style, agreement with the recorded count, or whether a result
would be appealing. If fewer than 100 eligible-for-check records exist, check all
and report the actual denominator. This sample is verification, not cohort
selection or a new experimental arm.

Stream the frozen listed archives once to locate the sampled IDs. Verify exact
source-line hashes, source account/community, original timestamps, retained-word
counts and qualification reasons. Use the actual frozen preprocessor, counting
word-kind entries in its token-offset view independently of the census's
word-token-list length. Do not display source prose, publish original IDs, inspect
protected reserve writing, or calculate any distances.

This is one additional verification read, separate from the census's two passes:
at most 6,000,000 source rows/4,000,000,000 uncompressed bytes, 100 preprocessing
calls, five minutes, and 2 GiB address space. Report failure or unfinished source
matching explicitly. The completed census and original receipts remain unchanged.

The broader independent metadata checker recomputes every per-pair and period
capacity, exclusion absence, disjoint membership and global quota choice without
importing the census, allocation or AHAS calculations. Synthetic tests separately
exercise the frozen text rules and exact allocation arithmetic. Neither check
certifies corpus completeness, human identity, language, or content independence.
