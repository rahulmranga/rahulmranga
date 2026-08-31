-- Read-only projection of the knowledge-worker graph for /app.
-- Rebuilt from resume-graph.jsonld at image build time; never written at runtime.

DROP TABLE IF EXISTS edges;
DROP TABLE IF EXISTS nodes;
DROP TABLE IF EXISTS nodes_fts;

CREATE TABLE nodes (
  id         TEXT PRIMARY KEY,
  type       TEXT NOT NULL,
  label      TEXT NOT NULL,
  body       TEXT,
  confidence TEXT,
  created_at TEXT
);

CREATE TABLE edges (
  src        TEXT NOT NULL REFERENCES nodes(id),
  dst        TEXT NOT NULL REFERENCES nodes(id),
  type       TEXT NOT NULL,
  confidence TEXT,
  excerpt    TEXT,
  source_id  TEXT,
  created_at TEXT
);

CREATE INDEX idx_edges_src  ON edges(src);
CREATE INDEX idx_edges_dst  ON edges(dst);
CREATE INDEX idx_edges_type ON edges(type);
CREATE INDEX idx_nodes_type ON nodes(type);

-- Search over label + body. contentless-external so it stays in sync with nodes.
CREATE VIRTUAL TABLE nodes_fts USING fts5(
  id UNINDEXED, label, body, content='nodes', content_rowid='rowid'
);
