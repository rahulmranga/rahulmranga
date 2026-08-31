#!/usr/bin/env python3
"""Generate resume.html from src/resume.md.

resume.md is the single source of truth: it feeds both this page and the
knowledge graph (src/build_candidates.py), so the two cannot drift. Output is
committed, so GitHub Pages still serves a plain static file with no build step.

    python3 src/build_resume_html.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RESUME_MD = HERE / "resume.md"
OUT = REPO / "resume.html"

# Public Turnstile site key for rahulrangarao.dev. Safe to commit: verification
# happens server-side in the app against TURNSTILE_SECRET, which is a Fly secret.
TURNSTILE_SITE_KEY = "0x4AAAAAAEi-usRhFYtq3ztw"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def inline(text: str) -> str:
    """Markdown inline -> HTML, escaping first so resume.md is never trusted as HTML."""
    out = html.escape(text, quote=False)
    out = LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', out)
    out = BOLD_RE.sub(r"<strong>\1</strong>", out)
    return out


def parse(md: str) -> dict:
    """Split resume.md into the blocks the template needs."""
    lines = md.splitlines()
    doc: dict = {"name": "", "headline": "", "subhead": "", "contact": "", "sections": []}
    section: dict | None = None
    i = 0

    # header block: # Name, **headline**, subhead, contact line
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            if doc["contact"]:
                break
            continue
        if line.startswith("# "):
            doc["name"] = line[2:].strip()
        elif line.startswith("**") and not doc["headline"]:
            doc["headline"] = line.strip("*").strip()
        elif not doc["subhead"] and "·" in line and "](" not in line:
            doc["subhead"] = line
        else:
            doc["contact"] = line

    for line in lines[i:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            section = {"title": stripped[3:].strip(), "blocks": []}
            doc["sections"].append(section)
        elif section is None:
            continue
        elif stripped.startswith("### "):
            section["blocks"].append({"kind": "role", "text": stripped[4:].strip(), "meta": ""})
        elif stripped.startswith("- "):
            blocks = section["blocks"]
            if not blocks or blocks[-1]["kind"] != "list":
                blocks.append({"kind": "list", "items": []})
            blocks[-1]["items"].append(stripped[2:].strip())
        elif stripped:
            blocks = section["blocks"]
            # a bare line straight after a ### is that role's date/location meta
            if blocks and blocks[-1]["kind"] == "role" and not blocks[-1]["meta"]:
                blocks[-1]["meta"] = stripped
            else:
                blocks.append({"kind": "para", "text": stripped})
    return doc


def render_role(text: str) -> str:
    if " · " in text:
        org, role = text.split(" · ", 1)
        return f"<h3>{inline(org)} <span class=\"role\">· {inline(role)}</span></h3>"
    return f"<h3>{inline(text)}</h3>"


def render_skills(items: list[str]) -> str:
    """`- **Label** — values` renders as the two-column definition grid."""
    rows = []
    for item in items:
        m = re.match(r"\*\*(.+?)\*\*\s*[—-]\s*(.*)", item)
        if m:
            rows.append(f"    <dt>{inline(m.group(1))}</dt><dd>{inline(m.group(2))}</dd>")
        else:
            rows.append(f"    <dd>{inline(item)}</dd>")
    return '  <dl class="skills-grid">\n' + "\n".join(rows) + "\n  </dl>"


def render(doc: dict, style: str) -> str:
    parts: list[str] = []
    for sec in doc["sections"]:
        parts.append("<section>")
        parts.append(f'  <h2>{html.escape(sec["title"])}</h2>')
        for block in sec["blocks"]:
            if block["kind"] == "role":
                parts.append("  " + render_role(block["text"]))
                if block["meta"]:
                    parts.append(f'  <div class="meta">{inline(block["meta"])}</div>')
            elif block["kind"] == "list":
                if sec["title"] == "Technical Skills":
                    parts.append(render_skills(block["items"]))
                else:
                    parts.append("  <ul>")
                    parts.extend(f"    <li>{inline(x)}</li>" for x in block["items"])
                    parts.append("  </ul>")
            else:
                cls = ' class="summary"' if sec["title"] == "Summary" else ""
                parts.append(f'  <p{cls}>{inline(block["text"])}</p>')
        parts.append("</section>\n")

    body = "\n".join(parts)
    name = html.escape(doc["name"])
    headline = inline(doc["headline"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} · Resume</title>
<meta name="description" content="{html.escape(doc['headline'], quote=True)}">
<link rel="canonical" href="https://rahulrangarao.dev/resume.html">
<!-- Generated from src/resume.md by src/build_resume_html.py. Do not edit by hand. -->
<style>
{style}
</style>
</head>
<body>

<a class="home-link" href="https://rahulrangarao.dev">← rahulrangarao.dev</a>

<header>
  <h1>{name}</h1>
  <div class="tagline">{headline}</div>
  <div class="contact">{inline(doc["subhead"])} · {inline(doc["contact"])}</div>
</header>

{body}
<section id="contact">
  <h2>Contact</h2>
  <p class="summary">The form goes straight to my inbox. It is handled by the app at
  <code>/app/contact</code>, so it works without exposing an address to scrapers.</p>
  <form class="contact-form" method="post" action="/app/contact">
    <label>Name<input name="name" required maxlength="120"></label>
    <label>Email<input name="email" type="email" required maxlength="200"></label>
    <label>Message<textarea name="message" rows="5" required maxlength="5000"></textarea></label>
    <div class="hp"><label>Website<input name="website" tabindex="-1" autocomplete="off"></label></div>
    <div class="cf-turnstile" data-sitekey="{TURNSTILE_SITE_KEY}"></div>
    <button type="submit">Send</button>
  </form>
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</section>

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "ProfilePage",
  "@id": "https://rahulrangarao.dev/resume.html#profilepage",
  "url": "https://rahulrangarao.dev/resume.html",
  "name": "{name} · Resume",
  "mainEntity": {{
    "@type": "Person",
    "@id": "https://rahulrangarao.dev/#rahul",
    "name": "{name}",
    "jobTitle": ["Analytics Engineer", "Data Engineer", "Data Platform Engineer",
                 "Data Product Engineer"],
    "url": "https://rahulrangarao.dev/",
    "address": {{
      "@type": "PostalAddress",
      "addressRegion": "New York Metro Area",
      "addressCountry": "US"
    }},
    "worksFor": {{
      "@type": "Organization",
      "name": "Bristol Myers Squibb"
    }},
    "alumniOf": [
      {{"@type": "CollegeOrUniversity", "name": "The University of Texas at Austin"}},
      {{"@type": "CollegeOrUniversity", "name": "JSS Science and Technology University"}}
    ],
    "knowsAbout": [
      "analytics engineering", "data engineering", "data platform engineering",
      "dbt", "Snowflake", "Databricks", "AWS", "knowledge graphs", "graph analytics",
      "provenance and attribution in AI systems", "pharmaceutical manufacturing"
    ],
    "sameAs": [
      "https://github.com/rahulmranga",
      "https://www.linkedin.com/in/rahul-mohan/",
      "https://medium.com/@rahulmohanrangarao",
      "https://dev.to/rahulmranga"
    ]
  }}
}}
</script>

</body>
</html>
"""


EXTRA_CSS = """
  .contact-form { max-width: 460px; }
  .contact-form label { display: block; margin-top: 10px; font-size: 9pt;
    font-weight: 700; color: var(--muted); }
  .contact-form input, .contact-form textarea {
    width: 100%; margin-top: 3px; padding: 8px 10px; font: inherit;
    border: 1.5px solid var(--rule); border-radius: 8px; background: #fff; color: var(--ink); }
  .contact-form button { margin-top: 12px; padding: 9px 20px; border: 0; border-radius: 8px;
    background: var(--accent); color: #fff; font: 600 10pt inherit; cursor: pointer; }
  .contact-form button:hover { background: #1c2766; }
  .hp { position: absolute; left: -9999px; }
  @media print { #contact { display: none; } }
"""


def main() -> int:
    md = RESUME_MD.read_text(encoding="utf-8")
    previous = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    m = re.search(r"<style>\n(.*?)\n</style>", previous, re.S)
    if not m:
        print("build_resume_html: could not reuse the existing <style> block", file=sys.stderr)
        return 1
    style = m.group(1).rstrip()
    if ".contact-form" not in style:
        style += "\n" + EXTRA_CSS.rstrip()

    OUT.write_text(render(parse(md), style), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} from {RESUME_MD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
