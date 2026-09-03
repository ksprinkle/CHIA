"""Approved CHIA v0.1 zero-preserving percentile normalization.

This module is deliberately database-independent. CE-A02 may use it to
produce normalized_measure records only after its own implementation begins.
"""

from __future__ import annotations

from collections.abc import Iterable
from math import isnan
from typing import Optional


NORMALIZATION_METHOD = "county_percentile_rank_average"
METHODOLOGY_VERSION = "v0.1"


def zero_preserving_percentile(
    values: Iterable[Optional[float]],
) -> list[Optional[float]]:
    """Normalize one complete CHIA county-universe series to 0--100.

    Missing values remain ``None``. Valid zero values remain exactly ``0.0``.
    Positive values are ranked only among positive values using average ranks:

        ((average_rank - 1) / (n_positive - 1)) * 100

    For the approved ``n_positive == 1`` edge case, the sole positive value
    receives ``100.0``. It is necessarily the maximum positive observation.

    The caller must supply the complete county/county-equivalent universe;
    this function intentionally has no state, region, or subset grouping.
    """

    normalized: list[Optional[float]] = []
    positives: list[tuple[int, float]] = []

    for index, value in enumerate(values):
        if value is None or (isinstance(value, float) and isnan(value)):
            normalized.append(None)
            continue

        numeric_value = float(value)
        if numeric_value < 0:
            raise ValueError("Zero-preserving percentile requires non-negative values.")
        if numeric_value == 0:
            normalized.append(0.0)
            continue

        normalized.append(None)
        positives.append((index, numeric_value))

    positive_count = len(positives)
    if positive_count == 0:
        return normalized
    if positive_count == 1:
        normalized[positives[0][0]] = 100.0
        return normalized

    sorted_positives = sorted(positives, key=lambda item: item[1])
    position = 0
    while position < positive_count:
        group_end = position + 1
        while (
            group_end < positive_count
            and sorted_positives[group_end][1] == sorted_positives[position][1]
        ):
            group_end += 1

        # Ranks are one-based; equal positive values receive the average rank.
        average_rank = ((position + 1) + group_end) / 2
        score = ((average_rank - 1) / (positive_count - 1)) * 100
        for original_index, _ in sorted_positives[position:group_end]:
            normalized[original_index] = score
        position = group_end

    return normalized
