from __future__ import annotations

import math

import numpy as np


def benjamini_hochberg(p_values) -> list[float]:
    values = np.asarray([math.nan if value is None else float(value) for value in p_values], dtype=float)
    q_values = np.full(len(values), np.nan)
    valid_indexes = np.where(~np.isnan(values))[0]
    if len(valid_indexes) == 0:
        return q_values.tolist()
    valid = values[valid_indexes]
    order = np.argsort(valid)
    ranked = valid[order]
    m = len(ranked)
    adjusted = np.empty(m)
    running = 1.0
    for rank in range(m, 0, -1):
        running = min(running, ranked[rank - 1] * m / rank)
        adjusted[rank - 1] = running
    restored = np.empty(m)
    restored[order] = adjusted
    q_values[valid_indexes] = restored
    return q_values.tolist()
