"""SQLite persistence: criteria, runs, supplier results."""
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("RFP_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "rfp_eval.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    weight REAL NOT NULL,
    max_score REAL NOT NULL DEFAULT 10,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT
);
CREATE TABLE IF NOT EXISTS supplier_results (
    rfp_run_id TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    submission_date TEXT NOT NULL,
    experience_rating REAL NOT NULL,
    absolute_score REAL,
    ppi REAL,
    final_rank INTEGER,
    result_json TEXT,
    PRIMARY KEY (rfp_run_id, supplier_name)
);
"""

SEED = [
    (1, "Technical Capability", "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    (2, "Implementation Plan", "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    (3, "Commercial Value", "Pricing clarity, total cost, assumptions", 20, 10, 1),
    (4, "Security & Compliance", "Controls, certifications, privacy, auditability", 20, 10, 1),
    (5, "Support & Experience", "Support model, similar projects, references", 10, 10, 1),
]


def connect(path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str = None) -> None:
    """Create tables and seed criteria if empty (idempotent)."""
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0] == 0:
            conn.executemany("INSERT INTO evaluation_criteria VALUES (?,?,?,?,?,?)", SEED)


def load_criteria(active_only: bool = True, path: str = None) -> list[dict]:
    sql = "SELECT * FROM evaluation_criteria"
    if active_only:
        sql += " WHERE is_active = 1"
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY criterion_id")]


def save_criteria(rows: list[dict], path: str = None) -> None:
    with connect(path) as conn:
        for r in rows:
            conn.execute(
                "UPDATE evaluation_criteria SET weight=?, max_score=?, is_active=? WHERE criterion_id=?",
                (float(r["weight"]), float(r["max_score"]), int(bool(r["is_active"])), int(r["criterion_id"])),
            )


def create_run(rfp_run_id: str, path: str = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?,?,?)",
            (rfp_run_id, datetime.now(timezone.utc).isoformat(), "RUNNING"),
        )


def set_run_status(rfp_run_id: str, status: str, result: dict | None = None, path: str = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE rfp_runs SET status=?, result_json=COALESCE(?, result_json) WHERE rfp_run_id=?",
            (status, json.dumps(result) if result is not None else None, rfp_run_id),
        )


def save_supplier_results(rfp_run_id: str, leaderboard: list[dict], path: str = None) -> None:
    with connect(path) as conn:
        for s in leaderboard:
            conn.execute(
                "INSERT OR REPLACE INTO supplier_results VALUES (?,?,?,?,?,?,?,?)",
                (rfp_run_id, s["supplier_name"], s["submission_date"], s["experience_rating"],
                 s["absolute_score"], s["ppi"], s["final_rank"], json.dumps(s)),
            )


def list_runs(path: str = None) -> list[dict]:
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY created_at DESC")]


def get_run_result(rfp_run_id: str, path: str = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute("SELECT result_json FROM rfp_runs WHERE rfp_run_id=?", (rfp_run_id,)).fetchone()
    return json.loads(row["result_json"]) if row and row["result_json"] else None
