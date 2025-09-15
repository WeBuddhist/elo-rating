
## Quick start
```bash
# From project root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create .env in the project root (no quotes)
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=AIza...

# Run the server (change port if needed)
PORT=5052 python backend/app.py
# Open http://localhost:5052
```

## Usage
1) Enter a prompt. Optionally choose Model A and Model B; otherwise keep Auto.
2) Click Compare. Outputs stream into left and right panes.
3) Vote: Left is better, Right is better, It's a tie, or Both are bad.
4) Elo updates and the leaderboard refreshes.

## Models included
- Claude: `claude-3-5-sonnet-20240620`, `claude-3-7-sonnet-latest`
- Gemini: `gemini-1.5-pro`, `gemini-2.5-flash`

Notes:
- Gemini 2.5 models use a thinking budget of 0 by default (fast, non-deliberative).
- Add new models in `backend/llm_handler.py` under `self.available_models` and ensure the `generate`/`stream_generate` logic knows how to call them.

## API
- `GET /api/models`
  - Returns available models with provider and current rating.
- `GET /api/rankings`
  - Returns all models sorted by Elo.
- `POST /api/compare`
  - Body: `{ prompt: string, model_a?: string, model_b?: string }`
  - Returns one-shot outputs: `{ a: {text}, b: {text}, a_model, b_model }`.
- `POST /api/compare/stream` (NDJSON)
  - Body: `{ prompt: string, model_a?: string, model_b?: string }`
  - Events: `{type: "meta"|"start"|"delta"|"end", side?: "a"|"b", text?: "..."}`
- `POST /api/vote`
  - Body: `{ outcome: "left"|"right"|"tie"|"both_bad", winner_id, loser_id }`
  - Tie applies 0.5 score to both. Both-bad leaves ratings unchanged.

## Elo details
- Default K-factor: 32
- Rating width: 400 (logistic curve)
- Updates:
  - Win/loss: `update_ratings(winner, loser)`
  - Generic: `apply_result(rating_a, rating_b, score_a)` where `score_a ∈ {1, 0.5, 0}`

## Reusable Elo library
- Location: `lib/elo`
  - `core.py`: `calculate_expected_score`, `apply_result`, `update_ratings`
  - `system.py`: `EloRatingSystem` (high-level interface)
  - `storage.py`: `JsonStore` (optional JSON persistence)
- Example:
```python
from lib.elo import EloRatingSystem

elo = EloRatingSystem(initial_rating=1000, k_factor=32)
elo.update_outcome("claude-3-7-sonnet-latest", "gemini-2.5-flash", outcome="left")
elo.update_outcome("gemini-1.5-pro", "claude-3-5-haiku-20241022", outcome="tie")
print(elo.rankings())
```

## Configuration
- Change default K or rating width by instantiating `EloRatingSystem` with custom values.
- Server port: set `PORT` env var (defaults to 5000 if not set).
- Ratings are stored in `backend/models.json`. Delete this file to reset.

## Troubleshooting
- 401 invalid `x-api-key` (Claude): verify `ANTHROPIC_API_KEY` in `.env` and restart server.
- 400 API key expired (Gemini): regenerate `GOOGLE_API_KEY` in Google AI Studio.
- httpx `proxies` TypeError: we pin `httpx<0.28` in `requirements.txt` for Anthropic SDK compatibility.
- Port in use: set a different `PORT` or stop the occupying service.

## Notes
- The UI hides model identities during comparison to reduce bias.
- You can schedule pairings externally for round-robin or coverage-aware tournaments.
