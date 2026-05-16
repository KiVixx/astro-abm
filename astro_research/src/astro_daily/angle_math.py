from __future__ import annotations


def normalize_360(value: float) -> float:
    return value % 360.0


def angular_diff_signed(a: float, b: float) -> float:
    return ((a - b + 180.0) % 360.0) - 180.0


def angular_distance(a: float, b: float) -> float:
    return abs(angular_diff_signed(a, b))
