"""Exact Pelt._seg backport from ruptures PR #383.

Source commit: a28574d9e63b0c2a966e176a1d049d3c9deaaaaf.
Only the class/import scaffolding is local. The method below is verbatim.
The remaining API and L2 cost come from the locked ruptures 1.1.10 package.
Copyright (c) 2017-2021, ENS Paris-Saclay, CNRS.
BSD-2-Clause: see ruptures_LICENSE.txt and ruptures_pr383.json alongside this file.
"""
from ruptures import Pelt


class PeltMinSize(Pelt):
    """Private pinned backport; never modifies the installed ruptures module."""

    def _seg(self, pen: float) -> dict[tuple[int, int], float]:
        """Compute the optimal penalized partition with delayed pruning.

        A start dominated at ``s`` stays eligible until ``s + min_size``.
        Only then can ``s`` legally start the replacement segment.
        As in the usual PELT rule, this requires the cost inequality
        ``C(r, u) >= C(r, s) + C(s, u)`` on legal segments.

        Args:
            pen (float): Penalty per segment. This differs from a penalty per
                change point by the same constant for every partition.

        Returns:
            dict: Mapping from segment bounds to segment cost plus penalty.
        """
        partitions = {0: {(0, 0): 0}}
        admissible = []
        prune_at = {}

        endpoints = [
            k for k in range(0, self.n_samples, self.jump) if k >= self.min_size
        ]
        endpoints.append(self.n_samples)

        # Each possible start enters once, only after a legal final segment
        # can follow it. Exclude n: it cannot start a nonempty segment.
        pending = iter([0] + endpoints[:-1])
        next_start = next(pending, None)

        for bkp in endpoints:
            while next_start is not None and next_start <= bkp - self.min_size:
                admissible.append(next_start)
                next_start = next(pending, None)

            # A witness s can replace a start only at endpoints u >= s+m.
            # Compare sample coordinates, not the number of grid iterations;
            # the final endpoint can lie off the jump grid.
            admissible = [
                t for t in admissible if t not in prune_at or bkp < prune_at[t]
            ]

            candidates = []
            for t in admissible:
                partition = partitions[t].copy()
                partition[(t, bkp)] = self.cost.error(t, bkp) + pen
                candidates.append((t, partition, sum(partition.values())))

            _, best_partition, best_value = min(candidates, key=lambda item: item[2])
            partitions[bkp] = best_partition

            if bkp != self.n_samples:
                for t, _, value in candidates:
                    if value > best_value + pen:
                        # Endpoints increase, so the first witness gives the
                        # earliest safe expiry. Later witnesses cannot extend it.
                        prune_at.setdefault(t, bkp + self.min_size)

        best_partition = partitions[self.n_samples]
        del best_partition[(0, 0)]
        return best_partition
