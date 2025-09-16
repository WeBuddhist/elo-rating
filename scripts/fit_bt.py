from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Import BT utilities from library
from lib.bt import process_csv_to_bt, fit_bt_mm, convert_bt_to_elo


def write_outputs(out_dir: Path, elos: Dict[str, float], wins: Dict[str, Dict[str, float]], totals: Dict[str, Dict[str, float]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    items = sorted(elos.items(), key=lambda kv: kv[1], reverse=True)

    # Rankings JSON
    rankings = [{"id": mid, "elo_bt": int(round(rating))} for mid, rating in items]
    (out_dir / "bt_ratings.json").write_text(json.dumps(rankings, indent=2), encoding="utf-8")

    # Aggregate stats per model
    stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "ties": 0})
    models = {i for i in wins.keys()} | {j for i in wins for j in wins[i].keys()}
    for i in models:
        for j, n_ij in totals.get(i, {}).items():
            stats[i]["games"] += n_ij
            w_ij = wins.get(i, {}).get(j, 0.0)
            w_ji = wins.get(j, {}).get(i, 0.0)
            # Split ties from symmetric fractional wins
            tie_count = max(0.0, min(w_ij, w_ji)) if abs((w_ij + w_ji) - n_ij) < 1e-6 else 0.0
            stats[i]["ties"] += tie_count
            # Wins/losses without the tied portion
            stats[i]["wins"] += max(0.0, w_ij - tie_count)
            stats[i]["losses"] += max(0.0, w_ji - tie_count)

    # Stats CSV
    with (out_dir / "bt_model_stats.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["model_id", "elo_bt", "games", "wins", "losses", "ties", "win_rate_percent"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for mid, elo_val in items:
            s = stats.get(mid, {"games": 0, "wins": 0, "losses": 0, "ties": 0})
            non_tie_games = max(1.0, float(s["wins"]) + float(s["losses"]))
            win_rate = 100.0 * float(s["wins"]) / non_tie_games
            writer.writerow({
                "model_id": mid,
                "elo_bt": str(int(round(elo_val))),
                "games": int(s["games"]),
                "wins": int(round(float(s["wins"]))),
                "losses": int(round(float(s["losses"]))),
                "ties": int(round(float(s["ties"]))),
                "win_rate_percent": str(int(round(win_rate))),
            })


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fit Bradley–Terry model from votes and output BT-based Elo ratings.")
    parser.add_argument("--csv", dest="csv_path", default="15th sept new.csv", help="Path to input CSV")
    parser.add_argument("--outdir", dest="outdir", default="analysis", help="Output directory for results")
    parser.add_argument("--tie", dest="tie_mode", choices=["half", "skip"], default="half", help="Tie handling: give 0.5 to each or skip")
    parser.add_argument("--max_iter", type=int, default=5000, help="Max MM iterations")
    parser.add_argument("--tol", type=float, default=1e-9, help="Convergence tolerance")
    args = parser.parse_args(argv)

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        return 1

    wins, totals = process_csv_to_bt(csv_path, tie_mode=args.tie_mode)
    if not wins:
        print("No pairwise data found in CSV.")
        return 1

    p = fit_bt_mm(wins, totals, max_iter=args.max_iter, tol=args.tol)
    elos = convert_bt_to_elo(p, base=1000.0)
    write_outputs(Path(args.outdir), elos, wins, totals)

    print("Top BT-based Elo models:")
    for mid, score in sorted(elos.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        print(f"- {mid}: {score:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


