#!/usr/bin/env python3
"""Load resume-graph.jsonld into a SQLite file for /app to serve read-only.

Run at image build time. The resulting graph.db is baked into the Docker image,
so the Fly machine needs no volume and the runtime connection can be mode=ro.

    python load_graph.py ../rahulmranga/resume-graph.jsonld graph.db
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "schema.sql"


def load(graph_path: Path, db_path: Path) -> tuple[int, int]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes, edges = graph["nodes"], graph["edges"]

    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))

    con.executemany(
        "INSERT INTO nodes (id, type, label, body, confidence, created_at)"
        " VALUES (:id, :type, :label, :body, :confidence, :created_at)",
        [{"id": nid,
          "type": n.get("type", ""),
          "label": n.get("label", nid),
          "body": n.get("body", ""),
          "confidence": n.get("confidence", ""),
          "created_at": n.get("created_at", "")} for nid, n in nodes.items()],
    )

    known = set(nodes)
    rows, skipped = [], []
    for e in edges:
        if e["src"] not in known or e["dst"] not in known:
            skipped.append(e)          # FK would fail; surface rather than swallow
            continue
        rows.append({"src": e["src"], "dst": e["dst"], "type": e.get("type", ""),
                     "confidence": e.get("confidence", ""), "excerpt": e.get("excerpt", ""),
                     "source_id": e.get("source_id", ""), "created_at": e.get("created_at", "")})
    con.executemany(
        "INSERT INTO edges (src, dst, type, confidence, excerpt, source_id, created_at)"
        " VALUES (:src, :dst, :type, :confidence, :excerpt, :source_id, :created_at)", rows)

    con.execute("INSERT INTO nodes_fts(nodes_fts) VALUES('rebuild')")
    con.commit()

    # provenance invariant, enforced here too: nothing ships without a source
    orphans = con.execute(
        "SELECT COUNT(*) FROM nodes n WHERE n.type != 'source'"
        " AND NOT EXISTS (SELECT 1 FROM edges e WHERE e.src = n.id AND e.type = 'MENTIONED_IN')"
    ).fetchone()[0]
    if orphans:
        raise SystemExit(f"load_graph: {orphans} non-source nodes have no MENTIONED_IN edge")

    con.execute("VACUUM")
    con.close()
    if skipped:
        print(f"  warning: skipped {len(skipped)} edges with unknown endpoints")
    return len(nodes), len(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    n, e = load(Path(sys.argv[1]).expanduser().resolve(), Path(sys.argv[2]).expanduser().resolve())
    print(f"loaded {n} nodes / {e} edges -> {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
