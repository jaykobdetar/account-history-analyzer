# Account-stream protocol frozen before scores

Use the first two development and first four evaluation accounts in metadata-ranked frozen cohort as account-consistency controls. Empty truth means corpus account ID continuity only; real stylistic transitions and actual human continuity are unknown. Never present their candidates as confirmed false alarms.

For evaluation ranks (1,2) and (3,4), use median creation timestamp of the union of their retained snapshots. Take A strictly before the timestamp and B at/after it. Keep all original record IDs, texts and timestamps; only manifest/account_id metadata are reassigned to one constructed-stream ID. The split is the first B record ordinal. No textual pattern or candidate score chooses it. If a side is empty, declare not constructible. Also retain exactly half the records ordered by sha256(ahas-realworld-v1:stream-missing: + record ID), preserving chronological order and adjusting the documented construction ordinal without top-up.

Analyze whole constructed/supplied histories via the existing account_stream interface, unmodified defaults, pooled comments, 10-record inclusive tolerance. No fine-tuning after scoring. Compare control/constructed/missingness strata separately; aggregate built-in metrics have only their documented proxy meaning. Re-run the entire dataset in a separate process with a different hash seed.
