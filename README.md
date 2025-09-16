# Elo/BT Library

This repository provides small, reusable tools to compute rankings from pairwise votes:

- Elo rating system (`lib/elo`) with a CLI to process a votes CSV
- Bradley–Terry model (`lib/bt`) with a CLI to fit BT and convert to Elo scale

No UI/server is included.

## Requirements
- Python 3.10+

## Install (optional)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # currently no external deps
```

## CLI tools

### Elo processing
```bash
python scripts/process_votes.py --csv "15th sept new.csv" --outdir analysis
```
Outputs:
- `analysis/elo_rankings.json` (integer ratings)
- `analysis/model_stats.csv` (rating, games, wins, losses, ties, appearances, both_bad, win_rate)

### Bradley–Terry fitting
```bash
python scripts/fit_bt.py --csv "15th sept new.csv" --outdir analysis --tie half
```
Outputs:
- `analysis/bt_ratings.json` (integer BT-based Elo)
- `analysis/bt_model_stats.csv`

## Library usage
```python
from lib.elo import EloRatingSystem

elo = EloRatingSystem(initial_rating=1000, k_factor=32)
elo.update_outcome("model_left", "model_right", outcome="left")
elo.update_outcome("a", "b", outcome="tie")
print(elo.rankings())
```

```python
from pathlib import Path
from lib.bt import process_csv_to_bt, fit_bt_mm, convert_bt_to_elo

wins, totals = process_csv_to_bt(Path("15th sept new.csv"), tie_mode="half")
p = fit_bt_mm(wins, totals)
elos = convert_bt_to_elo(p)
```

## Notes
- In the CSV, `is_tie == "2"` means both responses are bad (ignored for ratings).
- Ties are supported (Elo uses 0.5; BT uses 0.5/0.5 by default). For full Davidson tie modeling, extend `lib/bt`.
