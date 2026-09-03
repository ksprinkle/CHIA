"""Deterministic CE-A00 fixtures for approved CHIA v0.1 normalization."""

from __future__ import annotations

import math
import unittest

from app.services.normalization import (
    METHODOLOGY_VERSION,
    NORMALIZATION_METHOD,
    zero_preserving_percentile,
)


# Scores are bounded to 0--100 and use ordinary IEEE-754 arithmetic. An
# absolute tolerance of 1e-12 is well below displayed precision while allowing
# harmless floating-point representation differences.
ABSOLUTE_TOLERANCE = 1e-12


class ZeroPreservingPercentileFixturesTest(unittest.TestCase):
    def assert_scores_equal(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for actual_value, expected_value in zip(actual, expected):
            if expected_value is None:
                self.assertIsNone(actual_value)
            else:
                self.assertIsNotNone(actual_value)
                self.assertTrue(
                    math.isclose(
                        actual_value,
                        expected_value,
                        rel_tol=0.0,
                        abs_tol=ABSOLUTE_TOLERANCE,
                    ),
                    f"{actual_value!r} != {expected_value!r}",
                )

    def test_method_identity(self):
        self.assertEqual(NORMALIZATION_METHOD, "county_percentile_rank_average")
        self.assertEqual(METHODOLOGY_VERSION, "v0.1")

    def test_all_positive_values(self):
        self.assert_scores_equal(
            zero_preserving_percentile([1, 2, 3]),
            [0.0, 50.0, 100.0],
        )

    def test_valid_zero_values_remain_exactly_zero(self):
        self.assert_scores_equal(
            zero_preserving_percentile([0, 1, 2]),
            [0.0, 0.0, 100.0],
        )

    def test_missing_values_remain_missing(self):
        self.assert_scores_equal(
            zero_preserving_percentile([None, 1, 2, float("nan")]),
            [None, 0.0, 100.0, None],
        )

    def test_tied_positive_values_receive_average_rank(self):
        self.assert_scores_equal(
            zero_preserving_percentile([1, 2, 2, 3]),
            [0.0, 50.0, 50.0, 100.0],
        )

    def test_tied_zero_values_remain_exactly_zero(self):
        self.assert_scores_equal(
            zero_preserving_percentile([0, 0, 1, 2]),
            [0.0, 0.0, 0.0, 100.0],
        )

    def test_known_mixed_zero_positive_fixture(self):
        self.assert_scores_equal(
            zero_preserving_percentile([0, 0, 1, 2, 2, 4, None]),
            [0.0, 0.0, 0.0, 50.0, 50.0, 100.0, None],
        )

    def test_single_positive_value_receives_100(self):
        self.assert_scores_equal(
            zero_preserving_percentile([0, None, 7]),
            [0.0, None, 100.0],
        )

    def test_complete_universe_is_used_not_a_subset(self):
        # In the full universe, 4 has rank 2 of 3 positives, so it is 50.
        # Ranking the [2, 4] subset would incorrectly produce 100 for 4.
        self.assert_scores_equal(
            zero_preserving_percentile([0, 2, 4, 8]),
            [0.0, 0.0, 50.0, 100.0],
        )

    def test_validation_properties(self):
        scores = zero_preserving_percentile([None, 0, 1, 2, 2, 4])
        self.assertIsNone(scores[0])
        self.assertEqual(scores[1], 0.0)

        positive_scores = [score for score in scores[2:] if score is not None]
        self.assertTrue(all(0.0 <= score <= 100.0 for score in positive_scores))
        self.assertEqual(max(positive_scores), 100.0)
        self.assertEqual(scores[3], scores[4])


if __name__ == "__main__":
    unittest.main()
