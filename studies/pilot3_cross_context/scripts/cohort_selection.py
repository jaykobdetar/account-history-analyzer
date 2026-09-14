"""Score-free metadata selection helpers; not a scoring registration.

Raw account identities and record metadata passed to these functions are private.
They must not be published as purportedly anonymized source maps.
"""
from datetime import datetime, timezone
from hashlib import sha256

from study_math import maximum_disjoint_capacity

ACCOUNT_SALT = 'ahas-pilot3-account-rank-v1:'


def account_rank(account):
    if not isinstance(account, str) or not account or account != account.casefold():
        raise ValueError('A nonempty canonical source account key is required')
    return sha256((ACCOUNT_SALT + account).encode()).hexdigest()


def hash_quota_allocation(eligible, limit=20):
    """Exact quotas followed by deterministic flow in source-identity hash order.

    Candidate intake uses limit 40; final cohort uses limit 20 and must separately
    require every planned quota. No distance or measured separation is an input.
    """
    keys = set().union(*eligible.values()) if eligible else set()
    reverse = {account_rank(account): account for account in keys}
    if len(reverse) != len(keys):
        raise ValueError('Source-identity ranking hash collision')
    ranked = {s: {account_rank(a) for a in accounts} for s, accounts in eligible.items()}
    result = maximum_disjoint_capacity(ranked, limit)
    result['assigned'] = {s: [reverse[a] for a in accounts]
                          for s, accounts in result['assigned'].items()}
    result['assignment_role'] = 'prespecified_hash_ordered_quota_allocation'
    result['account_ranking_salt'] = ACCOUNT_SALT
    return result


def utc_seconds(stamp):
    value = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    elif value.utcoffset().total_seconds() != 0:
        raise ValueError('UTC source time required')
    seconds = value.timestamp()
    if seconds != int(seconds):
        raise ValueError('Original integer-second timestamp required')
    return int(seconds)


def candidate_prefix(rows, bounds, target_words=3000):
    """Whole-record midpoint prefix for auditing, never a post-audit refill.

    If fewer than 3000 words are available, all eligible records may enter the
    audit provided the unchanged four-cell prerequisite of 2000 words/8 records
    is met. Final full units are separately selected from audited survivors.
    """
    if target_words != 3000:
        raise ValueError('The preparatory audit-buffer target is fixed at 3000')
    start, end = map(utc_seconds, bounds)
    if start >= end:
        raise ValueError('Positive calendar period required')
    rows = list(rows)
    seen, identities = set(), set()
    for row in rows:
        rid, words = row['record_id'], row['retained_words']
        if (not isinstance(rid, str) or not rid or rid in seen
                or row.get('reason') is not None or type(words) is not int or words < 20):
            raise ValueError('Unique eligible original records are required')
        seen.add(rid)
        identities.add((row['account_key'], row['community']))
        if not start <= utc_seconds(row['created_utc']) < end:
            raise ValueError('Original record outside the frozen period')
    if len(identities) != 1:
        raise ValueError('Exactly one source account/community cell required')
    ordered = sorted(rows, key=lambda r: (abs(2 * utc_seconds(r['created_utc']) - start - end),
                                          utc_seconds(r['created_utc']), r['record_id']))
    chosen, words = [], 0
    for row in ordered:
        chosen.append(row)
        words += row['retained_words']
        if words >= target_words and len(chosen) >= 8:
            break
    if words < 2000 or len(chosen) < 8:
        raise ValueError('Candidate cell fails the unchanged 2000-word/eight-record prerequisite')
    return sorted(chosen, key=lambda r: (utc_seconds(r['created_utc']), r['record_id']))
