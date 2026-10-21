import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "eval_metrics", Path(__file__).resolve().parents[1] / "eval" / "metrics.py"
)
metrics = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(metrics)

RANKED = ["a#1", "b#2", "c#3", "d#4"]


def test_recall_at_k_any_of_gold():
    assert metrics.recall_at_k(RANKED, ["z#9", "c#3"], 3) == 1.0
    assert metrics.recall_at_k(RANKED, ["z#9", "c#3"], 2) == 0.0
    assert metrics.recall_at_k(RANKED, ["a#1"], 1) == 1.0


def test_recall_empty_gold_and_empty_ranking():
    assert metrics.recall_at_k(RANKED, [], 4) == 0.0
    assert metrics.recall_at_k([], ["a#1"], 5) == 0.0


def test_mrr_at_k_uses_first_gold_hit():
    assert metrics.mrr_at_k(RANKED, ["b#2", "d#4"], 4) == 0.5
    assert metrics.mrr_at_k(RANKED, ["d#4"], 3) == 0.0
    assert metrics.mrr_at_k(RANKED, ["a#1"], 1) == 1.0


def test_bootstrap_ci_constant_values():
    assert metrics.bootstrap_ci([1.0] * 10) == (1.0, 1.0, 1.0)


def test_bootstrap_ci_is_deterministic_and_brackets_mean():
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0]
    first = metrics.bootstrap_ci(values, n=500, seed=3)
    assert first == metrics.bootstrap_ci(values, n=500, seed=3)
    mean, lo, hi = first
    assert mean == pytest.approx(0.7)
    assert 0.0 <= lo <= mean <= hi <= 1.0


def test_bootstrap_ci_rejects_empty():
    with pytest.raises(ValueError):
        metrics.bootstrap_ci([])


def test_paired_bootstrap_diff_detects_clear_gap():
    a = [1.0] * 20
    b = [0.0] * 20
    diff, lo, hi = metrics.paired_bootstrap_diff(a, b)
    assert (diff, lo, hi) == (1.0, 1.0, 1.0)


def test_paired_bootstrap_diff_straddles_zero_when_noisy():
    a = [1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0]
    b = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0]
    diff, lo, hi = metrics.paired_bootstrap_diff(a, b)
    assert diff == 0.0
    assert lo < 0.0 < hi


def test_paired_bootstrap_diff_length_mismatch():
    with pytest.raises(ValueError):
        metrics.paired_bootstrap_diff([1.0], [1.0, 0.0])
