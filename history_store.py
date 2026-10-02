from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path.home() / ".local" / "share"
    path = root / "Gentill Transcriber"
    path.mkdir(parents=True, exist_ok=True)
    return path


DB_PATH = app_data_dir() / "history.sqlite3"


@dataclass(frozen=True)
class HistoryEntry:
    id: int
    created_at: str
    input_path: str
    output_dir: str
    model: str
    language: str
    duration: float | None
    elapsed: float
    status: str


class HistoryStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self._init()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init(self) -> None:
        with closing(self._connect()) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    input_path TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    model TEXT NOT NULL,
                    language TEXT NOT NULL,
                    duration REAL,
                    elapsed REAL NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            db.commit()

    def add(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        model: Path,
        language: str | None,
        duration: float | None,
        elapsed: float,
        status: str,
    ) -> None:
        with closing(self._connect()) as db:
            db.execute(
                """
                INSERT INTO transcriptions
                (created_at, input_path, output_dir, model, language, duration, elapsed, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    str(input_path),
                    str(output_dir),
                    str(model),
                    language or "auto",
                    duration,
                    elapsed,
                    status,
                ),
            )
            db.commit()

    def recent(self, limit: int = 200) -> list[HistoryEntry]:
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, created_at, input_path, output_dir, model, language,
                       duration, elapsed, status
                FROM transcriptions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [HistoryEntry(*row) for row in rows]

    def clear(self) -> None:
        with closing(self._connect()) as db:
            db.execute("DELETE FROM transcriptions")
            db.commit()
