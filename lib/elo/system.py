from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from .core import apply_result, calculate_expected_score, update_ratings


@dataclass
class EloRatingSystem:
    initial_rating: float = 1000.0
    k_factor: float = 32.0
    rating_width: float = 400.0
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None

    ratings: Dict[str, float] = field(default_factory=dict)

    def get_rating(self, model_id: str) -> float:
        if model_id not in self.ratings:
            self.ratings[model_id] = float(self.initial_rating)
        return self.ratings[model_id]

    def set_rating(self, model_id: str, rating: float) -> None:
        self.ratings[model_id] = self._clamp(rating)

    def expected(self, model_a: str, model_b: str) -> float:
        return calculate_expected_score(self.get_rating(model_a), self.get_rating(model_b), rating_width=self.rating_width)

    def update_by_score(self, model_a: str, model_b: str, score_a: float) -> Tuple[float, float]:
        new_a, new_b = apply_result(
            self.get_rating(model_a),
            self.get_rating(model_b),
            score_a,
            k_factor=self.k_factor,
            rating_width=self.rating_width,
        )
        self.set_rating(model_a, new_a)
        self.set_rating(model_b, new_b)
        return new_a, new_b

    def update_outcome(self, model_left: str, model_right: str, outcome: str) -> Tuple[float, float]:
        # outcome in {"left", "right", "tie", "both_bad"}
        if outcome == "tie":
            return self.update_by_score(model_left, model_right, 0.5)
        if outcome == "both_bad":
            return self.get_rating(model_left), self.get_rating(model_right)
        if outcome == "left":
            return self.update_by_score(model_left, model_right, 1.0)
        if outcome == "right":
            return self.update_by_score(model_left, model_right, 0.0)
        raise ValueError(f"Unknown outcome: {outcome}")

    def batch_update(self, matches: Iterable[Tuple[str, str, float]]) -> None:
        # Iterable of (model_a, model_b, score_a)
        for model_a, model_b, score_a in matches:
            self.update_by_score(model_a, model_b, score_a)

    def rankings(self) -> List[Dict[str, float]]:
        items = sorted(self.ratings.items(), key=lambda kv: kv[1], reverse=True)
        return [{"id": mid, "rating": rating} for mid, rating in items]

    def _clamp(self, rating: float) -> float:
        if self.min_rating is not None:
            rating = max(rating, self.min_rating)
        if self.max_rating is not None:
            rating = min(rating, self.max_rating)
        return rating


