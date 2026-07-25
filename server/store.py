from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class TrainingStore:
    def __init__(self, path: str | Path = "data/runner.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS priors (
                    action_key TEXT,
                    family TEXT,
                    support INT,
                    total INT,
                    PRIMARY KEY(action_key, family)
                );
                CREATE TABLE IF NOT EXISTS calibration (
                    bucket REAL PRIMARY KEY,
                    claimed REAL,
                    hit_rate REAL,
                    n INT
                );
                CREATE TABLE IF NOT EXISTS generations (
                    gen INT PRIMARY KEY,
                    created_at TEXT,
                    agent_metrics TEXT,
                    gen_metrics TEXT,
                    weights TEXT
                );
                CREATE TABLE IF NOT EXISTS synth_games (
                    spec_id TEXT PRIMARY KEY,
                    gen INT,
                    spec TEXT,
                    fool_score REAL,
                    solved INT
                );
                CREATE TABLE IF NOT EXISTS episodes (
                    episode_id TEXT PRIMARY KEY,
                    gen INT,
                    game TEXT,
                    source TEXT,
                    metrics TEXT,
                    steps_blob TEXT
                );
                CREATE TABLE IF NOT EXISTS trap_signals (
                    trap TEXT,
                    signature TEXT,
                    hits INT,
                    PRIMARY KEY(trap, signature)
                );
                """
            )

    def record_prior(self, action_key: str, family: str, support: int = 1, total: int = 1) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO priors(action_key, family, support, total)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(action_key, family) DO UPDATE SET
                    support = support + excluded.support,
                    total = total + excluded.total
                """,
                (action_key, family, support, total),
            )

    def record_calibration(self, claimed: float, hit: bool | float) -> None:
        bucket = round(min(0.9, max(0.0, claimed // 0.1 * 0.1)), 1)
        hit_value = min(1.0, max(0.0, float(hit)))
        with self._connect() as db:
            existing = db.execute(
                "SELECT * FROM calibration WHERE bucket = ?",
                (bucket,),
            ).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO calibration(bucket, claimed, hit_rate, n) VALUES (?, ?, ?, ?)",
                    (bucket, claimed, hit_value, 1),
                )
                return
            n = int(existing["n"]) + 1
            claimed_avg = (float(existing["claimed"]) * int(existing["n"]) + claimed) / n
            hits = float(existing["hit_rate"]) * int(existing["n"]) + hit_value
            db.execute(
                "UPDATE calibration SET claimed = ?, hit_rate = ?, n = ? WHERE bucket = ?",
                (claimed_avg, hits / n, n, bucket),
            )

    def record_generation(
        self,
        gen: int,
        created_at: str,
        agent_metrics: dict[str, Any],
        gen_metrics: dict[str, Any],
        weights: dict[str, Any],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO generations(
                    gen, created_at, agent_metrics, gen_metrics, weights
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    gen,
                    created_at,
                    json.dumps(agent_metrics),
                    json.dumps(gen_metrics),
                    json.dumps(weights),
                ),
            )

    def record_synth_game(
        self,
        spec_id: str,
        gen: int,
        spec: dict[str, Any],
        fool_score: float,
        solved: bool,
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO synth_games(spec_id, gen, spec, fool_score, solved)
                VALUES (?, ?, ?, ?, ?)
                """,
                (spec_id, gen, json.dumps(spec), fool_score, int(solved)),
            )

    def record_episode(
        self,
        episode_id: str,
        gen: int,
        game: str,
        source: str,
        metrics: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO episodes(episode_id, gen, game, source, metrics, steps_blob)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (episode_id, gen, game, source, json.dumps(metrics), json.dumps(steps)),
            )

    def record_trap_signal(self, trap: str, signature: str, hits: int = 1) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO trap_signals(trap, signature, hits)
                VALUES (?, ?, ?)
                ON CONFLICT(trap, signature) DO UPDATE SET hits = hits + excluded.hits
                """,
                (trap, signature, hits),
            )

    def list_generations(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM generations ORDER BY gen").fetchall()
        return [
            {
                "gen": int(row["gen"]),
                "created_at": row["created_at"],
                "agent_metrics": json.loads(row["agent_metrics"]),
                "gen_metrics": json.loads(row["gen_metrics"]),
                "weights": json.loads(row["weights"]),
            }
            for row in rows
        ]

    def list_generation_games(self, gen: int) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM synth_games WHERE gen = ? ORDER BY fool_score DESC",
                (gen,),
            ).fetchall()
        games = []
        for row in rows:
            spec = json.loads(row["spec"])
            trap = spec.get("traps", [{}])[0]
            games.append(
                {
                    "spec_id": row["spec_id"],
                    "gen": int(row["gen"]),
                    "trap": trap.get("template", "synth"),
                    "params": trap.get("params", {}),
                    "fool_score": float(row["fool_score"]),
                    "solved": bool(row["solved"]),
                }
            )
        return games

    def list_generation_episodes(self, gen: int) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT episode_id, game, source, metrics
                FROM episodes
                WHERE gen = ?
                ORDER BY episode_id
                """,
                (gen,),
            ).fetchall()
        episodes = []
        for row in rows:
            metrics = json.loads(row["metrics"])
            episodes.append(
                {
                    "episode_id": row["episode_id"],
                    "gen": gen,
                    "game": row["game"],
                    "source": row["source"],
                    "trap": metrics.get("trap", "synth"),
                    "solved": bool(metrics.get("solved", False)),
                    "fool_score": float(metrics.get("fool_score", 0.0)),
                    "steps": int(metrics.get("steps", 0)),
                    "max_surprise": float(metrics.get("max_surprise", 0.0)),
                    "prediction_accuracy": float(metrics.get("prediction_accuracy", 0.0)),
                }
            )
        return episodes

    def get_episode(self, episode_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM episodes WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
        if row is None:
            raise KeyError(episode_id)
        metrics = json.loads(row["metrics"])
        return {
            "episode_id": row["episode_id"],
            "gen": int(row["gen"]),
            "game": row["game"],
            "spec_id": row["game"],
            "source": row["source"],
            "trap": metrics.get("trap", "synth"),
            "solved": bool(metrics.get("solved", False)),
            "fool_score": float(metrics.get("fool_score", 0.0)),
            "metrics": metrics,
            "steps": json.loads(row["steps_blob"]),
        }

    def knowledge(self) -> dict[str, Any]:
        with self._connect() as db:
            priors = db.execute("SELECT * FROM priors ORDER BY action_key, family").fetchall()
            calibration = db.execute("SELECT * FROM calibration ORDER BY bucket").fetchall()
            trap_signals = db.execute(
                "SELECT * FROM trap_signals ORDER BY trap, hits DESC"
            ).fetchall()
            episode_rows = db.execute(
                "SELECT episode_id, gen, steps_blob FROM episodes ORDER BY gen, episode_id"
            ).fetchall()
        surprise_timeline = []
        for row in episode_rows:
            for step in json.loads(row["steps_blob"]):
                surprise_timeline.append(
                    {
                        "gen": int(row["gen"]),
                        "episode_id": row["episode_id"],
                        "step": int(step.get("index", 0)),
                        "surprise": float(step.get("surprise", {}).get("value", 0.0)),
                    }
                )
        return {
            "priors": [dict(row) for row in priors],
            "calibration": [dict(row) for row in calibration],
            "trap_signals": [dict(row) for row in trap_signals],
            "surprise_timeline": surprise_timeline,
        }
