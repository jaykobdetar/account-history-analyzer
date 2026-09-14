"""Independent AHAS checks for the pinned PR383 minimum-length PELT backport."""
from __future__ import annotations

import ast
from fractions import Fraction
import hashlib
import inspect
from itertools import combinations
import json
import math
from pathlib import Path
import random

import numpy as np
import pytest
from ruptures import Pelt

from account_history_analyzer._vendor.ruptures_pr383 import PeltMinSize
from account_history_analyzer.changepoints import pelt_l2
from account_history_analyzer.errors import ComputationError, InputError

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT/'src/account_history_analyzer/_vendor'
COMMIT = 'a28574d9e63b0c2a966e176a1d049d3c9deaaaaf'


def exact_costs(signal):
    """Rational SSE via moments, independent of NumPy variance/residual paths."""
    columns = list(zip(*signal, strict=True))
    costs = {}
    for start in range(len(signal)):
        for end in range(start+1,len(signal)+1):
            total = Fraction(0)
            for column in columns:
                sample = [Fraction(value) for value in column[start:end]]
                total += sum(value*value for value in sample)-sum(sample)**2/len(sample)
            costs[start,end] = total
    return costs


def exact_partition_objective(costs, ends, penalty):
    starts = (0,)+tuple(ends[:-1])
    return sum(costs[start,end] for start,end in zip(starts,ends,strict=True))+Fraction(penalty)*(len(ends)-1)


def exact_grid_oracle(signal, minimum, jump, penalty):
    costs = exact_costs(signal)
    n = len(signal)
    grid = tuple(range(jump,n,jump))
    candidates = []
    for count in range(len(grid)+1):
        for internal in combinations(grid,count):
            ends = internal+(n,)
            if all(end-start>=minimum for start,end in zip((0,)+internal,ends,strict=True)):
                candidates.append((exact_partition_objective(costs,ends,penalty),ends))
    return costs,min(value for value,_ in candidates)


@pytest.mark.parametrize('minimum,jump,dimensions',[
    (1,1,1),(1,4,2),(2,1,3),(2,3,1),(3,1,2),(3,2,3),
    (3,7,1),(4,1,3),(4,5,2),(5,2,1),(5,7,3),
])
def test_fraction_oracle_for_dyadic_multivariate_signals_and_grid_edges(minimum,jump,dimensions):
    rng = random.Random(38371+minimum*100+jump*10+dimensions)
    for n in (5,8,11):
        signal = [[rng.randrange(-8,9)/8 for _ in range(dimensions)] for _ in range(n)]
        algo = PeltMinSize(model='l2',min_size=minimum,jump=jump).fit(np.array(signal))
        for penalty in (0.0,0.125,1.5):
            costs,optimum = exact_grid_oracle(signal,minimum,jump,penalty)
            actual = algo.predict(penalty)
            assert actual[-1] == n
            assert all(end%jump==0 for end in actual[:-1])
            assert all(end-start>=minimum for start,end in zip([0]+actual[:-1],actual,strict=True))
            actual_cost = exact_partition_objective(costs,actual,penalty)
            assert float(actual_cost-optimum) <= 1e-12*max(1,float(abs(optimum)))


def test_backported_class_keeps_the_installed_upstream_class_unchanged():
    signal = np.array([0,9,2,8,3,0,10],dtype=float)
    assert PeltMinSize.__bases__ == (Pelt,)
    assert Pelt(model='l2',min_size=3,jump=1).fit_predict(signal,.1) == [4,7]
    assert PeltMinSize(model='l2',min_size=3,jump=1).fit_predict(signal,.1) == [3,7]


def test_private_partition_penalty_and_public_internal_boundary_penalty_differ_by_one_penalty():
    signal = np.array([0,0,0,0,10,10,10,10],dtype=float)
    private = PeltMinSize(model='l2',min_size=3,jump=1).fit(signal)._seg(.75)
    assert private == {(0,4):.75,(4,8):.75}
    public = pelt_l2(signal,.75)
    assert public['endpoints'] == [4,8]
    assert public['internal_boundaries'] == [4]
    assert public['sse'] == 0
    assert public['objective'] == .75
    assert sum(private.values()) == public['objective']+.75
    unsplit = pelt_l2([1.0]*9,8.25)
    assert unsplit['internal_boundaries'] == []
    assert unsplit['objective'] == 0


