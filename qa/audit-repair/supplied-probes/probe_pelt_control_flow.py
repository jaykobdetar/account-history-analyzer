"""Audit the original PELT function body against independent exact DP.
The installed pinned ruptures is unavailable here. This probe AST-extracts the
unchanged AHAS pelt_l2 function and supplies an explicitly marked direct SSE
cost adapter. It checks AHAS control flow, NOT the pinned third-party primitive,
not the upstream bug claim, and not full AHAS integration.
Usage: python probe_pelt_control_flow.py REPO OUTPUT_JSON
"""
import ast, hashlib, json, math, sys
from pathlib import Path
import numpy as np
repo=Path(sys.argv[1]).resolve();sys.path.insert(0,str(repo/'src'))
from account_history_analyzer.errors import InputError, ComputationError
source=repo/'src/account_history_analyzer/changepoints.py';tree=ast.parse(source.read_text())
node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='pelt_l2')
class DirectSSEAdapter:
    def fit(self,signal):self.signal=signal;return self
    def error(self,start,end):
        data=self.signal[start:end];residual=data-data.mean(axis=0)
        return float((residual*residual).sum())
space={'np':np,'math':math,'CostL2':DirectSSEAdapter,'InputError':InputError,
       'ComputationError':ComputationError,'PRUNING_TOLERANCE':1e-12,
       'OPTIMIZER':'pelt_l2_min_size_safe_pruning_v1'}
module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])
exec(compile(ast.fix_missing_locations(module),str(source),'exec'),space)
fn=space['pelt_l2']
def independent_dp(x,penalty,minimum):
    """Unpruned optimizer with separately calculated scalar SSE on every segment."""
    x=np.asarray(x,dtype=float);x=x[:,None] if x.ndim==1 else x
    n=len(x);cost=[math.inf]*(n+1);cost[0]=0.;prev=[None]*(n+1)
    for end in range(minimum,n+1):
        for start in range(end-minimum+1):
            if not math.isfinite(cost[start]):continue
            sse=0.
            for column in range(x.shape[1]):
                values=[float(v) for v in x[start:end,column]]
                mean=math.fsum(values)/len(values)
                sse+=math.fsum((v-mean)**2 for v in values)
            candidate=cost[start]+sse+(penalty if start else 0.)
            if candidate<cost[end]:cost[end]=candidate;prev[end]=start
    ends=[];end=n
    while end:ends.append(end);end=prev[end]
    ends.reverse();return {'objective':cost[n],'internal_boundaries':ends[:-1]}
rng=np.random.default_rng(374651)
checks=0;max_error=0.;boundary_differences=0;failures=[]
for minimum in [1,2,3,4,5]:
  for n in [minimum,minimum+1,2*minimum,3*minimum,20,35]:
    for dims in [1,3]:
      for case in range(8):
        if case==0:x=np.zeros((n,dims))
        elif case==1:x=np.full((n,dims),7.)
        elif case in [2,3]:x=rng.integers(-10,11,size=(n,dims))
        elif case in [4,5]:x=rng.normal(size=(n,dims))
        else:x=np.repeat(rng.integers(-4,5,size=(4,dims)),(n+3)//4,axis=0)[:n]
        penalty=[0.,.1,1.,math.log(max(n,2))][case%4]
        actual=fn(x,penalty,min_size=minimum);expected=independent_dp(x,penalty,minimum)
        error=abs(actual['objective']-expected['objective']);max_error=max(max_error,error);checks+=1
        if actual['internal_boundaries']!=expected['internal_boundaries']:boundary_differences+=1
        if not math.isclose(actual['objective'],expected['objective'],abs_tol=1e-9,rel_tol=1e-12):
            failures.append({'n':n,'minimum':minimum,'dims':dims,'case':case,'actual':actual,'expected':expected})
example=fn([0,9,2,8,3,0,10],.1,min_size=3)
result={'scope':'Original AHAS function body with direct SSE adapter; not pinned ruptures or full pipeline execution',
        'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'seed':374651,'cases':checks,
        'failures':failures,'maximum_absolute_objective_difference':max_error,
        'boundary_differences_including_equally_optimal_ties':boundary_differences,'documented_example':example}
Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert not failures
