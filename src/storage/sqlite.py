import json
import sqlite3
from pathlib import Path

from src.core.models import Analysis, Transcript


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS analyses (call_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, created_at TEXT NOT NULL, origin TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS analyses_agent_date ON analyses(agent_id, created_at)")
            db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, kind TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS qa_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def save(self, analysis: Analysis):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO analyses VALUES (?, ?, ?, ?, ?)",
                       (analysis.call_id, analysis.agent_id, analysis.created_at, analysis.origin, analysis.model_dump_json()))

    def list(self) -> list[Analysis]:
        with self.connect() as db:
            rows = db.execute("SELECT data FROM analyses ORDER BY created_at DESC").fetchall()
        return [Analysis.model_validate_json(row[0]) for row in rows]

    def get(self, call_id: str) -> Analysis | None:
        with self.connect() as db:
            row = db.execute("SELECT data FROM analyses WHERE call_id = ?", (call_id,)).fetchone()
        return Analysis.model_validate_json(row[0]) if row else None

    def cache_get(self, key: str, kind: str):
        with self.connect() as db:
            row = db.execute("SELECT data FROM cache WHERE key = ? AND kind = ?", (key, kind)).fetchone()
        return json.loads(row[0]) if row else None

    def cache_put(self, key: str, kind: str, value: Transcript | Analysis):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?)", (key, kind, value.model_dump_json()))

    def add_review(self, call_id: str, reviewer: str, decision: str, notes: str):
        if decision not in {"Approved", "Corrected", "Needs follow-up"}:
            raise ValueError("Invalid review decision")
        with self.connect() as db:
            db.execute("INSERT INTO qa_reviews(call_id, reviewer, decision, notes) VALUES (?, ?, ?, ?)",
                       (call_id, reviewer, decision, notes))

    def reviews(self, call_id: str):
        with self.connect() as db:
            return db.execute("SELECT reviewer, decision, notes, created_at FROM qa_reviews WHERE call_id = ? ORDER BY id DESC", (call_id,)).fetchall()
