#!/usr/bin/env python3
"""Build a knowledge-worker ingest candidates file from src/resume.md.

Deterministic stand-in for `mykg ingest --backend claude`: no LLM, so the graph
is reproducible and every fact is traceable to a resume line. The output still
goes through the real validate -> review -> merge path via
`mykg ingest src/resume.md --candidates-file src/resume.candidates.json`.

Excerpts are never typed by hand. Each node carries a `locator`, and the excerpt
is lifted verbatim from the line of resume.md containing it, so the validator's
substring check (mygraph/validator.py, provenance-or-bust) cannot fail silently.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESUME = HERE / "resume.md"
OUT = HERE / "resume.candidates.json"

WS_RE = re.compile(r"\s+")


def norm(s: str) -> str:
    """Mirror of mygraph.validator._norm."""
    return WS_RE.sub(" ", s).strip().lower()


SOURCE_ID = "source:resume"

# (id, type, label, locator, body)
NODES: list[tuple[str, str, str, str, str]] = [
    ("person:rahul-rangarao", "person", "Rahul Rangarao", "# Rahul Rangarao",
     "Analytics engineer, data engineer, and data platform engineer."),

    # --- goals -------------------------------------------------------------
    ("goal:durable-agent-memory", "goal", "Durable, provenance-backed AI memory",
     "durable, provenance-backed AI memory",
     "Give AI assistants memory that survives across sessions."),
    ("goal:provenance-invariant", "goal", "Enforce a hard provenance invariant",
     "hard provenance invariant",
     "Every claim in the graph must cite the source it came from."),

    # --- projects ----------------------------------------------------------
    ("project:knowledge-worker", "project", "knowledge-worker",
     "Local-first knowledge graph for durable, provenance-backed AI memory",
     "Local-first knowledge graph published on PyPI."),
    ("project:batch-traceability", "project", "Batch traceability data product",
     "batch traceability data product",
     "Graph-database traceability product accelerating batch release by 8%."),
    ("project:cart-data-product", "project", "CAR-T quality and manufacturing data product",
     "800+ quality and manufacturing data points",
     "End-to-end data product behind the 74% to 92% success-rate improvement."),
    ("project:self-service-platform", "project", "Enterprise self-service analytics platform",
     "self-service analytics platform",
     "dbt, AWS Glue, Databricks and CI/CD platform serving 50+ engineers."),
    ("project:cxo-dashboards", "project", "CXO-level KPI dashboards",
     "CXO-level KPI dashboards",
     "Executive reporting standardising enterprise KPIs."),
    ("project:report-rationalization", "project", "Report rationalization",
     "report rationalization process",
     "Consolidated 70+ reports into seven standardized reports."),
    ("project:risk-prediction-model", "project", "Enterprise risk prediction model",
     "risk prediction model",
     "Fintech retention model preserving roughly $500K in recurring revenue."),
    ("project:kompress-ultra", "project", "kompress-ultra",
     "kompress-ultra",
     "Context-management middleware experiments for AI agent frameworks."),
    ("project:ag-ui-protocol", "project", "AG-UI protocol",
     "AG-UI protocol",
     "Open protocol work for agent/UI interoperability."),

    # --- decisions ---------------------------------------------------------
    ("decision:provenance-first-architecture", "decision", "Validate every document before ingestion",
     "provenance-first knowledge graph architecture",
     "Deterministic validation gates ingestion, so untraceable claims never land."),
    ("decision:append-only-storage", "decision", "Use append-only graph storage",
     "append-only graph storage",
     "History is preserved rather than overwritten."),
    ("decision:zero-runtime-dependencies", "decision", "Keep the core dependency-free",
     "zero runtime dependencies",
     "LLM backends and RDF export stay optional extras."),
    ("decision:graph-db-for-traceability", "decision", "Model batch traceability as a graph",
     "graph database (AWS Neptune)",
     "Traceability is a path problem, so it was modelled on a graph database."),
    ("decision:medallion-architecture", "decision", "Adopt a Medallion architecture",
     "Medallion architecture",
     "Layered bronze/silver/gold modelling for the self-service platform."),

    # --- ideas -------------------------------------------------------------
    ("idea:offline-graph-visualizer", "idea", "Offline HTML graph visualizer",
     "offline HTML graph visualizer",
     "Inspect the graph without a server or build step."),
    ("idea:benchmark-suite", "idea", "Benchmark provenance and privacy boundaries",
     "9-benchmark public test suite",
     "Guards provenance, recall, privacy boundaries and context compactness."),
    ("idea:context-export", "idea", "Export compact context for an LLM",
     "context export",
     "Ship a small snapshot instead of dumping whole notes."),

    # --- organisations, education, awards, links ---------------------------
    ("reference:bristol-myers-squibb", "reference", "Bristol Myers Squibb",
     "Bristol Myers Squibb · Analytics Engineer", "Employer since October 2023."),
    ("reference:mu-sigma", "reference", "Mu Sigma Inc.",
     "Mu Sigma Inc. · Senior Data Consultant", "Employer from July 2018 to March 2022."),
    ("reference:ut-austin", "reference", "The University of Texas at Austin",
     "The University of Texas at Austin", "M.S. Information Technology & Management."),
    ("reference:jss-university", "reference", "JSS Science and Technology University",
     "JSS Science and Technology University", "B.E. Electronics & Communication Engineering."),
    ("reference:pypi", "reference", "PyPI", "https://pypi.org/project/knowledge-worker/",
     "knowledge-worker is published to PyPI."),
    ("reference:dfs-hackathon", "reference", "1st Place, DFS Hackathon",
     "1st Place, DFS Hackathon", "Dover Fueling Solutions, September 2022."),
    ("reference:bravo-batch-genealogy", "reference", "Bravo Award, Batch Genealogy",
     "Bravo Award, Batch Genealogy Data Product Release 4", "Bristol Myers Squibb, April 2026."),
    ("reference:bravo-aws-tech-stack", "reference", "Bravo Award, AE AWS Tech Stack",
     "Bravo Award, AE AWS Tech Stack Implementation", "Bristol Myers Squibb, July 2025."),
    ("reference:bravo-daily-aph", "reference", "Bravo Award, Daily Aph vs. Budget Reporting",
     "Bravo Award, Daily Aph vs. Budget Reporting", "Bristol Myers Squibb, August 2024."),
    ("reference:impact-award", "reference", "Impact Award", "**Impact Award**",
     "Mu Sigma Inc., August 2021."),
    ("reference:snowflake-certification", "reference", "Snowflake data warehouse certification",
     "Hands-on Essentials: Data Warehouse", "Snowflake, October 2022."),
]

# Skills: id suffix -> (label, locator). Locator must appear in resume.md.
TOPICS: list[tuple[str, str, str]] = [
    ("python", "Python", "Python, SQL, JavaScript (React)"),
    ("sql", "SQL", "Python, SQL, JavaScript (React)"),
    ("dbt", "dbt", "dbt, AWS Glue, Dagster"),
    ("aws-glue", "AWS Glue", "dbt, AWS Glue, Dagster"),
    ("dagster", "Dagster", "dbt, AWS Glue, Dagster"),
    ("snowflake", "Snowflake", "Snowflake, Databricks"),
    ("databricks", "Databricks", "Snowflake, Databricks"),
    ("data-modeling", "Data modeling", "data modeling"),
    ("data-warehousing", "Data warehousing", "data warehousing"),
    ("analytics-engineering", "Analytics engineering", "analytics engineering"),
    ("unified-data-model", "Unified Data Model", "Unified Data Model"),
    ("enterprise-reporting", "Enterprise reporting", "enterprise reporting"),
    ("data-product-development", "Data product development", "data product development"),
    ("llm", "Large language models", "LLMs, LLM orchestration"),
    ("llm-orchestration", "LLM orchestration", "LLMs, LLM orchestration"),
    ("prompt-engineering", "Prompt engineering", "prompt engineering"),
    ("rag", "Retrieval-augmented generation", "retrieval-augmented generation (RAG)"),
    ("ai-context-management", "AI context management", "AI context management"),
    ("knowledge-graphs", "Knowledge graphs", "knowledge graphs"),
    ("graph-analytics", "Graph analytics", "graph analytics"),
    ("machine-learning", "Machine learning", "machine learning"),
    ("ab-testing", "Hypothesis and A/B testing", "hypothesis & A/B testing"),
    ("aws-neptune", "AWS Neptune", "AWS Neptune"),
    ("json-ld", "JSON-LD", "JSON-LD, RDF, Turtle"),
    ("rdf", "RDF", "JSON-LD, RDF, Turtle"),
    ("turtle", "Turtle", "JSON-LD, RDF, Turtle"),
    ("linked-data", "Linked data", "linked data"),
    ("ci-cd", "CI/CD", "GitHub Actions, CI/CD"),
    ("github-actions", "GitHub Actions", "GitHub Actions, CI/CD"),
    ("tableau", "Tableau", "Tableau, Power BI"),
    ("power-bi", "Power BI", "Tableau, Power BI"),
    ("api-development", "API development", "API development"),
    ("software-architecture", "Software architecture", "software architecture"),
    ("benchmark-testing", "Benchmark testing", "benchmark testing"),
    ("sap", "SAP ERP", "ERP (SAP)"),
    ("car-t", "CAR-T cell therapy", "CAR-T"),
    ("pagerank", "PageRank", "PageRank, betweenness, k-core, community detection"),
    ("betweenness", "Betweenness centrality", "PageRank, betweenness, k-core, community detection"),
    ("k-core", "k-core", "PageRank, betweenness, k-core, community detection"),
    ("community-detection", "Community detection", "PageRank, betweenness, k-core, community detection"),
]

# (src, dst, type)
EDGES: list[tuple[str, str, str]] = [
    # what he worked on
    *[("person:rahul-rangarao", p, "INVOLVES") for p in (
        "project:knowledge-worker", "project:batch-traceability", "project:cart-data-product",
        "project:self-service-platform", "project:cxo-dashboards", "project:report-rationalization",
        "project:risk-prediction-model", "project:kompress-ultra", "project:ag-ui-protocol")],
    # where
    ("person:rahul-rangarao", "reference:bristol-myers-squibb", "RELATES_TO"),
    ("person:rahul-rangarao", "reference:mu-sigma", "RELATES_TO"),
    ("person:rahul-rangarao", "reference:ut-austin", "RELATES_TO"),
    ("person:rahul-rangarao", "reference:jss-university", "RELATES_TO"),
    *[(p, "reference:bristol-myers-squibb", "MADE_AT") for p in (
        "project:batch-traceability", "project:cart-data-product",
        "project:self-service-platform", "project:cxo-dashboards")],
    *[(p, "reference:mu-sigma", "MADE_AT") for p in (
        "project:report-rationalization", "project:risk-prediction-model")],
    # goals and ideas
    ("project:knowledge-worker", "goal:durable-agent-memory", "SERVES"),
    ("project:knowledge-worker", "goal:provenance-invariant", "SERVES"),
    ("project:kompress-ultra", "goal:durable-agent-memory", "SERVES"),
    ("decision:provenance-first-architecture", "goal:provenance-invariant", "SERVES"),
    *[("person:rahul-rangarao", i, "HAS_IDEA") for i in (
        "idea:offline-graph-visualizer", "idea:benchmark-suite", "idea:context-export")],
    *[(i, "project:knowledge-worker", "ABOUT") for i in (
        "idea:offline-graph-visualizer", "idea:benchmark-suite", "idea:context-export")],
    # decisions
    *[(d, "project:knowledge-worker", "ABOUT") for d in (
        "decision:provenance-first-architecture", "decision:append-only-storage",
        "decision:zero-runtime-dependencies")],
    ("decision:graph-db-for-traceability", "project:batch-traceability", "ABOUT"),
    ("decision:medallion-architecture", "project:self-service-platform", "ABOUT"),
    ("decision:provenance-first-architecture", "reference:bristol-myers-squibb", "CHALLENGES"),
    # awards evidence
    ("project:batch-traceability", "reference:bravo-batch-genealogy", "SUPPORTED_BY"),
    ("project:self-service-platform", "reference:bravo-aws-tech-stack", "SUPPORTED_BY"),
    ("project:cxo-dashboards", "reference:bravo-daily-aph", "SUPPORTED_BY"),
    ("project:report-rationalization", "reference:impact-award", "SUPPORTED_BY"),
    ("project:knowledge-worker", "reference:pypi", "SUPPORTED_BY"),
    ("reference:snowflake-certification", "topic:snowflake", "ABOUT"),
    ("person:rahul-rangarao", "reference:dfs-hackathon", "SUPPORTED_BY"),
    # which tech each project used
    *[("project:knowledge-worker", f"topic:{t}", "ABOUT") for t in (
        "python", "knowledge-graphs", "graph-analytics", "json-ld", "rdf", "turtle",
        "linked-data", "llm", "pagerank", "betweenness", "k-core", "community-detection",
        "github-actions", "ci-cd", "benchmark-testing", "api-development",
        "software-architecture", "ai-context-management")],
    *[("project:batch-traceability", f"topic:{t}", "ABOUT") for t in (
        "aws-neptune", "sap", "llm", "knowledge-graphs", "car-t")],
    *[("project:cart-data-product", f"topic:{t}", "ABOUT") for t in ("car-t", "data-product-development")],
    *[("project:self-service-platform", f"topic:{t}", "ABOUT") for t in (
        "dbt", "aws-glue", "databricks", "ci-cd", "unified-data-model",
        "analytics-engineering", "data-modeling", "data-warehousing")],
    *[("project:cxo-dashboards", f"topic:{t}", "ABOUT") for t in (
        "python", "enterprise-reporting", "tableau", "power-bi")],
    *[("project:report-rationalization", f"topic:{t}", "ABOUT") for t in (
        "snowflake", "enterprise-reporting")],
    *[("project:risk-prediction-model", f"topic:{t}", "ABOUT") for t in (
        "machine-learning", "ab-testing")],
    *[("project:kompress-ultra", f"topic:{t}", "ABOUT") for t in (
        "ai-context-management", "knowledge-graphs")],
    *[("project:ag-ui-protocol", f"topic:{t}", "ABOUT") for t in ("api-development",)],
    *[("person:rahul-rangarao", f"topic:{t}", "RELATES_TO") for t in (
        "python", "sql", "analytics-engineering", "graph-analytics", "prompt-engineering",
        "rag", "llm-orchestration")],
]


def find_excerpt(text_lines: list[str], locator: str, node_id: str) -> str:
    """Return the resume.md line containing `locator`, verbatim."""
    target = norm(locator)
    for line in text_lines:
        if target in norm(line):
            return line.strip().lstrip("-").lstrip("#").strip()
    raise SystemExit(f"build_candidates: locator not found in resume.md for {node_id}: {locator!r}")


def main() -> int:
    text = RESUME.read_text(encoding="utf-8")
    lines = text.splitlines()
    src_norm = norm(text)

    nodes: list[dict] = []
    for nid, ntype, label, locator, body in NODES:
        nodes.append({"id": nid, "type": ntype, "label": label, "body": body,
                      "confidence": "high", "excerpt": find_excerpt(lines, locator, nid)})
    for suffix, label, locator in TOPICS:
        nid = f"topic:{suffix}"
        nodes.append({"id": nid, "type": "topic", "label": label,
                      "body": f"{label}, from the resume skills matrix.",
                      "confidence": "high", "excerpt": find_excerpt(lines, locator, nid)})

    by_id = {n["id"]: n for n in nodes}

    edges: list[dict] = []
    # provenance: every node cites the resume line it came from
    for n in nodes:
        edges.append({"src": n["id"], "dst": SOURCE_ID, "type": "MENTIONED_IN",
                      "confidence": "high", "excerpt": n["excerpt"]})
    for src, dst, etype in EDGES:
        for ep in (src, dst):
            if ep not in by_id:
                raise SystemExit(f"build_candidates: edge endpoint not among nodes: {ep}")
        edges.append({"src": src, "dst": dst, "type": etype, "confidence": "high",
                      "excerpt": by_id[src]["excerpt"]})

    # fail loudly rather than let the validator silently demote to `low`
    bad = [n["id"] for n in nodes if norm(n["excerpt"]) not in src_norm]
    if bad:
        raise SystemExit(f"build_candidates: excerpt not a substring of resume.md: {bad}")

    payload = {
        "source": {
            "id": SOURCE_ID,
            "label": "Rahul Rangarao — resume",
            "body": "Canonical resume at src/resume.md. Public content only.",
        },
        "nodes": nodes,
        "edges": edges,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}: {len(nodes)} nodes / {len(edges)} edges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
