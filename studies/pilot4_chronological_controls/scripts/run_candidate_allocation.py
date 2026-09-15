"""Bind and execute the prespecified metadata-only candidate-pool allocation."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
import os
from pathlib import Path
import resource
import signal
from allocate_candidate_accounts import allocate
from run_full_chronology import sha, write


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'numerator', 'denominator'}:
            return Fraction(value['numerator'], value['denominator'])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--registration', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--public-out', required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Offline wrapper required')
    reg = json.loads(args.registration.read_bytes())
    if reg['phase'] != 'frozen_before_metadata_allocation' or reg['script_sha256'] != sha(__file__):
        raise ValueError('Allocation registration mismatch')
    for row in reg['bound_artifacts']:
        if sha(row['path']) != row['sha256']:
            raise ValueError('Allocation dependency changed')
    if args.out.exists() or args.public_out.exists():
        raise ValueError('Refuse to replace prior allocation')
    resource.setrlimit(resource.RLIMIT_AS, (4294967296,)*2)
    signal.alarm(600)
    strata = {}
    for source in reg['sources']:
        document = decode(json.loads(Path(source['path']).read_bytes()))
        for name in source['stratum_ids']:
            if name in strata:
                raise ValueError('Repeated allocation stratum')
            strata[name] = document['strata'][name]
    result = allocate(strata, json.loads(Path(reg['design']).read_bytes()))
    result['strata'] = [dict(stratum_id=name, communities=strata[name]['public']['communities'],
                             cut=strata[name]['public']['cut'], accounts=result['assigned'][name],
                             block_cap=result['planned_block_caps'][name]) for name in sorted(strata)]
    result['registration_sha256'] = sha(args.registration)
    result['created_utc'] = datetime.now(timezone.utc).isoformat()
    result['style_scores_computed'] = 0
    write(args.out, result)
    os.chmod(args.out, 0o600)
    public = {key: result[key] for key in ('registration_sha256', 'created_utc', 'style_scores_computed',
              'attainable_reserved_block_counts', 'planned_block_caps', 'registered_target_deficits',
              'candidate_graph_edges')}
    public['private_allocation_sha256'] = sha(args.out)
    public['strata'] = [{k: v for k, v in spec.items() if k != 'accounts'} |
                        {'candidate_accounts': len(spec['accounts'])} for spec in result['strata']]
    public['global_accounts_distinct'] = True
    write(args.public_out, public)
    print(json.dumps(public))


if __name__ == '__main__':
    main()
