from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


class JsonStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, float]:
        if not self.path.exists():
            return {}
        try:
            content = self.path.read_text()
            return json.loads(content) if content.strip() else {}
        except Exception:
            return {}

    def save(self, data: Dict[str, float]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))


