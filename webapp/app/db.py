"""Read-only SQLite access for /app, including the public /app/sql query box.

Defence is layered, because any single check can be worked around:
  1. the file is opened `mode=ro`, so the driver itself refuses writes
  2. a sqlite3 authorizer denies every action except reading the graph tables
  3. a statement guard rejects anything that is not a single SELECT/WITH
  4. a progress handler aborts long queries, and rows are hard-capped
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"

MAX_ROWS = 200
TIMEOUT_SECONDS = 2.0

READABLE_TABLES = {"nodes", "edges", "nodes_fts"}

# Statements that are structurally not a read. Checked before SQLite sees them
# so the user gets a clear error rather than an opaque authorizer failure.
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|replace|attach|detach|vacuum|reindex"
    r"|pragma|begin|commit|rollback|savepoint|load_extension)\b",
    re.IGNORECASE,
)


class QueryError(Exception):
    """Raised for a query we refuse to run. Message is shown to the user."""


def _authorizer(action: int, arg1: str | None, arg2: str | None, *_rest) -> int:
    """Deny everything except reading columns of the graph tables."""
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 in READABLE_TABLES else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        # scalar/aggregate functions are fine; extension loading is not
        return sqlite3.SQLITE_DENY if arg2 == "load_extension" else sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def connect(readonly: bool = True) -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro" if readonly else f"file:{DB_PATH}"
    con = sqlite3.connect(uri, uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _guard(sql: str) -> str:
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise QueryError("Empty query.")
    if ";" in stripped:
        raise QueryError("One statement at a time, please.")
    if not re.match(r"^(select|with)\b", stripped, re.IGNORECASE):
        raise QueryError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    if FORBIDDEN.search(stripped):
        raise QueryError("This query contains a keyword that is not allowed here.")
    return stripped


def run_query(sql: str) -> tuple[list[str], list[tuple], bool]:
    """Return (columns, rows, truncated). Raises QueryError for refusals."""
    stripped = _guard(sql)
    con = connect()
    deadline = time.monotonic() + TIMEOUT_SECONDS
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
    con.set_authorizer(_authorizer)
    try:
        cur = con.execute(stripped)
        rows = cur.fetchmany(MAX_ROWS + 1)
        cols = [d[0] for d in cur.description] if cur.description else []
    except sqlite3.OperationalError as exc:
        msg = str(exc)
        if "interrupted" in msg.lower():
            raise QueryError(f"Query took longer than {TIMEOUT_SECONDS:g}s and was stopped.") from exc
        if "not authorized" in msg.lower():
            raise QueryError("That query touches something outside the graph tables.") from exc
        raise QueryError(f"SQLite: {msg}") from exc
    except sqlite3.DatabaseError as exc:
        raise QueryError(f"SQLite: {exc}") from exc
    finally:
        con.close()

    truncated = len(rows) > MAX_ROWS
    return cols, [tuple(r) for r in rows[:MAX_ROWS]], truncated


# --- fixed queries used by the browse UI -----------------------------------

def summary() -> dict:
    con = connect()
    try:
        return {
            "nodes": con.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
            "edges": con.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
            "by_type": con.execute(
                "SELECT type, COUNT(*) n FROM nodes GROUP BY type ORDER BY n DESC").fetchall(),
            "edge_types": con.execute(
                "SELECT type, COUNT(*) n FROM edges GROUP BY type ORDER BY n DESC").fetchall(),
        }
    finally:
        con.close()


def node(node_id: str) -> sqlite3.Row | None:
    con = connect()
    try:
        return con.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    finally:
        con.close()


def neighbourhood(node_id: str) -> dict:
    con = connect()
    try:
        return {
            "out": con.execute(
                "SELECT e.type, e.dst id, n.label, n.type node_type, e.excerpt"
                " FROM edges e JOIN nodes n ON n.id = e.dst WHERE e.src = ?"
                " ORDER BY e.type, n.label", (node_id,)).fetchall(),
            "in": con.execute(
                "SELECT e.type, e.src id, n.label, n.type node_type, e.excerpt"
                " FROM edges e JOIN nodes n ON n.id = e.src WHERE e.dst = ?"
                " ORDER BY e.type, n.label", (node_id,)).fetchall(),
        }
    finally:
        con.close()


def nodes_of_type(node_type: str) -> list[sqlite3.Row]:
    con = connect()
    try:
        return con.execute(
            "SELECT * FROM nodes WHERE type = ? ORDER BY label", (node_type,)).fetchall()
    finally:
        con.close()


def search(term: str, limit: int = 40) -> list[sqlite3.Row]:
    term = (term or "").strip()
    if not term:
        return []
    con = connect()
    try:
        # FTS first; fall back to LIKE for partial words and punctuation the
        # tokenizer chokes on (e.g. "car-t", "json-ld").
        try:
            fts = term.replace('"', " ")
            return con.execute(
                "SELECT n.* FROM nodes_fts f JOIN nodes n ON n.rowid = f.rowid"
                " WHERE nodes_fts MATCH ? ORDER BY rank LIMIT ?", (f'"{fts}"*', limit)).fetchall()
        except sqlite3.DatabaseError:
            like = f"%{term}%"
            return con.execute(
                "SELECT * FROM nodes WHERE label LIKE ? OR body LIKE ? OR id LIKE ?"
                " ORDER BY label LIMIT ?", (like, like, like, limit)).fetchall()
    finally:
        con.close()
