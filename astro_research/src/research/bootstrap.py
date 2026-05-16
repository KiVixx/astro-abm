from __future__ import annotations

import math

import numpy as np


def bootstrap_ci(values, *, samples: int = 1000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    array = _clean_array(values)
    if len(array) == 0:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(array, size=len(array), replace=True))) for _ in range(samples)]
    return (
        float(np.quantile(means, alpha / 2)),
        float(np.quantile(means, 1 - alpha / 2)),
    )


def permutation_p_value(event_values, baseline_values, *, samples: int = 1000, seed: int = 42) -> float:
    event = _clean_array(event_values)
    baseline = _clean_array(baseline_values)
    if len(event) == 0 or len(baseline) == 0:
        return math.nan
    observed = abs(float(np.mean(event) - np.mean(baseline)))
    combined = np.concatenate([event, baseline])
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(samples):
        shuffled = rng.permutation(combined)
        simulated = abs(float(np.mean(shuffled[: len(event)]) - np.mean(shuffled[len(event) :])))
        if simulated >= observed:
            hits += 1
    return float((hits + 1) / (samples + 1))


def _clean_array(values) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return array[~np.isnan(array)]
