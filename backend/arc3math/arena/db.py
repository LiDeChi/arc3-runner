from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any
import json
import sqlite3
import uuid
from datetime import datetime, timezone


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  config_json TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS games (
  id TEXT PRIMARY KEY,
  run_id TEXT,
  spec_json TEXT NOT NULL,
  traps_json TEXT NOT NULL,
  difficulty REAL,
  oracle_len INTEGER
);
CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  run_id TEXT,
  game_id TEXT,
  idx INTEGER,
  result TEXT,
  steps INTEGER,
  avg_conf REAL,
  overconf REAL,
  probe_steps INTEGER,
  revisions INTEGER,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  episode_id TEXT,
  step_idx INTEGER,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metrics (
  run_id TEXT,
  episode_idx INTEGER,
  name TEXT,
  value REAL,
  PRIMARY KEY (run_id, episode_idx, name)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self.lock = RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self) -> None:
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def create_run(self, config: dict[str, Any], run_id: str | None = None, status: str = "running") -> str:
        rid = run_id or str(uuid.uuid4())
        with self.lock:
            self.conn.execute(
                "INSERT INTO runs(id, config_json, status, created_at) VALUES(?,?,?,?)",
                (rid, json.dumps(config, sort_keys=True), status, now_iso()),
            )
            self.conn.commit()
        return rid

    def update_run_status(self, run_id: str, status: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
            self.conn.commit()

    def insert_game(self, run_id: str, spec: dict[str, Any]) -> None:
        meta = spec.get("meta", {})
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO games(id, run_id, spec_json, traps_json, difficulty, oracle_len) VALUES(?,?,?,?,?,?)",
                (
                    spec["id"],
                    run_id,
                    json.dumps(spec, sort_keys=True),
                    json.dumps(meta.get("traps", []), sort_keys=True),
                    float(meta.get("difficulty", 0.0)),
                    int(meta.get("oracle_len", 0) or 0),
                ),
            )
            self.conn.commit()

    def insert_episode(self, run_id: str, game_id: str, idx: int, episode_id: str, summary: dict[str, Any]) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO episodes
                (id, run_id, game_id, idx, result, steps, avg_conf, overconf, probe_steps, revisions, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    episode_id,
                    run_id,
                    game_id,
                    idx,
                    summary.get("result"),
                    int(summary.get("steps", 0)),
                    float(summary.get("avg_conf", 0.0)),
                    float(summary.get("overconf", 0.0)),
                    int(summary.get("probe_steps", 0)),
                    int(summary.get("revisions", 0)),
                    now_iso(),
                ),
            )
            self.conn.commit()

    def insert_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stored = []
        with self.lock:
            for event in events:
                cur = self.conn.execute(
                    "INSERT INTO events(episode_id, step_idx, type, payload_json) VALUES(?,?,?,?)",
                    (event["episode_id"], int(event["step_idx"]), event["type"], json.dumps(event["payload"], sort_keys=True)),
                )
                row = {**event, "id": cur.lastrowid}
                stored.append(row)
            self.conn.commit()
        return stored

    def insert_metric(self, run_id: str, idx: int, name: str, value: float) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO metrics(run_id, episode_idx, name, value) VALUES(?,?,?,?)",
                (run_id, idx, name, float(value)),
            )
            self.conn.commit()

    def list_runs(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._run_row(r) for r in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return None
            data = self._run_row(row)
            metrics = self.conn.execute(
                "SELECT episode_idx, name, value FROM metrics WHERE run_id=? ORDER BY episode_idx",
                (run_id,),
            ).fetchall()
        data["metrics"] = [dict(r) for r in metrics]
        return data

    def _run_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "config": json.loads(row["config_json"]), "status": row["status"], "created_at": row["created_at"]}

    def list_episodes(self, run_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT e.*, g.traps_json, g.difficulty, g.spec_json
                FROM episodes e LEFT JOIN games g ON e.game_id=g.id
                WHERE e.run_id=? ORDER BY e.idx LIMIT ? OFFSET ?
                """,
                (run_id, limit, offset),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["traps"] = json.loads(item.pop("traps_json") or "[]")
            item["spec"] = json.loads(item.pop("spec_json") or "{}")
            out.append(item)
        return out

    def episode_events(self, episode_id: str, after_id: int | None = None) -> list[dict[str, Any]]:
        with self.lock:
            if after_id is None:
                rows = self.conn.execute(
                    "SELECT * FROM events WHERE episode_id=? ORDER BY step_idx, id",
                    (episode_id,),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM events WHERE episode_id=? AND id>? ORDER BY step_idx, id",
                    (episode_id, after_id),
                ).fetchall()
        return [self._event_row(r) for r in rows]

    def run_events(self, run_id: str, after_id: int | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT ev.* FROM events ev
            JOIN episodes ep ON ep.id=ev.episode_id
            WHERE ep.run_id=?
        """
        params: list[Any] = [run_id]
        if after_id is not None:
            sql += " AND ev.id>?"
            params.append(after_id)
        sql += " ORDER BY ev.id"
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [self._event_row(r) for r in rows]

    def _event_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "episode_id": row["episode_id"],
            "step_idx": row["step_idx"],
            "type": row["type"],
            "payload": json.loads(row["payload_json"]),
        }

    def metrics(self, run_id: str, names: list[str] | None = None) -> list[dict[str, Any]]:
        with self.lock:
            if names:
                placeholders = ",".join("?" for _ in names)
                rows = self.conn.execute(
                    f"SELECT * FROM metrics WHERE run_id=? AND name IN ({placeholders}) ORDER BY episode_idx",
                    [run_id, *names],
                ).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM metrics WHERE run_id=? ORDER BY episode_idx", (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def trap_stats(self, run_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT g.traps_json, e.result, e.overconf
                FROM episodes e JOIN games g ON e.game_id=g.id
                WHERE e.run_id=?
                """,
                (run_id,),
            ).fetchall()
        stats: dict[str, dict[str, Any]] = {}
        for row in rows:
            arm = "+".join(json.loads(row["traps_json"]) or ["none"])
            item = stats.setdefault(arm, {"arm": arm, "plays": 0, "wins": 0, "overconf_sum": 0.0})
            item["plays"] += 1
            item["wins"] += 1 if row["result"] == "win" else 0
            item["overconf_sum"] += float(row["overconf"] or 0.0)
        return [
            {
                "arm": arm,
                "plays": v["plays"],
                "agent_win_rate": v["wins"] / v["plays"] if v["plays"] else 0.0,
                "overconf_mean": v["overconf_sum"] / v["plays"] if v["plays"] else 0.0,
                "ucb": 0.0,
            }
            for arm, v in sorted(stats.items())
        ]
