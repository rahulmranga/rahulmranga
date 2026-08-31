"""FastAPI app served at rahulrangarao.dev/app via a Cloudflare route.

Everything under /app is dynamic; the rest of the domain stays on GitHub Pages.
"""
from __future__ import annotations

import os
import re
import smtplib
import time
from email.message import EmailMessage
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape

from . import db

BASE = Path(__file__).resolve().parent
app = FastAPI(title="rahulrangarao.dev/app", docs_url=None, redoc_url=None)
app.mount("/app/static", StaticFiles(directory=BASE.parent / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def _md_bold(text: str) -> Markup:
    """Render **bold** in resume excerpts without trusting the excerpt as HTML.

    Excerpts are stored verbatim so the graph's provenance stays byte-identical
    to resume.md, which means the markdown markers travel with them. Escape
    first, then convert, so this stays safe even though the source is our own.
    """
    escaped = escape(text or "")
    return Markup(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped))


templates.env.filters["md_bold"] = _md_bold

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# SMTP is the no-new-vendor path: a Gmail App Password sends to the same inbox
# the mail is destined for. Whichever of the two is configured wins, SMTP first.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "")
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
CONTACT_TO = os.environ.get("CONTACT_TO", "rahulmranga@gmail.com")
CONTACT_FROM = os.environ.get("CONTACT_FROM", "site@rahulrangarao.dev")

EXAMPLE_QUERIES = [
    ("What is every claim backed by?",
     "SELECT n.label, e.excerpt\nFROM nodes n JOIN edges e ON e.src = n.id\nWHERE e.type = 'MENTIONED_IN'\nLIMIT 20"),
    ("Which technologies show up in the most projects?",
     "SELECT n.label, COUNT(*) AS projects\nFROM edges e JOIN nodes n ON n.id = e.dst\nWHERE e.type = 'ABOUT' AND n.type = 'topic'\nGROUP BY n.label\nORDER BY projects DESC\nLIMIT 15"),
    ("What was built where?",
     "SELECT p.label AS project, o.label AS org\nFROM edges e\nJOIN nodes p ON p.id = e.src\nJOIN nodes o ON o.id = e.dst\nWHERE e.type = 'MADE_AT'"),
    ("Which work has award evidence?",
     "SELECT p.label AS project, a.label AS evidence\nFROM edges e\nJOIN nodes p ON p.id = e.src\nJOIN nodes a ON a.id = e.dst\nWHERE e.type = 'SUPPORTED_BY'"),
    ("Most connected nodes",
     "SELECT n.label, n.type, COUNT(*) AS degree\nFROM edges e JOIN nodes n ON n.id IN (e.src, e.dst)\nGROUP BY n.id\nORDER BY degree DESC\nLIMIT 15"),
]

# naive in-process rate limit; the machine is single-instance and this only
# needs to stop casual abuse, not a determined flood (Cloudflare handles that)
_hits: dict[str, deque] = defaultdict(deque)


def _rate_limited(key: str, limit: int, window: float) -> bool:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def _client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown"))


@app.get("/app", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"summary": db.summary(), "examples": EXAMPLE_QUERIES})


@app.get("/app/type/{node_type}", response_class=HTMLResponse)
def by_type(request: Request, node_type: str):
    return templates.TemplateResponse(request, "list.html", {"node_type": node_type, "nodes": db.nodes_of_type(node_type)})


@app.get("/app/node/{node_id:path}", response_class=HTMLResponse)
def node_detail(request: Request, node_id: str):
    row = db.node(node_id)
    if row is None:
        return templates.TemplateResponse(request, "404.html", {"node_id": node_id}, status_code=404)
    return templates.TemplateResponse(request, "node.html", {"node": row, "nbr": db.neighbourhood(node_id)})


@app.get("/app/search", response_class=HTMLResponse)
def search(request: Request, q: str = ""):
    results = db.search(q)
    # HTMX asks for the fragment; a direct visit gets the whole page
    name = "_results.html" if request.headers.get("hx-request") else "search.html"
    return templates.TemplateResponse(request, name, {"q": q, "results": results})


