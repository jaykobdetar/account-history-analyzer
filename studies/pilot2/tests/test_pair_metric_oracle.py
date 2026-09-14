import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('pair_metric_oracle',Path(__file__).resolve().parents[1]/'scripts/check_pair_metrics.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.parametrize('negative,positive,auc,ap',[
    ([0,0],[1,1],1,1),([1,1],[0,0],0,0.5),([1,1],[1,1],0.5,0.5),
    ([0,2],[1,3],0.75,5/6),([],[],None,None),([1],[],None,None),([],[1],None,1)])
def test_hand_checkable_ranking(negative,positive,auc,ap):
    rows=[{'label':'same_author','score':score} for score in negative]+[{'label':'different_author','score':score} for score in positive]
    rows.append({'label':'different_author','score':None})
    result=module.oracle(rows)
    assert result['roc_auc']==auc and result['average_precision']==ap
    assert result['abstained']==1
