"""
Elo rating system utilities.

This module provides small, focused helpers to compute expected scores and
updated Elo ratings after a head-to-head match.
"""

from dataclasses import dataclass
from typing import Tuple


DEFAULT_K_FACTOR: int = 32


def calculate_expected_score(rating_player: float, rating_opponent: float) -> float:
    """Return the expected score for a player facing an opponent.

    Uses the classic Elo expected score formula:
        E = 1 / (1 + 10^((R_opponent - R_player) / 400))
    """

    exponent = (rating_opponent - rating_player) / 400.0
    return 1.0 / (1.0 + 10.0 ** exponent)


def update_ratings(
    rating_winner: float,
    rating_loser: float,
    k_factor: int = DEFAULT_K_FACTOR,
) -> Tuple[float, float]:
    """Return new ratings after a decisive match where winner beats loser.

    The winner receives a score of 1, the loser receives 0.
    """

    expected_winner = calculate_expected_score(rating_winner, rating_loser)
    expected_loser = calculate_expected_score(rating_loser, rating_winner)

    new_winner = rating_winner + k_factor * (1.0 - expected_winner)
    new_loser = rating_loser + k_factor * (0.0 - expected_loser)
    return new_winner, new_loser


def apply_result(
    rating_a: float,
    rating_b: float,
    score_a: float,
    k_factor: int = DEFAULT_K_FACTOR,
) -> Tuple[float, float]:
    """Generic Elo update where score_a is in [0, 0.5, 1] (loss, draw, win).

    Args:
        rating_a: Elo for player A.
        rating_b: Elo for player B.
        score_a: Observed score for A (1 win, 0 loss, 0.5 draw).
        k_factor: Sensitivity multiplier for updates.

    Returns:
        Tuple(new_rating_a, new_rating_b)
    """

    expected_a = calculate_expected_score(rating_a, rating_b)
    expected_b = calculate_expected_score(rating_b, rating_a)

    new_a = rating_a + k_factor * (score_a - expected_a)
    new_b = rating_b + k_factor * ((1.0 - score_a) - expected_b)
    return new_a, new_b


