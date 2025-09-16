from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Tuple


def parse_bool(value: str) -> bool:
    text = (value or "").strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def build_model_id(provider: Optional[str], version: Optional[str]) -> str:
    provider = (provider or "").strip()
    version = (version or "").strip()
    if provider and version:
        return f"{provider}:{version}"
    return version or provider or "unknown"


def determine_outcome(row: Dict[str, str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Returns (outcome, a_model_id, b_model_id)
    a_provider = row.get("model_a_provider")
    a_version = row.get("model_a_version")
    b_provider = row.get("model_b_provider")
    b_version = row.get("model_b_version")
    a_id = row.get("output_a_id")
    b_id = row.get("output_b_id")
    winner_id = row.get("winner_id")
    winner_choice = (row.get("winner_choice") or "").strip().lower()
    raw_is_tie = (row.get("is_tie", "") or "").strip()
    is_tie = parse_bool(raw_is_tie) if raw_is_tie != "2" else False

    model_a = build_model_id(a_provider, a_version)
    model_b = build_model_id(b_provider, b_version)

    if raw_is_tie == "2":
        return "both_bad", model_a, model_b

    if is_tie:
        return "tie", model_a, model_b

    if winner_id and a_id and winner_id == a_id:
        return "left", model_a, model_b
    if winner_id and b_id and winner_id == b_id:
        return "right", model_a, model_b

    if winner_choice in {"a", "left"}:
        return "left", model_a, model_b
    if winner_choice in {"b", "right"}:
        return "right", model_a, model_b
    if winner_choice in {"tie", "both"}:
        return "tie", model_a, model_b

    return None, model_a, model_b


def process_csv_to_bt(
    csv_path: Path,
    tie_mode: str = "half",  # "half" => count tie as 0.5 win to each; "skip" => ignore ties
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, float]]]:
    # wins[i][j] = number of wins of i over j
    wins: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    # totals[i][j] = total games between i and j
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            outcome, model_a, model_b = determine_outcome(row)
            if not outcome or not model_a or not model_b:
                continue
            if model_a == model_b:
                continue

            if outcome == "both_bad":
                continue
            elif outcome == "left":
                wins[model_a][model_b] += 1.0
                totals[model_a][model_b] += 1.0
                totals[model_b][model_a] += 1.0
            elif outcome == "right":
                wins[model_b][model_a] += 1.0
                totals[model_a][model_b] += 1.0
                totals[model_b][model_a] += 1.0
            elif outcome == "tie":
                if tie_mode == "half":
                    wins[model_a][model_b] += 0.5
                    wins[model_b][model_a] += 0.5
                    totals[model_a][model_b] += 1.0
                    totals[model_b][model_a] += 1.0

    return wins, totals


def fit_bt_mm(
    wins: Dict[str, Dict[str, float]],
    totals: Dict[str, Dict[str, float]],
    max_iter: int = 5000,
    tol: float = 1e-9,
) -> Dict[str, float]:
    # p_i^{new} = w_i / sum_j n_ij / (p_i + p_j)
    # Normalize mean(log p)=0 for identifiability
    players = sorted({i for i in wins.keys()} | {j for i in wins for j in wins[i].keys()})
    if not players:
        return {}
    p = {i: 1.0 for i in players}

    def total_wins(i: str) -> float:
        return sum(wins.get(i, {}).values())

    def denom(i: str) -> float:
        d = 0.0
        for j, n_ij in totals.get(i, {}).items():
            if n_ij <= 0:
                continue
            d += n_ij / max(p[i] + p[j], 1e-15)
        return d

    for _ in range(max_iter):
        p_new = {}
        max_rel_change = 0.0
        for i in players:
            w_i = total_wins(i)
            d_i = denom(i)
            if d_i <= 0:
                p_new[i] = p[i]
            else:
                p_new[i] = max(w_i / d_i, 1e-15)
            if p[i] > 0:
                max_rel_change = max(max_rel_change, abs(p_new[i] - p[i]) / p[i])

        mean_log = sum(math.log(max(p_new[i], 1e-15)) for i in players) / float(len(players))
        for i in players:
            p_new[i] = p_new[i] / math.exp(mean_log)

        p = p_new
        if max_rel_change < tol:
            break

    return p


def convert_bt_to_elo(p: Dict[str, float], base: float = 1000.0) -> Dict[str, float]:
    c = 400.0 / math.log(10.0)
    players = list(p.keys())
    if not players:
        return {}
    mean_log = sum(math.log(max(p[i], 1e-15)) for i in players) / float(len(players))
    elos = {}
    for i in players:
        elos[i] = c * (math.log(max(p[i], 1e-15)) - mean_log) + base
    return elos


