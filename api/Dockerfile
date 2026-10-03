# API container (spec §3: FastAPI + Uvicorn). Host-neutral: Fly.io, Render and
# Railway all run this as-is. Build from the repository root:
#   docker build -f api/Dockerfile -t ahuverify-api .
FROM python:3.12-slim

WORKDIR /srv
COPY engine/ engine/
COPY api/ api/
RUN pip install --no-cache-dir ./engine ./api \
 && useradd --create-home --uid 10001 app
USER app
WORKDIR /srv/api

ENV ENV=production PORT=8000
EXPOSE 8000
# Apply database migrations, then serve. DATABASE_URL, CLERK_JWKS_URL,
# CLERK_ISSUER, CLERK_AUTHORIZED_PARTIES and CORS_ORIGINS come from the host.
CMD ["sh", "-c", "python -c 'import os; from app.db import migrate; migrate(os.environ[\"DATABASE_URL\"])' && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
