#!/usr/bin/env python3
"""Generate AHAS design fixtures using only the Python standard library.

These are construction-controlled software test inputs, not human/bot labels,
real Reddit histories, or an evaluation of the unimplemented analyzer.
The script never calls a model, accesses a network, or reads a wall clock.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)
LEX = re.compile(r"(?u)[^\W\d_]+(?:['’][^\W\d_]+)*|\d+")


def stamp(value: datetime) -> str:
    return value.strftime('%Y-%m-%dT%H:%M:%SZ')


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + '\n', encoding='utf-8')


def record(account: str, index: int, text: str | None,
           offset: int | None, **overrides: Any) -> dict[str, Any]:
    obj: dict[str, Any] = {
        'schema_version': '1.0.0', 'id': f'{account}_{index:03d}',
        'account_id': account, 'kind': 'comment', 'text': text,
        'status': 'present',
        'created_utc': stamp(BASE + timedelta(seconds=offset)) if offset is not None else None,
        'subreddit': 'synthetic_examples', 'language': 'en',
        'edit_state': 'not_edited', 'edited_utc': None,
        'title': None, 'parent_id': None, 'thread_id': f'{account}_thread',
        'parent_created_utc': None, 'permalink': None,
    }
    obj.update(overrides)
    return obj


def save_case(out: Path, name: str, records: list[dict[str, Any]],
              *, text_format: str, truth: dict[str, Any]) -> None:
    (out / f'{name}.jsonl').write_text(
        ''.join(dumps(row) + '\n' for row in records), encoding='utf-8')
    account = records[0]['account_id'] if records else name
    valid_times = [row['created_utc'] for row in records if row['created_utc']]
    manifest = {
        'schema_version': '1.0.0', 'snapshot_id': f'{name}_snapshot_v1',
        'account_id': account, 'source_category': 'synthetic',
        'capture_utc': '2025-03-01T00:00:00Z',
        'text_format': text_format, 'default_language': 'en',
        'source_notes': 'Constructed software-test fixture. No real account or person is represented.',
        'license_notes': 'Original synthetic fixture material supplied for use and modification with this project.',
        'coverage': {
            'status': 'complete_for_declared_scope',
            'start_utc': min(valid_times) if valid_times else None,
            'end_utc': max(valid_times) if valid_times else None,
            'known_gaps': [],
            'notes': 'Complete only with respect to this artificial fixture, not any real platform account.',
        },
    }
    save_json(out / f'{name}.snapshot.json', manifest)
    save_json(out / f'{name}.truth.json', {
        'fixture_version': '1.0.0', 'case': name,
        'label_type': 'construction_operations_only',
        'human_bot_or_ai_ground_truth': 'not_applicable', **truth,
    })


def synthetic_text(index: int, *, garden: bool, formal: bool) -> str:
    # Equal-length content-word substitutions intentionally preserve the mask's
    # word-length shapes. This does not model realistic changes in subject matter.
    nouns = (['plant','grass','fruit','seeds','roots','stems','vines','bloom'] if garden else
             ['panel','cable','meter','valve','wheel','lever','relay','motor'])
    adjectives = (['green','fresh','sweet','thick','young','round','brown','moist'] if garden else
                  ['quiet','small','light','heavy','plain','loose','tight','sharp'])
    assert all(len(word) == 5 for word in nouns + adjectives)
    b = hashlib.sha256(f'ahas-fixture-{index}'.encode('ascii')).digest()
    n = [nouns[b[k] % len(nouns)] for k in range(12)]
    a = [adjectives[b[12+k] % len(adjectives)] for k in range(12)]
    verb = 'grows' if garden else 'works'
    sentences = [
        f"i think the {n[0]} is {a[0]}, but i don't think the {n[1]} is {a[1]}.",
        f"when the {n[2]} is {a[2]}, the {n[3]} can be {a[3]} and the {n[4]} can be {a[4]}.",
        f"we should put the {a[5]} {n[5]} by the {a[6]} {n[6]}, because it {verb} with the {a[7]} {n[7]}.",
        f"if the {n[8]} is {a[8]}, i would use the {n[9]} with the {a[9]} {n[10]}.",
        f"the {a[10]} {n[11]} is not the same as the {a[11]} {n[0]}, and we should see what it does.",
        f"i don't think we should do more until we see how the {n[1]} {verb}. case {index:06d}.",
    ]
    result = '\n\n'.join(sentences)
    if formal:
        result = result.upper().replace(', ', '; ').replace("DON'T", 'DO NOT')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    texts = [
        "I don't know, but I think it works.",
        "I  don't know, but I think it works.",
        "I do not know, but I think it works.",
        "> Someone else's quoted sentence.\n\nI think it works.\n\n```python\nprint('not prose')\n```",
        'See [the notes](https://example.test/notes) and https://example.test/again.',
        'THE RESULT WORKS!',
    ]
    offsets = [0, 10, 20, 60, 120, 180]
    rows = [record('arithmetic', i+1, text, offset) for i, (text, offset) in enumerate(zip(texts, offsets))]
    rows[3]['parent_id'] = 'arithmetic_001'
    rows[3]['parent_created_utc'] = stamp(BASE)
    rows[5]['edit_state'] = 'edited'
    rows[5]['edited_utc'] = stamp(BASE + timedelta(seconds=240))
    # One ingestion duplicate: same ID and all supplied fields. It is not an event.
    rows.append(dict(rows[1]))
    retained = [texts[0], texts[0], texts[2], 'I think it works.', 'See the notes and .', texts[5]]
    word_counts = [sum(not token.isdigit() for token in LEX.findall(text)) for text in retained]
    assert word_counts == [8, 8, 9, 4, 4, 3]
    save_case(out, 'arithmetic', rows, text_format='markdown', truth={
        'raw_input_lines': 7, 'unique_events': 6, 'ingestion_duplicate_records': 1,
        'event_offsets_seconds': offsets,
        'inter_event_gaps_seconds': [10, 10, 40, 60, 60],
        'gap_mean_seconds': 36, 'gap_population_variance_seconds_squared': 504,
        'gap_coefficient_of_variation': math.sqrt(504) / 36,
        'gap_quantiles_seconds': {'0.25': 10, '0.5': 40, '0.75': 60},
        'max_events_in_sliding_windows': {'30': 3, '120': 5, '3600': 6},
        'greedy_30_second_3_event_bursts': [['arithmetic_001','arithmetic_002','arithmetic_003']],
        'retained_word_counts_by_unique_record': dict(zip([r['id'] for r in rows[:6]], word_counts)),
        'retained_word_count_total': 36,
        'normalized_prose_identical_group': ['arithmetic_001','arithmetic_002'],
        'dont_occurrences': 2, 'do_not_occurrences': 1,
        'literal_dont_preference_raw_fraction': {'numerator': 2, 'denominator': 3},
        'qualified_contraction_preference_status': 'insufficient_opportunities',
        'links': {'example.test': {'occurrences': 2, 'records_with_host': 1}},
        'default_style_eligible_records': 0,
        'notes': 'URL destination strings, explicit blockquote text, and code are excluded from retained word counts. These values are expected arithmetic, not measured analyzer outputs.',
    })

    for name in ['stable_constructed_style','constructed_style_shift','constructed_topic_shift']:
        rows = []
        for index in range(320):
            garden = name == 'constructed_topic_shift' and index >= 160
            formal = name == 'constructed_style_shift' and index >= 160
            rows.append(record(name, index+1, synthetic_text(index, garden=garden, formal=formal), index*3*3600,
                               subreddit='synthetic_single_context'))
        save_case(out, name, rows, text_format='plain', truth={
            'record_count': 320,
            'transformation_starts_at_zero_based_record': 160 if name != 'stable_constructed_style' else None,
            'construction': {
                'stable_constructed_style': 'Fixed lowercase template with hash-selected equal-length content words and a unique numeric case marker.',
                'constructed_style_shift': 'Second half is uppercased, comma-space becomes semicolon-space, and DON\'T becomes DO NOT.',
                'constructed_topic_shift': 'Second half substitutes equal-length content words and works→grows; mask shape and registered surface/function rates should remain unchanged.',
            }[name],
            'activity_note': 'An exact three-hour artificial timestamp interval is a construction convenience, not a human baseline.',
            'acceptance_scope': 'Test operational measurements and controlled feature changes only; no real-world detection-accuracy claim.',
        })

    hazards = [
        record('edge_cases', 1, 'This record has text but no known creation timestamp.', None),
        record('edge_cases', 2, None, 10, status='removed'),
        record('edge_cases', 3, '[deleted]', 20),
        record('edge_cases', 4, 'Este texto no debe usar la lista inglesa de palabras funcionales.', 30, language='es'),
        record('edge_cases', 5, '<script>alert("do not execute");</script>\n\nVisible ordinary prose remains separate.', 40,
               id='../../untrusted_id', permalink='javascript:alert(1)'),
        record('edge_cases', 6, '[click](javascript:alert(1))\n\n![image](https://example.test/pixel.png)', 50),
    ]
    save_case(out, 'edge_cases', hazards, text_format='markdown', truth={
        'record_count': 6, 'valid_timestamp_count': 5,
        'removed_records': 1, 'present_deleted_sentinel_records': 1,
        'notes': 'Valid input exercising missingness, supplied language, unsafe HTML/URLs, and pathlike IDs. Never execute or fetch any source content.',
    })
    save_case(out, 'empty', [], text_format='plain', truth={
        'record_count': 0, 'expected_analysis': 'Coverage present; analysis modules show appropriate insufficient-data/not-run states, never a human/bot verdict.',
    })

    save_json(out/'numerical_oracles.json', {
        'purpose': 'Hand-checkable expected values for low-level functions, below product minimum-text gates.',
        'cosine': [
            {'x':[1,0],'y':[1,0],'expected_distance':0},
            {'x':[1,0],'y':[0,1],'expected_distance':1},
            {'x':[1,0],'y':[1,1],'expected_distance':1-1/math.sqrt(2)},
        ],
        'jensen_shannon_base_2_distance': [
            {'p':[1,0],'q':[1,0],'expected_distance':0},
            {'p':[1,0],'q':[0,1],'expected_distance':1},
        ],
        'shingles': {
            'tokens_a':'one two three four five six seven'.split(),
            'tokens_b':'one two three four five six eight'.split(),
            'n':5,'set_size_a':3,'set_size_b':3,'intersection':2,'union':4,
            'jaccard':0.5,'containment_a_in_b':2/3,'containment_b_in_a':2/3,
        },
        'delta': {'vocabulary':['the','and'],'means':[50,100],'stds':[10,20],
                  'frequency_a':[40,140],'frequency_b':[60,100],'expected_delta':2},
        'pelt_unscaled_l2': {'series':[0,0,0,0,10,10,10,10],
                            'minimum_segment_size':3,'penalty_per_internal_change':1,
                            'expected_internal_boundaries':[4],
                            'no_change_objective':200,'optimal_objective':1},
    })
    file_index = []
    for path in sorted(out.glob('*.json*')):
        if path.name == 'fixture_index.json':
            continue
        data = path.read_bytes()
        file_index.append({'file':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    save_json(out/'fixture_index.json', {'fixture_version':'1.0.0','files':file_index})
    print(f'Wrote deterministic fixtures to {out}')


if __name__ == '__main__':
    main()
