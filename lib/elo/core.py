from __future__ import annotations

from typing import Tuple


def calculate_expected_score(rating_player: float, rating_opponent: float, rating_width: float = 400.0) -> float:
    exponent = (rating_opponent - rating_player) / rating_width
    return 1.0 / (1.0 + 10.0 ** exponent)


def apply_result(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k_factor: float = 32.0,
    rating_width: float = 400.0,
) -> Tuple[float, float]:
    expected_a = calculate_expected_score(rating_a, rating_b, rating_width=rating_width)
    expected_b = calculate_expected_score(rating_b, rating_a, rating_width=rating_width)
    new_a = rating_a + k_factor * (score_a - expected_a)
    new_b = rating_b + k_factor * ((1.0 - score_a) - expected_b)
    return new_a, new_b


def update_ratings(rating_winner: float, rating_loser: float, k_factor: float = 32.0, rating_width: float = 400.0) -> Tuple[float, float]:
    expected_winner = calculate_expected_score(rating_winner, rating_loser, rating_width=rating_width)
    expected_loser = calculate_expected_score(rating_loser, rating_winner, rating_width=rating_width)
    new_winner = rating_winner + k_factor * (1.0 - expected_winner)
    new_loser = rating_loser + k_factor * (0.0 - expected_loser)
    return new_winner, new_loser


