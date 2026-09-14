"""Check native saved replay contracts; operational receipts stay separate."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]

def main():
    case='chrono-ApplyingToCollege-pair1-splice-full'
    original=ROOT/'outputs/streams'/case;replay=ROOT/'outputs/replay-splice'/case
    files={}
    for name in ['evaluation.json','report.md','checksums.json']:
        assert (original/name).read_bytes()==(replay/name).read_bytes(),name
        files[name]=hashlib.sha256((original/name).read_bytes()).hexdigest()
    left=ROOT/'outputs/streams'/(case+'.operation')/'grid-diagnostic.json'
    right=ROOT/'outputs/replay-splice'/(case+'.operation')/'grid-diagnostic.json'
    assert left.read_bytes()==right.read_bytes()
    result=json.loads((ROOT/'logs/natural-canonical-recompute.stdout.log').read_bytes())
    assert result['status']=='reproduced'
    assert result['verification_scope']=='all_canonical_artifacts'
    assert len(result['reproduced_artifacts'])==14
    assert {'report.md','report.html','checksums.json','results.json'}<=set(result['reproduced_artifacts'])
    assert sum(name.endswith('.svg') for name in result['reproduced_artifacts'])==5
    output={'status':'passed','splice_canonical_sha256':files,'splice_grid_diagnostic_byte_identical':True,
        'natural_verification':result,'splice_receipt':'logs/splice-canonical-replay.receipt.json',
        'natural_receipt':'logs/natural-canonical-recompute.receipt.json',
        'receipts_excluded_from_canonical_identity':True,'cross_platform_byte_identity_claimed':False}
    with (ROOT/'review/stream-reproduction.json').open('x') as handle:json.dump(output,handle,indent=2);handle.write('\n')
    print(json.dumps({'status':'passed','splice_artifacts':len(files),'natural_artifacts':len(result['reproduced_artifacts'])}))

if __name__=='__main__':main()
