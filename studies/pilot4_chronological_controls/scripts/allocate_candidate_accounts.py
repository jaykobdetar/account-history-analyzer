"""Score-free, globally disjoint audit-pool allocation from metadata witnesses."""
from itertools import combinations, product
from metadata_feasibility import compatible, edge_cost, identity_order


def joint_witness(graphs,quotas):
    names=sorted(graphs); chosen={}
    def visit(position,used):
        if position==len(names):return dict(chosen)
        name=names[position]
        for pairs in combinations(graphs[name],quotas[name]):
            accounts={a for pair in pairs for a in pair}
            if len(accounts)!=2*quotas[name] or accounts&used:continue
            chosen[name]=list(pairs)
            result=visit(position+1,used|accounts)
            if result is not None:return result
        chosen.pop(name,None)
        return None
    return visit(0,set())


def allocate(strata,design):
    """Reserve an attainable capped witness, then add compatible edge endpoints.

    strata map fixed IDs02/04/05 to public/candidate_cells as in the census. The
    original physics edge is mandatory; the new per-pair caps remain two even
    when an explicitly reported feasibility deficit leaves a smaller witness.
    """
    names=['stratum-02','stratum-04','stratum-05']
    if set(strata)!=set(names):raise ValueError('The three registered strata are required')
    graphs={};costs={}
    for name in names:
        cells=strata[name]['candidate_cells'];nodes=sorted(cells,key=identity_order)
        edges=[(a,b) for i,a in enumerate(nodes) for b in nodes[i+1:] if compatible(cells[a],cells[b],design)]
        graphs[name]=edges
        costs[name]={edge:edge_cost(cells[edge[0]],cells[edge[1]],design) for edge in edges}
    if len(graphs['stratum-02'])!=1:raise ValueError('Original physics witness changed')
    quota_options=sorted(product(range(3),repeat=2),key=lambda q:(-sum(q),-min(q),-q[0],-q[1]))
    for linux,programming in quota_options:
        quotas={'stratum-02':1,'stratum-04':linux,'stratum-05':programming}
        witness=joint_witness(graphs,quotas)
        if witness is not None:break
    if witness is None:raise ValueError('Even original physics witness unavailable')
    assigned={name:{a for pair in witness[name] for a in pair} for name in names}
    reserved={name:set(accounts) for name,accounts in assigned.items()}
    for name in names[1:]:
        others=set().union(*(accounts for sid,accounts in assigned.items() if sid!=name))
        ordered=sorted(graphs[name],key=lambda e:(costs[name][e],identity_order(e[0]),identity_order(e[1])))
        for edge in ordered:
            if set(edge)&others or len(assigned[name]|set(edge))>12:continue
            assigned[name].update(edge)
    all_accounts=[a for accounts in assigned.values() for a in accounts]
    if len(all_accounts)!=len(set(all_accounts)) or len(all_accounts)>26:
        raise AssertionError('Global allocation is not disjoint')
    return {'assigned':{name:sorted(accounts,key=identity_order) for name,accounts in assigned.items()},
            'reserved_witness':witness,'reserved_witness_accounts':{name:sorted(v,key=identity_order) for name,v in reserved.items()},
            'attainable_reserved_block_counts':quotas,'planned_block_caps':{'stratum-02':1,'stratum-04':2,'stratum-05':2},
            'registered_target_deficits':{name:(1 if name=='stratum-02' else 2)-quotas[name] for name in names},
            'candidate_graph_edges':{name:len(edges) for name,edges in graphs.items()}}
