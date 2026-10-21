"""Pure retrieval metrics over section_ids, plus bootstrap helpers.

A question counts as a hit when any of its acceptable gold section_ids shows up
in the ranked list. Per-question functions return a number; average them (or
pass them to ``bootstrap_ci``) for a run-level score.
"""

import random
from collections.abc import Iterable, Sequence


def first_hit_rank(
    ranked: Sequence[str], gold: Iterable[str], k: int | None = None
) -> int | None:
    """1-based rank of the first ranked id that is in gold within the top k, else None."""
    gold_set = set(gold)
    for rank, sid in enumerate(ranked if k is None else ranked[:k], start=1):
        if sid in gold_set:
            return rank
    return None


def recall_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    """1.0 if any gold id is in the top k, else 0.0 (any-of matching)."""
    return 1.0 if first_hit_rank(ranked, gold, k) is not None else 0.0


def mrr_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    """Reciprocal rank of the first gold id in the top k, 0.0 if none."""
    rank = first_hit_rank(ranked, gold, k)
    return 0.0 if rank is None else 1.0 / rank


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted list, q in [0, 1]."""
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def bootstrap_ci(
    values: Sequence[float], n: int = 2000, seed: int = 0, alpha: float = 0.05
) -> tuple[float, float, float]:
    """Mean and percentile bootstrap (1 - alpha) interval: (mean, lo, hi)."""
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    size = len(values)
    means = sorted(
        _mean([values[rng.randrange(size)] for _ in range(size)]) for _ in range(n)
    )
    return (
        _mean(values),
        _percentile(means, alpha / 2),
        _percentile(means, 1 - alpha / 2),
    )


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    n: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Mean of (a - b) over paired questions with a bootstrap interval: (diff, lo, hi).

    The interval excluding 0 means the gap between the two systems is unlikely
    to be question sampling noise.
    """
    if len(a) != len(b):
        raise ValueError("paired_bootstrap_diff needs equal-length inputs")
    return bootstrap_ci([x - y for x, y in zip(a, b)], n=n, seed=seed, alpha=alpha)
