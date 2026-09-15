"""Exact metadata matching with the same cardinality/cost/identity objectives.

This optional study-only backend never imports AHAS. Integer weights preserve
the complete rational cost order and lexicographic tie rule; no float solver.
"""
from fractions import Fraction
from math import lcm
import networkx as nx


def exact_matching(nodes,edges,check=lambda:None):
    if nx.__version__!='3.5':raise ValueError('Pinned study-only NetworkX3.5 required')
    nodes=list(nodes);order={node:i for i,node in enumerate(nodes)}
    if len(order)!=len(nodes):raise ValueError('Duplicate graph vertex')
    costs={}
    for (left,right),cost in edges.items():
        if left==right or left not in order or right not in order or isinstance(cost,(bool,float)):
            raise ValueError('Invalid vertex or inexact cost')
        pair=tuple(sorted((order[left],order[right])))
        if pair in costs:raise ValueError('Duplicate undirected edge')
        costs[pair]=Fraction(cost)
    ordered=sorted(costs);denominator=1
    for cost in costs.values():denominator=lcm(denominator,cost.denominator)
    # One integer cost unit dominates every possible tie-bit difference.
    base=1<<len(ordered)
    graph=nx.Graph();graph.add_nodes_from(range(len(nodes)))
    for rank,pair in enumerate(ordered):
        if rank%256==0:check()
        scaled=costs[pair]*denominator
        if scaled.denominator!=1:raise AssertionError('Rational cost scaling failed')
        graph.add_edge(*pair,weight=-scaled.numerator*base+(1<<(len(ordered)-rank-1)))
    check()
    matching=nx.max_weight_matching(graph,maxcardinality=True,weight='weight')
    check()
    pairs=sorted(tuple(sorted(pair)) for pair in matching)
    if len({n for pair in pairs for n in pair})!=len(pairs)*2 or any(pair not in costs for pair in pairs):
        raise AssertionError('Invalid matching returned')
    return {'cardinality':len(pairs),'cost':sum((costs[p] for p in pairs),Fraction()),
            'pairs':[(nodes[a],nodes[b]) for a,b in pairs],'dp_states':0}
