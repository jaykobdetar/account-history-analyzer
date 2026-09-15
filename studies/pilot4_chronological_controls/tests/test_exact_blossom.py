from fractions import Fraction
from itertools import combinations
from pathlib import Path
import random
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from exact_blossom import exact_matching
from metadata_feasibility import exact_matching as subset_matching


class ExactBlossomTests(unittest.TestCase):
    def test_all_graphs_on_five_vertices_and_three_exact_cost_patterns(self):
        nodes=['e','d','c','b','a'];possible=list(combinations(nodes,2))
        for mask in range(1<<len(possible)):
            for pattern in range(3):
                edges={pair:(Fraction(0) if pattern==0 else Fraction((i%3)-1,7) if pattern==1 else Fraction(i+1,1000000000003))
                       for i,pair in enumerate(possible) if mask>>i&1}
                expected=subset_matching(nodes,edges);actual=exact_matching(nodes,edges)
                self.assertEqual((actual['cardinality'],actual['cost'],actual['pairs']),
                                 (expected['cardinality'],expected['cost'],expected['pairs']))

    def test_seeded_larger_general_graphs_against_subset_algorithm(self):
        rng=random.Random(739180)
        for n in range(6,13):
            for trial in range(15):
                nodes=list(range(n));edges={pair:Fraction(rng.randrange(-10,11),rng.choice([7,9,123456789]))
                                           for pair in combinations(nodes,2) if rng.random()<.6}
                expected=subset_matching(nodes,edges);actual=exact_matching(nodes,edges)
                self.assertEqual((actual['cardinality'],actual['cost'],actual['pairs']),
                                 (expected['cardinality'],expected['cost'],expected['pairs']))

    def test_maximum_cardinality_precedes_cost_even_with_negative_weights(self):
        result=exact_matching('abcd',{('a','b'):Fraction(1000000),('c','d'):Fraction(1000000),('a','c'):Fraction(0)})
        self.assertEqual(result['pairs'],[('a','b'),('c','d')])

    def test_float_and_repeated_edge_rejected(self):
        with self.assertRaises(ValueError):exact_matching('ab',{('a','b'):0.1})
        with self.assertRaises(ValueError):exact_matching('ab',{('a','b'):1,('b','a'):1})


if __name__=='__main__':unittest.main()
