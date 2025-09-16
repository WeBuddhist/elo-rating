from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _add_project_root_to_path() -> None:
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_add_project_root_to_path()

from lib.elo import EloRatingSystem  # noqa: E402


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

    # Special case: "2" means both are bad (not a tie)
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


def process_csv(
    csv_path: Path,
    initial_rating: float,
    k_factor: float,
    rating_width: float,
) -> Tuple[EloRatingSystem, Dict[str, Dict[str, float]]]:
    elo = EloRatingSystem(initial_rating=initial_rating, k_factor=k_factor, rating_width=rating_width)
    stats: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "appearances_total": 0,
            "appearances_left": 0,
            "appearances_right": 0,
            "both_bad": 0,
        }
    )

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            outcome, model_a, model_b = determine_outcome(row)
            if not model_a or not model_b:
                continue

            # Count appearances regardless of outcome
            stats[model_a]["appearances_total"] += 1
            stats[model_b]["appearances_total"] += 1
            stats[model_a]["appearances_left"] += 1
            stats[model_b]["appearances_right"] += 1

            if not outcome:
                continue

            if outcome == "both_bad":
                # Track both_bad but skip rating update
                stats[model_a]["both_bad"] += 1
                stats[model_b]["both_bad"] += 1
                continue
            elif outcome == "left":
                elo.update_outcome(model_a, model_b, outcome="left")
                stats[model_a]["wins"] += 1
                stats[model_b]["losses"] += 1
                stats[model_a]["games"] += 1
                stats[model_b]["games"] += 1
            elif outcome == "right":
                elo.update_outcome(model_a, model_b, outcome="right")
                stats[model_b]["wins"] += 1
                stats[model_a]["losses"] += 1
                stats[model_a]["games"] += 1
                stats[model_b]["games"] += 1
            elif outcome == "tie":
                elo.update_outcome(model_a, model_b, outcome="tie")
                stats[model_a]["ties"] += 1
                stats[model_b]["ties"] += 1
                stats[model_a]["games"] += 1
                stats[model_b]["games"] += 1

    return elo, stats


def write_outputs(out_dir: Path, elo: EloRatingSystem, stats: Dict[str, Dict[str, float]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure every model in stats has a rating allocated
    for mid in list(stats.keys()):
        _ = elo.get_rating(mid)

    rankings = elo.rankings()
    rating_map = {row["id"]: row["rating"] for row in rankings}
    for mid, s in stats.items():
        rating = float(rating_map.get(mid, elo.get_rating(mid)))
        games = int(s["games"]) or 1
        non_tie_games = max(1, int(s["wins"]) + int(s["losses"]))
        win_rate = (float(s["wins"]) / float(non_tie_games)) * 100.0
        s.update({"rating": rating, "win_rate_percent": win_rate})

    # Round ratings to integers in JSON output
    rankings_int = [{"id": r["id"], "rating": int(round(r["rating"]))} for r in rankings]
    rankings_path = out_dir / "elo_rankings.json"
    rankings_path.write_text(json.dumps(rankings_int, indent=2), encoding="utf-8")

    stats_path = out_dir / "model_stats.csv"
    with stats_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "model_id",
            "rating",
            "games",
            "wins",
            "losses",
            "ties",
            "win_rate_percent",
            "appearances_total",
            "appearances_left",
            "appearances_right",
            "both_bad",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mid, s in sorted(stats.items(), key=lambda kv: kv[1].get("rating", 0), reverse=True):
            writer.writerow({
                "model_id": mid,
                "rating": str(int(round(s.get('rating', 0)))),
                "games": int(s.get("games", 0)),
                "wins": int(s.get("wins", 0)),
                "losses": int(s.get("losses", 0)),
                "ties": int(s.get("ties", 0)),
                "win_rate_percent": str(int(round(s.get('win_rate_percent', 0.0)))),
                "appearances_total": int(s.get("appearances_total", 0)),
                "appearances_left": int(s.get("appearances_left", 0)),
                "appearances_right": int(s.get("appearances_right", 0)),
                "both_bad": int(s.get("both_bad", 0)),
            })

    print(f"Wrote {rankings_path}")
    print(f"Wrote {stats_path}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Process vote CSV and compute Elo ratings.")
    parser.add_argument("--csv", dest="csv_path", default="15th sept new.csv", help="Path to input CSV")
    parser.add_argument("--outdir", dest="outdir", default="analysis", help="Output directory for results")
    parser.add_argument("--initial", type=float, default=1000.0, help="Initial Elo rating")
    parser.add_argument("--k", dest="k_factor", type=float, default=32.0, help="K-factor")
    parser.add_argument("--width", dest="rating_width", type=float, default=400.0, help="Rating width")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    elo, stats = process_csv(csv_path, args.initial, args.k_factor, args.rating_width)
    write_outputs(Path(args.outdir), elo, stats)

    print("Top models:")
    for row in elo.rankings()[:10]:
        print(f"- {row['id']}: {row['rating']:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


