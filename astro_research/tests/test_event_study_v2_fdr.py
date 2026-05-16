from __future__ import annotations

from research.multiple_testing import benjamini_hochberg


def test_fdr_group_input_is_order_preserving():
    q_values = benjamini_hochberg([0.01, 0.20, 0.03])

    assert q_values[0] <= q_values[1]
    assert len(q_values) == 3