@app.get("/app/sql", response_class=HTMLResponse)
def sql_form(request: Request, q: str = ""):
    return templates.TemplateResponse(request, "sql.html", {"q": q, "examples": EXAMPLE_QUERIES,
        "cols": None, "rows": None, "error": None, "truncated": False})


@app.post("/app/sql", response_class=HTMLResponse)
def sql_run(request: Request, q: str = Form("")):
    if _rate_limited(f"sql:{_client_ip(request)}", limit=30, window=60):
        ctx = {"error": "Too many queries — give it a minute."}
        cols = rows = None
        truncated = False
    else:
        ctx, cols, rows, truncated = {}, None, None, False
        try:
            cols, rows, truncated = db.run_query(q)
        except db.QueryError as exc:
            ctx = {"error": str(exc)}
    name = "_table.html" if request.headers.get("hx-request") else "sql.html"
    return templates.TemplateResponse(request, name, {"q": q, "examples": EXAMPLE_QUERIES,
        "cols": cols, "rows": rows, "truncated": truncated, "error": ctx.get("error")})


@app.get("/app/contact", response_class=HTMLResponse)
def contact_form(request: Request):
    return templates.TemplateResponse(request, "contact.html", {"site_key": TURNSTILE_SITE_KEY, "sent": False, "error": None})


def _send_smtp(subject: str, body: str, reply_to: str) -> None:
    """Blocking send; call via run_in_threadpool. STARTTLS on 587."""
    msg = EmailMessage()
    msg["Subject"] = subject
    # From must be the authenticated mailbox or Gmail rewrites/rejects it;
    # the visitor's address goes in Reply-To so a reply reaches them.
    msg["From"] = SMTP_USER
    msg["To"] = CONTACT_TO
    msg["Reply-To"] = reply_to
    msg.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)


async def _turnstile_ok(token: str, ip: str) -> bool:
    if not TURNSTILE_SECRET:
        return True  # unconfigured in local dev; honeypot still applies
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": TURNSTILE_SECRET, "response": token, "remoteip": ip})
    return bool(r.json().get("success"))


@app.post("/app/contact", response_class=HTMLResponse)
async def contact_send(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    message: str = Form(""),
    website: str = Form(""),                       # honeypot: real users leave it empty
    cf_turnstile_response: str = Form("", alias="cf-turnstile-response"),
):
    def render(sent: bool, error: str | None):
        return templates.TemplateResponse(request, "contact.html", {"site_key": TURNSTILE_SITE_KEY, "sent": sent,
            "error": error, "name": name, "email": email, "message": message})

    if website:
        return render(True, None)                  # bot: pretend success, send nothing
    if _rate_limited(f"contact:{_client_ip(request)}", limit=3, window=3600):
        return render(False, "That's a few too many messages for one hour.")
    if not (name.strip() and email.strip() and message.strip()):
        return render(False, "Name, email and a message, please.")
    if len(message) > 5000:
        return render(False, "That message is longer than this form accepts.")
    if not await _turnstile_ok(cf_turnstile_response, _client_ip(request)):
        return render(False, "The anti-spam check did not pass. Please try again.")
    subject = f"rahulrangarao.dev — message from {name}"
    body = f"From: {name} <{email}>\n\n{message}"

    if SMTP_USER and SMTP_PASS:
        try:
            await run_in_threadpool(_send_smtp, subject, body, email)
        except Exception:
            return render(False, "Sending failed. Please try again shortly.")
        return render(True, None)

    if not RESEND_API_KEY:
        return render(False, "Mail is not configured on this deployment yet.")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": CONTACT_FROM, "to": [CONTACT_TO], "reply_to": email,
                  "subject": subject, "text": body})
    if r.status_code >= 300:
        return render(False, "Sending failed. Please try again shortly.")
    return render(True, None)


@app.get("/app/health")
def health():
    s = db.summary()
    return JSONResponse({"ok": True, "nodes": s["nodes"], "edges": s["edges"]})