def test_repeated_private_partition_mutation_does_not_leak_prediction_state():
    signal = np.array([[0,1],[0,1],[0,1],[8,3],[8,3],[8,3]],dtype=float)
    original = signal.copy()
    detector = PeltMinSize(model='l2',min_size=3,jump=1).fit(signal)
    partition = detector._seg(.125)
    partition.clear()
    assert detector.predict(.125) == [3,6]
    assert detector.predict(10000) == [6]
    assert detector.predict(.125) == [3,6]
    np.testing.assert_array_equal(signal,original)
    assert detector.fit_predict(np.ones((7,3)),0) == [7]


@pytest.mark.parametrize('scale',[2.0**-20,1.0,2.0**20])
def test_unique_optimum_under_score_and_penalty_scale_changes(scale):
    signal = np.array([0,0,0,8,8,8,8,1,1,1],dtype=float)*scale
    penalty = .5*scale**2
    result = pelt_l2(signal,penalty,min_size=3)
    assert result['endpoints'] == [3,7,10]
    assert result['sse'] == 0
    assert result['objective'] == 2*penalty


def test_float_tie_and_finite_sse_validation_remain_deterministic():
    # Positive penalty and all-zero coordinates must not create spurious splits.
    for penalty in (0.0,2.0**-45,1.0):
        results = [pelt_l2(np.zeros((13,4)),penalty,min_size=3) for _ in range(3)]
        assert results[0] == results[1] == results[2]
        assert results[0]['endpoints'] == [13]
        assert results[0]['objective'] == 0
    with pytest.raises(InputError):
        pelt_l2([0,math.inf,0],1)
    with pytest.raises(ComputationError):
        pelt_l2([1e308,-1e308,1e308],1)


def test_ahas_still_rejects_nonunit_jump_even_though_private_pr_handles_it():
    signal = [0,1,0,0,1]
    assert PeltMinSize(model='l2',min_size=2,jump=2).fit_predict(np.array(signal,dtype=float),.1) == [5]
    with pytest.raises(InputError,match='jump'):
        pelt_l2(signal,.1,min_size=2,jump=2)


def test_accepted_numeric_unit_jump_is_normalized_for_dependency_range():
    integer = pelt_l2([0,0,0,10,10,10],1,jump=1)
    floating = pelt_l2([0,0,0,10,10,10],1,jump=1.0)
    assert floating == integer
    assert type(floating['jump']) is float


def test_exact_method_ast_matches_preserved_upstream_source():
    original = ast.parse((VENDOR/'ruptures_pr383_source.txt').read_text())
    source_class = next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='Pelt')
    source_method = next(node for node in source_class.body if isinstance(node,ast.FunctionDef) and node.name=='_seg')
    # Parse its class wrapper so indentation inside the verbatim method's
    # docstring remains identical; dedenting a method also changes string data.
    actual_class = ast.parse(inspect.getsource(PeltMinSize)).body[0]
    actual_method = next(node for node in actual_class.body if isinstance(node,ast.FunctionDef) and node.name=='_seg')
    assert ast.dump(actual_method,include_attributes=False) == ast.dump(source_method,include_attributes=False)


def test_preserved_source_and_metadata_bind_the_reviewed_commit():
    source = (VENDOR/'ruptures_pr383_source.txt').read_bytes()
    metadata = json.loads((VENDOR/'ruptures_pr383.json').read_bytes())
    assert metadata['commit'] == COMMIT
    assert metadata['source_sha256'] == hashlib.sha256(source).hexdigest()
    assert metadata['method_sha256'] == hashlib.sha256(inspect.getsource(PeltMinSize._seg).encode()).hexdigest()
    assert metadata['license_sha256'] == hashlib.sha256((VENDOR/'ruptures_LICENSE.txt').read_bytes()).hexdigest()
    assert metadata['pull_request'] == 'https://github.com/deepcharles/ruptures/pull/383'


def test_copied_upstream_tests_change_only_import_and_provenance_header():
    copied = (ROOT/'tests/vendor_pr383/test_pelt_min_size.py').read_text()
    original = copied.split('\n',4)[4]
    changed = 'from account_history_analyzer._vendor.ruptures_pr383 import PeltMinSize as Pelt'
    assert original.count(changed) == 1
    original = original.replace(changed,'from ruptures import Pelt')
    metadata = json.loads((VENDOR/'ruptures_pr383.json').read_bytes())
    assert hashlib.sha256(original.encode()).hexdigest() == metadata['upstream_tests_sha256']
