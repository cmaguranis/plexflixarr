import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


class CallState:
    """JSON file-backed store for persisting the last-called date per key.

    The file is created on first write. Missing keys return ``None``.

    Example::

        state = CallState("data/state.json")
        state.record("tmdb")
        last = state.get("tmdb")   # date(2026, 3, 15), or None if never called
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)

    def get(self, key: str) -> date | None:
        """Return the last recorded date for *key*, or None."""
        raw = self._read().get(key)
        return date.fromisoformat(raw) if raw is not None else None

    def record(self, key: str, when: date | None = None) -> None:
        """Record *key* as called on *when* (defaults to today)."""
        value = (when or date.today()).isoformat()
        data = self._read()
        data[key] = value
        self._write(data)
        logger.debug("CallState: recorded '%s' on %s", key, value)

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except FileNotFoundError:
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))
