from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any


class TrainingStore:
    """Small SQLite store for the current process' synthetic training audit."""

    def __init__(self, path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._db:
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS generations (
                    gen INTEGER PRIMARY KEY,
                    metrics TEXT NOT NULL
                )
                """
            )
            self._db.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    gen INTEGER NOT NULL,
                    game TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )

    def reset(self) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM episodes")
            self._db.execute("DELETE FROM generations")

    def save_generation(self, gen: int, metrics: dict[str, Any]) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT OR REPLACE INTO generations (gen, metrics)
                VALUES (?, ?)
                """,
                (gen, json.dumps(metrics, ensure_ascii=False)),
            )

    def save_episode(
        self,
        *,
        episode_id: str,
        gen: int,
        game: str,
        source: str,
        metrics: dict[str, Any],
        detail: dict[str, Any],
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT OR REPLACE INTO episodes
                    (episode_id, gen, game, source, metrics, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    gen,
                    game,
                    source,
                    json.dumps(metrics, ensure_ascii=False),
                    json.dumps(detail, ensure_ascii=False),
                ),
            )

    def list_generations(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT gen, metrics FROM generations ORDER BY gen"
            ).fetchall()
        return [self._with_gen(row) for row in rows]

    def list_episodes_by_gen(self, gen: int) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                """
                SELECT episode_id, game, source, metrics
                FROM episodes
                WHERE gen = ?
                ORDER BY episode_id
                """,
                (gen,),
            ).fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            metrics = json.loads(row["metrics"])
            summaries.append(
                {
                    "episode_id": row["episode_id"],
                    "gen": gen,
                    "game": row["game"],
                    "source": row["source"],
                    **metrics,
                }
            )
        return summaries

    def get_episode(self, episode_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT detail FROM episodes WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["detail"])

    def list_episode_details(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT detail FROM episodes ORDER BY gen, episode_id"
            ).fetchall()
        return [json.loads(row["detail"]) for row in rows]

    @staticmethod
    def _with_gen(row: sqlite3.Row) -> dict[str, Any]:
        metrics = json.loads(row["metrics"])
        return {"gen": int(row["gen"]), **metrics}
