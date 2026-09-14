"""Exact segmented longest-substring matching and deterministic work reservations.

The suffix automaton indexes actual token equality. A separator that cannot equal
a lexical string prevents crossing left segments; right segments reset the scan.
No frequent-token suppression, hashing surrogate, sampling or approximate match
enters a decision. Earliest end occurrences recover the specified evidence ties.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class ReuseLimit(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class WorkMeter:
    """Reserve logical work/size before an operation, never exceeding a limit.

    A failed bulk reservation consumes no units. Counters describe deterministic
    reservations, not elapsed instructions or probabilistic complexity estimates.
    """
    NAMES = ('work_units','index_postings','evidence_tokens','evidence_codepoints')

    def __init__(self, config: Mapping):
        self.limits = {'max_'+name:config['max_'+name] for name in self.NAMES}
        self.usage = {name:0 for name in self.NAMES}

    def charge(self, name: str, amount: int = 1) -> None:
        if self.usage[name]+amount > self.limits['max_'+name]:
            raise ReuseLimit('max_'+name)
        self.usage[name] += amount


class _Unmetered:
    def charge(self, name: str, amount: int = 1) -> None:
        pass


@dataclass(frozen=True)
class TokenMatch:
    size: int
    left_segment: int
    right_segment: int
    left_start: int
    right_start: int


class TokenMatcher:
    """Reusable index for one left record; exact global longest-match tie order.

    Work is linear in index/scan tokens and automaton transition changes, including
    clones, with linear counting-sort occurrence propagation. A caller may reuse
    this index for consecutive pairs sharing the left record, then release it.
    """
    def __init__(self, left: Sequence[Sequence[str]], minimum: int, meter: WorkMeter | None = None):
        self.left = left
        self.minimum = minimum
        self.meter = meter or _Unmetered()
        self.token_count = sum(map(len,left))
        self.transitions: list[dict] | None = None

    def _build(self) -> None:
        meter = self.meter
        transitions: list[dict] = [{}]
        links, lengths, earliest = [-1], [0], [None]
        last = 0

        def extend(token: str | None, occurrence: tuple[int,int] | None) -> None:
            nonlocal last
            meter.charge('work_units')
            current = len(transitions)
            transitions.append({}); links.append(0); lengths.append(lengths[last]+1); earliest.append(occurrence)
            previous = last
            while previous!=-1 and token not in transitions[previous]:
                meter.charge('work_units')
                transitions[previous][token] = current
                previous = links[previous]
            if previous!=-1:
                meter.charge('work_units')
                following = transitions[previous][token]
                if lengths[previous]+1==lengths[following]:
                    links[current] = following
                else:
                    meter.charge('work_units',1+len(transitions[following]))
                    clone = len(transitions)
                    transitions.append(transitions[following].copy())
                    lengths.append(lengths[previous]+1); links.append(links[following]); earliest.append(None)
                    while previous!=-1 and transitions[previous].get(token)==following:
                        meter.charge('work_units')
                        transitions[previous][token] = clone
                        previous = links[previous]
                    links[following] = links[current] = clone
            last = current

        for segment_index,segment in enumerate(self.left):
            meter.charge('work_units')
            if len(segment)<self.minimum:
                continue
            if last:
                extend(None,None)
            for offset,token in enumerate(segment):
                extend(token,(segment_index,offset))
        # Linear counting sort by longest represented length; no token ordering
        # or interpreter hash order influences propagation or tie selection.
        meter.charge('work_units',3*len(transitions)+lengths[last]+1)
        counts = [0]*(lengths[last]+1)
        for length in lengths:
            counts[length] += 1
        for i in range(1,len(counts)):
            counts[i] += counts[i-1]
        order = [0]*len(transitions)
        for state,length in enumerate(lengths):
            counts[length] -= 1
            order[counts[length]] = state
        for state in reversed(order):
            parent = links[state]
            if parent>=0 and earliest[state] is not None:
                if earliest[parent] is None or earliest[state]<earliest[parent]:
                    earliest[parent] = earliest[state]
        self.transitions,self.links,self.lengths,self.earliest = transitions,links,lengths,earliest

    def find(self, right: Sequence[Sequence[str]]) -> TokenMatch | None:
        meter = self.meter
        meter.charge('work_units',self.token_count+sum(map(len,right))+len(self.left)+len(right))
        # Equal complete segment sequences admit a proven full-segment optimum;
        # the general index below also covers nonidentical low-entropy sequences.
        if self.left==right:
            eligible = [(len(segment),index) for index,segment in enumerate(self.left) if len(segment)>=self.minimum]
            if not eligible:
                return None
            size,index = min(eligible,key=lambda item:(-item[0],item[1]))
            return TokenMatch(size,index,index,0,0)
        if self.transitions is None:
            self._build()
        transitions,links,lengths,earliest = self.transitions,self.links,self.lengths,self.earliest
        best = None
        for ri,segment in enumerate(right):
            meter.charge('work_units')
            if len(segment)<self.minimum:
                continue
            state = size = 0
            for end,token in enumerate(segment):
                meter.charge('work_units')
                while state and token not in transitions[state]:
                    meter.charge('work_units')
                    state = links[state]
                    size = min(size,lengths[state])
                following = transitions[state].get(token)
                if following is None:
                    state = size = 0
                    continue
                state = following
                size += 1
                if size>=self.minimum:
                    li,left_end = earliest[state]
                    key = (-size,li,ri,left_end-size+1,end-size+1)
                    if best is None or key<best:
                        best = key
        return None if best is None else TokenMatch(-best[0],*best[1:])
