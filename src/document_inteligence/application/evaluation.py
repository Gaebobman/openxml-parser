"""Golden-label evaluation metrics.

Provides shared metric functions used by both the CLI evaluate script
and the regression test suite.
"""
from __future__ import annotations

from itertools import combinations


def kendall_tau(predicted: list[str], expected: list[str]) -> float:
    """Kendall's Tau-b between two orderings sharing the same element set.

    Returns 1.0 when the orderings are identical or there are fewer than 2
    common elements.
    """
    common = [e for e in expected if e in set(predicted)]
    if len(common) < 2:
        return 1.0
    pred_rank = {eid: i for i, eid in enumerate(predicted)}
    exp_rank = {eid: i for i, eid in enumerate(common)}
    concordant = 0
    discordant = 0
    for a, b in combinations(common, 2):
        pred_diff = pred_rank.get(a, 0) - pred_rank.get(b, 0)
        exp_diff = exp_rank[a] - exp_rank[b]
        if pred_diff * exp_diff > 0:
            concordant += 1
        elif pred_diff * exp_diff < 0:
            discordant += 1
    n_pairs = concordant + discordant
    if n_pairs == 0:
        return 1.0
    return (concordant - discordant) / n_pairs


def normalised_edit_distance(predicted: list[str], expected: list[str]) -> float:
    """1 - (levenshtein / max_len).  Higher is better."""
    m, n = len(predicted), len(expected)
    if m == 0 and n == 0:
        return 1.0
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if predicted[i - 1] == expected[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    max_len = max(m, n)
    return 1.0 - dp[m][n] / max_len


def relation_prf(
    predicted: list[dict], expected: list[dict]
) -> dict[str, dict[str, float]]:
    """Precision / Recall / F1 per relation type and ``_overall``."""

    def _key(r: dict) -> tuple[str, str, str]:
        return (r["type"], r["source"], r["target"])

    pred_set = {_key(r) for r in predicted}
    exp_set = {_key(r) for r in expected}
    tp = pred_set & exp_set
    fp = pred_set - exp_set
    fn = exp_set - pred_set

    all_types = {k[0] for k in pred_set | exp_set} | {"_overall"}
    result: dict[str, dict[str, float]] = {}
    for rtype in sorted(all_types):
        if rtype == "_overall":
            t_tp, t_fp, t_fn = len(tp), len(fp), len(fn)
        else:
            t_tp = sum(1 for k in tp if k[0] == rtype)
            t_fp = sum(1 for k in fp if k[0] == rtype)
            t_fn = sum(1 for k in fn if k[0] == rtype)
        precision = t_tp / max(t_tp + t_fp, 1)
        recall = t_tp / max(t_tp + t_fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        result[rtype] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": t_tp,
            "fp": t_fp,
            "fn": t_fn,
        }
    return result
