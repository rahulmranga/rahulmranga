# rahulrangarao.dev/app

FastAPI + SQLite app serving the knowledge-worker graph built from the resume.
Deployed on Fly.io; Cloudflare routes `rahulrangarao.dev/app/*` here while every
other path stays on GitHub Pages.

Kept in its own repo on purpose: the Pages repo is a Jekyll site, and app source
sitting in it would be copied into the published output.

## Routes

| route | what it does |
|---|---|
| `/app` | graph summary, type browser, live search |
| `/app/type/{type}` | every node of one type |
| `/app/node/{id}` | a node, its provenance excerpt, and its neighbourhood |
| `/app/search?q=` | search; returns an HTMX fragment when asked for one |
| `/app/sql` | read-only SQL query box |
| `/app/contact` | contact form → Resend, behind Turnstile and a honeypot |
| `/app/health` | node/edge counts, used by the Fly health check |

## The data

`graph.db` is **generated, never edited**. It is rebuilt inside the Docker image
from `resume-graph.jsonld`, which `mykg` exports from `../rahulmranga/src/resume.md`.
To refresh after the resume changes:

```bash
cd ../rahulmranga
export MYGRAPH_PATH="$PWD/resume-graph.jsonld"
python3 src/build_candidates.py
../.venv/bin/mykg ingest src/resume.md --candidates-file src/resume.candidates.json --non-interactive
../.venv/bin/mykg check --provenance          # must report 0 violations
cp resume-graph.jsonld ../rahulrangarao-app/
```

`load_graph.py` re-checks the provenance invariant at load time and refuses to
build a database where a non-source node has no `MENTIONED_IN` edge.

## Why `/app/sql` is safe to expose

Four independent layers, because any one of them can be wrong:

1. the file is opened `mode=ro` — the driver itself refuses writes
2. a sqlite3 **authorizer** denies every action except reading `nodes`/`edges`/`nodes_fts`
3. a statement guard rejects anything that is not a single `SELECT`/`WITH`
4. a progress handler aborts after 2s, and results are capped at 200 rows

Layer 3 alone would let `SELECT * FROM sqlite_master` through; layer 2 stops it.

## Local development

```bash
python load_graph.py ../rahulmranga/resume-graph.jsonld graph.db
uvicorn app.main:app --reload --port 8099
```

## Deploy

```bash
fly launch --no-deploy          # first time only
fly secrets set TURNSTILE_SECRET=0x4... TURNSTILE_SITE_KEY=0x4...

# mail: either a Gmail App Password (no new vendor) ...
fly secrets set SMTP_USER=rahulmranga@gmail.com SMTP_PASS='<16-char app password>'
# ... or Resend
fly secrets set RESEND_API_KEY=re_...
fly deploy
fly scale show                  # expect shared-cpu-1x / 256MB, no volume
```

Then publish the router in `worker/`:

```bash
cd worker
npx wrangler login
npx wrangler deploy
```

`wrangler.toml` already declares both routes (`/app` and `/app/*`) on the
rahulrangarao.dev zone. Origin Rules could do this without a Worker, but
rewriting the origin host there is a paid feature; Workers are free to 100k
requests/day.

Mail has two paths and picks whichever is configured, SMTP first: `SMTP_USER` +
`SMTP_PASS` (Gmail App Password, STARTTLS on 587, which Fly allows outbound), or
`RESEND_API_KEY`. With neither, the form validates and rejects politely rather
than pretending to send. Gmail rewrites a `From` that is not the authenticated
mailbox, so the visitor's address is set as `Reply-To` instead. Without `TURNSTILE_SITE_KEY` the widget is omitted and
the honeypot plus rate limit still apply — fine locally, not for production.
