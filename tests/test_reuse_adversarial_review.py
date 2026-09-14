"""Independent AUD-003 review: substring tables, tie semantics and rollback."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes
from account_history_analyzer.reuse import analyze_reuse
from account_history_analyzer.reuse_matching import TokenMatch, TokenMatcher
from test_reuse import run_texts, WORDS


def substring_table_oracle(left, right, minimum):
    """Index all complete left substrings, then join independently enumerated right substrings."""
    index = {}
    for li, segment in enumerate(left):
        for size in range(minimum, len(segment)+1):
            for start in range(len(segment)-size+1):
                key = tuple(segment[start:start+size])
                position = (li, start)
                if key not in index or position < index[key]:
                    index[key] = position
    found = []
    for ri, segment in enumerate(right):
        for size in range(minimum, len(segment)+1):
            for start in range(len(segment)-size+1):
                key = tuple(segment[start:start+size])
                if key in index:
                    li, left_start = index[key]
                    found.append((-size, li, ri, left_start, start))
    if not found:
        return None
    size, li, ri, ls, rs = min(found)
    return TokenMatch(-size, li, ri, ls, rs)


SEGMENT = st.lists(st.sampled_from(['alpha', 'beta', 'gamma', 'café', "can't", '١٢', '123']), max_size=18)
RECORD = st.lists(SEGMENT, max_size=5)


@given(RECORD, RECORD, RECORD, st.integers(1, 8))
@settings(max_examples=160)
def test_REVIEW_REUSE_01_reused_suffix_index_agrees_with_substring_table(left, first, second, minimum):
    matcher = TokenMatcher(left, minimum)
    for right in (first, second, left, first):
        assert matcher.find(right) == substring_table_oracle(left, right, minimum)


def test_REVIEW_REUSE_02_segment_priority_precedes_earliest_token_position():
    left = [['short'], ['padding', 'a', 'b', 'a', 'b'], ['a', 'b', 'a', 'b']]
    right = [['a', 'b', 'a', 'b'], ['padding', 'a', 'b', 'a', 'b']]
    # Longer match wins even though its right segment comes later.
    assert TokenMatcher(left, 2).find(right) == TokenMatch(5, 1, 1, 0, 0)
    right = [['a', 'b', 'a', 'b'], ['a', 'b', 'a', 'b']]
    # Earlier left segment wins before smaller token offset in a later segment.
    assert TokenMatcher(left, 2).find(right) == TokenMatch(4, 1, 0, 1, 0)


def test_REVIEW_REUSE_03_no_cross_segment_match_after_skipped_short_segments():
    left = [['a', 'b'], [], ['c'], ['c', 'd'], ['a', 'b']]
    assert TokenMatcher(left, 2).find([['a', 'b', 'c', 'd']]) == TokenMatch(2, 0, 0, 0, 0)
    assert TokenMatcher(left, 3).find([['a', 'b', 'c', 'd']]) is None


def test_REVIEW_REUSE_04_failure_after_first_emitted_passage_discards_all_near_output(tmp_path):
    text = ' '.join(WORDS[:30])
    complete, snapshot, features, config = run_texts(tmp_path, [text]*3)
    assert len(complete['pairs']) == 3
    limited_config = config.with_overrides({'reuse': {'max_evidence_tokens': 45, 'repeat_reduced_near_sensitivity': True}})
    limited = analyze_reuse(snapshot, features, limited_config)
    assert limited['resource_usage']['evidence_tokens'] == 30
    assert limited['resource_limit_reason'] == 'max_evidence_tokens'
    assert limited['candidate_pair_count'] == 3 and not limited['candidate_count_is_lower_bound']
    assert limited['pairs'] == limited['connected_groups'] == limited['near_reductions'] == []
    assert limited['exact_groups'] == complete['exact_groups']
    assert limited['exact_reductions'] == complete['exact_reductions']
    assert limited['repeat_reduced_retained_ids'] == ['r000']
    assert canonical_bytes(analyze_reuse(snapshot, features, limited_config)) == canonical_bytes(limited)


def test_REVIEW_REUSE_05_disconnected_components_keep_only_their_own_edges(tmp_path):
    groups = [' '.join(WORDS[start:start+25]) for start in (0, 30, 60)]
    result, *_ = run_texts(tmp_path, [value for group in groups for value in (group, group)])
    assert result['budget_complete']
    assert len(result['pairs']) == len(result['connected_groups']) == 3
    pairs = {pair['pair_id']: pair for pair in result['pairs']}
    for group in result['connected_groups']:
        assert len(group['record_ids']) == 2 and len(group['pair_ids']) == 1
        pair = pairs[group['pair_ids'][0]]
        assert group['record_ids'] == [pair['left_record_id'], pair['right_record_id']]
    assert {identifier for group in result['connected_groups'] for identifier in group['pair_ids']} == set(pairs)
