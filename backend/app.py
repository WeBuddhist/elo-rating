from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask import Response


# Ensure local imports work when running this file directly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from elo import update_ratings, apply_result
from llm_handler import LLMHandler


app = Flask(__name__, template_folder=str(CURRENT_DIR.parent / "templates"), static_folder=str(CURRENT_DIR.parent / "static"))
CORS(app)

MODELS_DB_PATH = CURRENT_DIR / "models.json"


def _load_models() -> Dict[str, float]:
    if not MODELS_DB_PATH.exists() or MODELS_DB_PATH.read_text().strip() == "":
        return {}
    try:
        return json.loads(MODELS_DB_PATH.read_text())
    except Exception:
        return {}


def _save_models(models: Dict[str, float]) -> None:
    MODELS_DB_PATH.write_text(json.dumps(models, indent=2, sort_keys=True))


def _ensure_default_models(handler: LLMHandler, default_rating: float = 1000.0) -> Dict[str, float]:
    models = _load_models()
    for model in handler.list_models():
        if model["id"] not in models:
            models[model["id"]] = float(default_rating)
    _save_models(models)
    return models


handler = LLMHandler()
_ensure_default_models(handler)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/models", methods=["GET"])
def list_models():
    ratings = _load_models()
    data = []
    for model in handler.list_models():
        data.append({
            "id": model["id"],
            "provider": model["provider"],
            "display_name": model["display_name"],
            "rating": ratings.get(model["id"], 1000.0),
        })
    return jsonify(data)


@app.route("/api/rankings", methods=["GET"])
def rankings():
    ratings = _load_models()
    ranked = sorted(ratings.items(), key=lambda kv: kv[1], reverse=True)
    return jsonify([{"id": k, "rating": v} for k, v in ranked])


@app.route("/api/compare", methods=["POST"])
def compare():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Missing prompt"}), 400

    available = [m["id"] for m in handler.list_models()]
    if len(available) < 2:
        return jsonify({"error": "At least two models must be configured"}), 400

    # Allow user to specify specific models, otherwise sample two
    model_a = body.get("model_a")
    model_b = body.get("model_b")
    if not (model_a and model_b):
        model_a, model_b = random.sample(available, 2)

    text_a = handler.generate(model_id=model_a, prompt=prompt)
    text_b = handler.generate(model_id=model_b, prompt=prompt)

    return jsonify({
        "a": {"text": text_a},
        "b": {"text": text_b},
        # Hidden identifiers used by the client when submitting a vote
        "a_model": model_a,
        "b_model": model_b,
    })


@app.route("/api/compare/stream", methods=["POST"])
def compare_stream():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    model_a = body.get("model_a")
    model_b = body.get("model_b")
    available = [m["id"] for m in handler.list_models()]
    if not (model_a and model_b):
        if len(available) >= 2:
            model_a, model_b = random.sample(available, 2)
        else:
            return jsonify({"error": "At least two models must be configured"}), 400

    def generate_ndjson():
        yield json.dumps({"type": "meta", "a_model": model_a, "b_model": model_b}) + "\n"
        yield json.dumps({"type": "start", "side": "a"}) + "\n"
        for token in handler.stream_generate(model_id=model_a, prompt=prompt):
            yield json.dumps({"type": "delta", "side": "a", "text": token}) + "\n"
        yield json.dumps({"type": "end", "side": "a"}) + "\n"
        yield json.dumps({"type": "start", "side": "b"}) + "\n"
        for token in handler.stream_generate(model_id=model_b, prompt=prompt):
            yield json.dumps({"type": "delta", "side": "b", "text": token}) + "\n"
        yield json.dumps({"type": "end", "side": "b"}) + "\n"

    return Response(generate_ndjson(), mimetype="application/x-ndjson")


@app.route("/api/vote", methods=["POST"])
def vote():
    body = request.get_json(silent=True) or {}
    winner = body.get("winner_id")
    loser = body.get("loser_id")
    outcome = body.get("outcome")  # 'left', 'right', 'tie', 'both_bad'

    ratings = _load_models()

    # Maintain compatibility with older clients: if outcome not provided, use winner/loser
    if outcome in {"left", "right"}:
        pass
    elif outcome == "tie":
        if not (winner and loser):
            return jsonify({"error": "Missing winner_id and loser_id for tie"}), 400
    elif outcome == "both_bad":
        if not (winner and loser):
            return jsonify({"error": "Missing winner_id and loser_id for both_bad"}), 400
    else:
        # fallback path: expect explicit winner/loser
        if not winner or not loser:
            return jsonify({"error": "Missing winner_id or loser_id"}), 400
        outcome = "right"  # interpret as winner=right by default for legacy

    if winner not in ratings or loser not in ratings:
        return jsonify({"error": "Unknown model id(s)"}), 400

    # Elo updates
    if outcome == "tie":
        new_winner, new_loser = apply_result(ratings[winner], ratings[loser], 0.5)
    elif outcome == "both_bad":
        new_winner, new_loser = ratings[winner], ratings[loser]
    elif outcome == "left":
        # 'left is better' means 'winner' beat 'loser'
        new_winner, new_loser = update_ratings(ratings[winner], ratings[loser])
    elif outcome == "right":
        new_winner, new_loser = update_ratings(ratings[winner], ratings[loser])
    else:
        return jsonify({"error": "Invalid outcome"}), 400

    ratings[winner] = new_winner
    ratings[loser] = new_loser
    _save_models(ratings)

    ranked = sorted(ratings.items(), key=lambda kv: kv[1], reverse=True)
    return jsonify({
        "updated": {winner: new_winner, loser: new_loser},
        "rankings": [{"id": k, "rating": v} for k, v in ranked],
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


