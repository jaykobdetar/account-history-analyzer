#!/usr/bin/env python3
"""Independent pairwise AUC and exact-rational tied AP checks of saved outputs."""
import hashlib,json,math
from fractions import Fraction
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def oracle(rows):
    observed=[row for row in rows if row['score'] is not None]
    positive=[row['score'] for row in observed if row['label']=='different_author']
    negative=[row['score'] for row in observed if row['label']=='same_author']
    auc=(sum(Fraction(1) if p>n else Fraction(1,2) if p==n else Fraction(0) for p in positive for n in negative)/(len(positive)*len(negative))) if positive and negative else None
    # Each positive contributes precision at the end of its whole tied group.
    ap=sum((Fraction(sum(p>=score for p in positive),sum(row['score']>=score for row in observed)) for score in positive),Fraction(0))/len(positive) if positive else None
    return {'roc_auc':float(auc) if auc is not None else None,
            'average_precision':float(ap) if ap is not None else None,
            'scored':len(observed),'total':len(rows),'abstained':len(rows)-len(observed)}

def main():
    index=json.loads((ROOT/'outputs/paired/execution-index.json').read_bytes())
    summary=[]
    for item in index['runs']:
        assert item['driver_exit_code']==0,item['path']
        path=ROOT/item['output']/'evaluation.json';evaluation=json.loads(path.read_bytes())
        assert evaluation['frozen_threshold'] is None
        assert evaluation['implementation_fingerprint']==json.loads((ROOT/'protocol/plan.json').read_bytes())['implementation_fingerprint']
        for split,partition in evaluation['partitions'].items():
            expected=oracle(partition['rows']);metrics=partition['metrics']
            for name in ('roc_auc','average_precision'):
                actual=metrics['ranking'][name]['value']
                assert (actual is None)==(expected[name] is None)
                if actual is not None:assert math.isclose(actual,expected[name],rel_tol=0,abs_tol=1e-15)
            assert metrics['total_pair_count']==expected['total']
            assert metrics['scored_pair_count']==expected['scored']
            assert metrics['abstained_pair_count']==expected['abstained']
            assert metrics['decisions']['confusion'] is None
            for row in partition['rows']:
                assert (row['status']=='ok')==(row['score'] is not None)
                assert row['score'] is None or row['score']==row['raw_distance']
            summary.append({'dataset':item['path'],'partition':split,**expected})
    output={'status':'passed','checks':'Brute positive-negative AUC and exact rational whole-tie AP; null/coverage/threshold contracts.',
            'partition_count':len(summary),'rows':summary}
    with (ROOT/'review/independent-pair-metrics.json').open('x') as target:json.dump(output,target,indent=2);target.write('\n')
    print(json.dumps({'status':'passed','partitions':len(summary)}))

if __name__=='__main__':main()
