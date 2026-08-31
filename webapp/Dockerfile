FROM python:3.12-slim

WORKDIR /srv

RUN adduser --disabled-password --gecos "" app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY schema.sql load_graph.py ./
COPY app ./app
COPY static ./static
# The graph is baked in at build time: read-only at runtime, so no Fly volume.
COPY resume-graph.jsonld ./
RUN python load_graph.py resume-graph.jsonld graph.db && rm resume-graph.jsonld

USER app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
