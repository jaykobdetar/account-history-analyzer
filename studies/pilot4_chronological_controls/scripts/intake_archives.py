"""Bounded two-pass archive intake exporting only comment eligibility metadata.

The frozen AHAS preprocessor conversion matches pilot3 census.py. New design
rules do not alter that engine. First-pass body access checks availability only;
excluded accounts are rejected before any body-field access. No distance runs.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import zipfile

PLACEHOLDERS = {'', 'anonymous', '[anonymous]', 'unknown', '[unknown]', '[deleted]', '[removed]', '[missing]', 'automoderator'}
MANIFEST = {'default_language': 'en', 'text_format': 'markdown'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)+'\n').encode()


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write(path, value, private=False):
    with Path(path).open('xb') as handle:
        if private:
            os.chmod(path, 0o600)
        handle.write(canonical(value))


def stamp(value):
    if type(value) is not int:
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError, OSError):
        return None


def comment_metadata(raw, excluded):
    """Exclusions precede body access, including in synthetic spy mappings."""
    account = raw.get('user')
    if not isinstance(account, str):
        return None, None, 'missing_account'
    account = account.casefold()
    if account.strip() in PLACEHOLDERS:
        return None, None, 'placeholder_account'
    if account in excluded:
        return None, None, 'excluded_account'
    if raw.get('root') == raw.get('id'):
        return account, None, 'submission'
    instant = stamp(raw.get('timestamp'))
    if instant is None:
        return account, None, 'invalid_timestamp'
    return account, instant, None


def present_comment(raw, excluded):
    account, instant, reason = comment_metadata(raw, excluded)
    if reason is not None:
        return account, instant, reason
    body = raw.get('text')
    if not isinstance(body, str) or body.strip() in {'[removed]', '[deleted]'}:
        return account, instant, 'unavailable_text'
    return account, instant, None


def candidate_memberships(frame, pairs, minimum=80):
    """Both communities must qualify within the same registered pair."""
    memberships, by_pair = set(), {}
    for x, y in pairs:
        qualified = {a for a, counts in frame.items() if counts.get(x, 0) >= minimum and counts.get(y, 0) >= minimum}
        by_pair[x+' / '+y] = qualified
        memberships.update((a, c) for a in qualified for c in (x, y))
    return memberships, by_pair


def preprocess_comment(raw, community, excluded, config, preprocessing):
    """Return metadata,skip reason,call count; never return prose or features."""
    account, instant, reason = present_comment(raw, excluded)
    if reason is not None:
        return None, reason, 0
    body = raw.get('text')
    if len(body) > config['input']['max_text_codepoints']:
        return None, 'source_record_text_codepoint_limit', 0
    converted = {'id':raw['id'], 'kind':'comment', 'text':body, 'status':'present',
                 'created_utc':instant, 'language':None, 'subreddit':community, 'edit_state':'unknown'}
    view = preprocessing(converted, MANIFEST, config)
    words = sum(len(segment) for segment in view['word_tokens'])
    reason = None if view['usable'] and words >= config['style']['minimum_record_words'] else 'below_frozen_record_word_guard'
    item = {'account_key':account, 'community':community, 'record_id':raw['id'], 'created_utc':instant,
            'retained_words':words, 'reason':reason, 'thread_id':raw.get('root'), 'parent_id':raw.get('reply_to')}
    return item, reason, 1


def load_engine(plan):
    from account_history_analyzer import AnalysisConfig
    from account_history_analyzer.io import digest
    from account_history_analyzer.pipeline import implementation_identity
    from account_history_analyzer.text import preprocess
    config = AnalysisConfig.from_toml()
    fingerprint, environment, resources = implementation_identity()
    if fingerprint != plan['implementation_fingerprint'] or digest(config.analytical()) != plan['analysis_config_sha256']:
        raise ValueError('Frozen engine/configuration mismatch')
    return config, preprocess, {'implementation_fingerprint':fingerprint, 'analysis_config_sha256':digest(config.analytical()),
                               'reference_environment':environment, 'resource_hashes':resources}


def run(plan_path, flags_path, registration_path, source_root, out, private_out):
    started = time.monotonic(); started_utc = datetime.now(timezone.utc).isoformat()
    plan = json.loads(plan_path.read_bytes()); registration = json.loads(registration_path.read_bytes())
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise ValueError('Frozen offline runner required')
    if registration['plan_sha256'] != sha(plan_path) or registration['implementation_sha256'] != sha(__file__) or \
       registration['exposure_flags_sha256'] != sha(flags_path) or plan['exposure_flags_sha256'] != sha(flags_path):
        raise ValueError('Intake registration/input binding mismatch')
    for test in registration['test_files']:
        if sha(plan_path.parent.parent/test['path']) != test['sha256']:
            raise ValueError('Registered test changed')
    limits = plan['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['max_address_space_bytes'],)*2)
    flags = json.loads(flags_path.read_bytes())['accounts']
    if len({r['account_key'] for r in flags}) != len(flags) or any(r['account_key'] != r['account_key'].casefold() for r in flags) or \
       any(type(r[k]) is not bool for r in flags for k in ('pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure')):
        raise ValueError('Noncanonical exposure flags')
    mandatory = {r['account_key'] for r in flags if r['pilot1_or_pilot2_or_private_mandatory_exclusion']}
    scored3 = {r['account_key'] for r in flags if r['pilot3_selected_scored_exposure']}
    if len(mandatory) != 57 or len(scored3) != 60 or mandatory & scored3:
        raise ValueError('Required57+60 exclusion identities not established')
    excluded = mandatory | scored3
    capacity_only = {r['account_key'] for r in flags if r['prior_capacity_only_exposure']}
    config, preprocessing, engine = load_engine(plan)
    out.mkdir(parents=True, exist_ok=False); private_out.mkdir(parents=True, mode=0o700, exist_ok=False)
    initial = {'phase':'before_first_archive_scan', 'utc':datetime.now(timezone.utc).isoformat(), 'plan_sha256':sha(plan_path),
               'registration_sha256':sha(registration_path), 'script_sha256':sha(__file__), 'exposure_flags_sha256':sha(flags_path),
               **engine, 'style_distance_calls':0, 'limits':limits}
    write(out/'start-binding.json', initial)
    frame = defaultdict(Counter); all_ids = set(); counts = Counter(); source_bindings = []; total_uncompressed = 0
    private_bytes = 0; eligibility_bytes = 0; processed = 0
    def check(rows=0):
        if rows > limits['max_source_rows_per_pass'] or processed > limits['max_preprocessed_records']:
            raise RuntimeError('Intake row/preprocessor budget exhausted')
        if time.monotonic()-started > limits['max_wall_seconds']:
            raise TimeoutError('Intake wall budget exhausted')
        if eligibility_bytes > limits['max_eligibility_output_bytes'] or private_bytes > limits['max_private_output_bytes']:
            raise RuntimeError('Intake private output budget exhausted')
    def private_row(handle, row, *, eligibility=False):
        nonlocal private_bytes, eligibility_bytes
        data = canonical(row); private_bytes += len(data)
        if eligibility:
            eligibility_bytes += len(data)
        check(); handle.write(data)
    try:
        for source in plan['sources']:
            relative = Path(source['archive'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Archive path escapes declared root')
            path = source_root/relative
            if path.stat().st_size != source['bytes'] or sha(path) != source['sha256']:
                raise ValueError('Archive identity mismatch')
            digest = hashlib.sha256(); source_counts = Counter()
            with zipfile.ZipFile(path) as archive:
                matches = [m for m in archive.infolist() if m.filename == 'utterances.jsonl']
                if len(matches) != 1:
                    raise ValueError('Unique utterances member required')
                member = matches[0]; total_uncompressed += member.file_size
                if member.file_size != source['utterances_bytes'] or total_uncompressed > limits['max_source_uncompressed_bytes_per_pass']:
                    raise RuntimeError('Registered uncompressed source bound exceeded')
                with archive.open(member) as handle:
                    for line in handle:
                        digest.update(line); source_counts['rows'] += 1; counts['first_pass_rows'] += 1
                        if counts['first_pass_rows'] > limits['max_source_rows_per_pass']:
                            raise RuntimeError('Registered first-pass row cap exceeded')
                        if counts['first_pass_rows'] % 10000 == 0:
                            check(counts['first_pass_rows'])
                        raw = json.loads(line); rid = raw.get('id')
                        if not isinstance(rid, str) or not rid or rid in all_ids:
                            raise ValueError('Missing or duplicate original source ID')
                        all_ids.add(rid)
                        if (raw.get('meta') or {}).get('subreddit') != source['community']:
                            raise ValueError('Unexpected source community')
                        account, instant, reason = present_comment(raw, excluded)
                        source_counts[reason or 'present_timestamped_comment'] += 1
                        if reason is None:
                            frame[account][source['community']] += 1
            source_bindings.append({'community':source['community'], 'archive_sha256':source['sha256'],
                                    'archive_bytes':source['bytes'], 'utterances_sha256':digest.hexdigest(),
                                    'utterances_bytes':member.file_size, 'counts':dict(source_counts)})
            print(json.dumps({'phase':'metadata_first_pass', 'community':source['community'], 'source_rows':source_counts['rows']}), flush=True)
        check(counts['first_pass_rows']); del all_ids
        memberships, by_pair = candidate_memberships(frame, plan['community_pairs'], plan['raw_present_comments_per_community_min'])
        member_communities = defaultdict(list)
        for account, community in sorted(memberships):
            member_communities[account].append(community)
        with (private_out/'account-frame.jsonl').open('xb') as handle:
            os.chmod(private_out/'account-frame.jsonl', 0o600)
            for account, values in sorted(frame.items()):
                private_row(handle, {'account_key':account, 'present_timestamped_comment_counts':dict(values),
                                     'preprocess_communities':member_communities.get(account, []),
                                     'capacity_only_exposure':account in capacity_only})
        write(out/'metadata-prefilter-summary.json', {'accounts_with_any_present_timestamped_comment':len(frame),
              'candidate_accounts':len({a for a, c in memberships}), 'candidate_account_community_memberships':len(memberships),
              'candidate_accounts_by_pair':{k:len(v) for k,v in by_pair.items()},
              'raw_comment_rows_in_candidate_memberships':sum(frame[a][c] for a,c in memberships),
              'raw_minimum_per_community':plan['raw_present_comments_per_community_min'], 'sources':source_bindings,
              'preprocessing_calls_so_far':0, 'style_distance_calls':0})
        del frame
        rejections = Counter(); eligible = Counter(); second_bindings = []
        with (private_out/'record-eligibility.jsonl').open('xb') as log:
            os.chmod(private_out/'record-eligibility.jsonl', 0o600)
            for source in plan['sources']:
                digest = hashlib.sha256(); source_rows = 0
                with zipfile.ZipFile(source_root/source['archive']) as archive, archive.open('utterances.jsonl') as handle:
                    for line in handle:
                        digest.update(line); source_rows += 1; counts['second_pass_rows'] += 1
                        if counts['second_pass_rows'] > limits['max_source_rows_per_pass']:
                            raise RuntimeError('Registered second-pass row cap exceeded')
                        if counts['second_pass_rows'] % 10000 == 0:
                            check(counts['second_pass_rows'])
                        raw = json.loads(line); account = raw.get('user')
                        if not isinstance(account, str) or (account.casefold(), source['community']) not in memberships:
                            continue
                        if account.casefold() in excluded:
                            raise AssertionError('Excluded account entered candidate preprocessing')
                        #Availability guards use the frozen conversion contract; every actual call is counted before dispatch.
                        _, _, skip = present_comment(raw, excluded)
                        if skip is not None:
                            rejections[skip] += 1; continue
                        if len(raw['text']) > config['input']['max_text_codepoints']:
                            rejections['source_record_text_codepoint_limit'] += 1; continue
                        if processed >= limits['max_preprocessed_records']:
                            raise RuntimeError('Registered preprocessing call cap reached before next call')
                        processed += 1
                        item, reason, calls = preprocess_comment(raw, source['community'], excluded, config, preprocessing)
                        if calls != 1 or item is None:
                            raise AssertionError('Preprocessor dispatch count mismatch')
                        item['source_line_sha256'] = hashlib.sha256(line).hexdigest()
                        private_row(log, item, eligibility=True)
                        counts['eligibility_metadata_rows'] += 1
                        if reason:
                            rejections[reason] += 1
                        else:
                            eligible['frozen_eligible_records'] += 1; eligible['frozen_eligible_words'] += item['retained_words']
                            if plan['record_word_min'] <= item['retained_words'] <= plan['record_word_max']:
                                eligible['registered_record_bound_records'] += 1
                                eligible['registered_record_bound_words'] += item['retained_words']
                first = next(r for r in source_bindings if r['community'] == source['community'])
                if source_rows != first['counts']['rows'] or digest.hexdigest() != first['utterances_sha256']:
                    raise ValueError('Source changed between registered passes')
                second_bindings.append({'community':source['community'], 'rows':source_rows, 'utterances_sha256':digest.hexdigest()})
                print(json.dumps({'phase':'frozen_preprocessing', 'community':source['community'], 'preprocessing_calls':processed,
                                  'eligible_metadata_records':eligible['registered_record_bound_records']}), flush=True)
        check(counts['second_pass_rows'])
        if counts['first_pass_rows'] != counts['second_pass_rows'] or processed != counts['eligibility_metadata_rows']:
            raise AssertionError('Complete pass/metadata row count mismatch')
        result = {'status':'completed_score_free_archive_intake', 'plan_sha256':sha(plan_path), 'registration_sha256':sha(registration_path),
                  'implementation_sha256':sha(__file__), 'started_utc':started_utc, 'finished_utc':datetime.now(timezone.utc).isoformat(),
                  'wall_seconds':time.monotonic()-started, 'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  'counts':dict(counts), 'preprocessing_calls':processed, 'eligibility':dict(eligible), 'rejections':dict(rejections),
                  'source_passes':2, 'source_bindings':source_bindings, 'second_pass_bindings':second_bindings,
                  'eligibility_metadata_bytes':eligibility_bytes, 'eligibility_metadata_sha256':sha(private_out/'record-eligibility.jsonl'),
                  'private_output_bytes':private_bytes, 'limits':limits, 'style_distance_calls':0, 'source_prose_displayed':False,
                  'metadata_coverage':'One eligibility row per actual preprocessing call; unavailable/invalid/oversize candidate records are counted as rejections without rows and cannot supply eligible cells. Above500-word records remain in metadata with frozen eligibility; the unchanged calendar feasibility gate filters their registered word bounds.',
                  'calendar_capacity_evaluated':False, 'cohort_selected':False}
        write(out/'intake-summary.json', result)
        write(out/'private-artifact-hashes.json', {p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in private_out.iterdir() if p.is_file()})
        print(json.dumps({'status':result['status'], 'preprocessing_calls':processed, 'metadata_rows':counts['eligibility_metadata_rows']}), flush=True)
        return 0
    except Exception as error:
        write(out/'incomplete-intake.json', {'status':'incomplete_not_zero_capacity', 'error_type':type(error).__name__,
              'counts':dict(counts), 'preprocessing_calls':processed, 'plan_sha256':sha(plan_path),
              'wall_seconds':time.monotonic()-started, 'private_output_bytes':private_bytes})
        print(json.dumps({'status':'incomplete_not_zero_capacity', 'error_type':type(error).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan','exposure-flags','registration','source-root','out','private-out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.plan,args.exposure_flags,args.registration,args.source_root,args.out,args.private_out))
