"""Independent synthetic objective oracles for the optional study-only matcher."""
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import random
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from exact_blossom import exact_matching


def enumerate_matchings(remaining,edges):
    if not remaining:
        yield ();return
    first,*rest=remaining
    yield from enumerate_matchings(rest,edges)
    for other in rest:
        edge=tuple(sorted((first,other)))
        if edge in edges:
            for tail in enumerate_matchings([v for v in rest if v!=other],edges):
                yield tuple(sorted((edge,)+tail))


def oracle(nodes,edges):
    indices={node:i for i,node in enumerate(nodes)}
    costs={tuple(sorted((indices[a],indices[b]))):Fraction(w) for (a,b),w in edges.items()}
    best=min((-len(pairs),sum((costs[p] for p in pairs),Fraction()),pairs)
             for pairs in enumerate_matchings(list(range(len(nodes))),costs))
    return -best[0],best[1],[(nodes[a],nodes[b]) for a,b in best[2]]


def objective(result):return result['cardinality'],result['cost'],result['pairs']


def test_reversed_endpoint_and_node_order_with_unmatched_vertex():
    nodes=['z','a','t','b','isolated']
    edges={('a','z'):0,('t','z'):0,('b','a'):0,('b','t'):0}
    assert objective(exact_matching(nodes,edges))==oracle(nodes,edges)==(2,Fraction(),[('z','a'),('t','b')])


def test_lexicographic_bits_select_first_differing_edge_not_sum_of_edge_ranks():
    nodes=list(range(6))
    edges={p:Fraction() for p in combinations(nodes,2)}
    result=exact_matching(nodes,edges)
    assert result['pairs']==[(0,1),(2,3),(4,5)]
    assert objective(result)==oracle(nodes,edges)


def test_rational_cost_precedes_arbitrarily_large_lexicographic_preference():
    nodes=list(range(8));edges={p:Fraction() for p in combinations(nodes,2)}
    # The lexicographically first edge has an extremely small exact penalty.
    edges[0,1]=Fraction(1,2**4096*3**53)
    result=exact_matching(nodes,edges)
    assert result['cost']==0 and result['pairs'][0]==(0,2)
    assert objective(result)==oracle(nodes,edges)


def test_cardinality_precedes_huge_positive_cost_and_negative_edge_attraction():
    nodes=list('abcdefg')
    edges={('a','b'):Fraction(-10**200),('a','c'):Fraction(10**200,3),
           ('b','d'):Fraction(10**200,7),('e','f'):Fraction(11,13)}
    assert objective(exact_matching(nodes,edges))==oracle(nodes,edges)
    assert exact_matching(nodes,edges)['cardinality']==3


def test_140_seeded_general_graphs_against_unrestricted_enumeration():
    rng=random.Random(584139)
    for n in range(3,10):
        for trial in range(20):
            nodes=list(range(n));rng.shuffle(nodes)
            edges={p:Fraction(rng.randrange(-3,4),rng.choice([1,3,11,101,10**70+33]))
                   for p in combinations(nodes,2) if rng.random()<.65}
            assert objective(exact_matching(nodes,edges))==oracle(nodes,edges)


def test_empty_graph_and_isolated_vertices_have_exact_zero_objective():
    for nodes in ([],['one'],list(range(10))):
        assert objective(exact_matching(nodes,{}))==(0,Fraction(),[])


@pytest.mark.parametrize('nodes,edges',[
    (['a','a'],{}),(['a'],{('a','a'):0}),(['a'],{('a','b'):0}),
    (['a','b'],{('a','b'):True}),(['a','b'],{('a','b'):float('nan')}),
    (['a','b'],{('a','b'):Fraction(1),('b','a'):Fraction(1)}),
])
def test_invalid_graph_or_inexact_inputs_rejected(nodes,edges):
    with pytest.raises(ValueError):exact_matching(nodes,edges)


def test_bounded_check_interrupt_propagates_before_solver():
    def stop():raise TimeoutError('synthetic metadata budget')
    with pytest.raises(TimeoutError):exact_matching('ab',{('a','b'):0},check=stop)
