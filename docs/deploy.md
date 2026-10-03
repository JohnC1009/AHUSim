# Deploying (M3-8)

Status: **ready, waiting on the owner** for three accounts and one choice
(CLAUDE.md rule 9: hosting and accounts are the owner's call):

1. **Clerk** (sign-in) — create an application.
2. **Neon** (Postgres) — create a project and database.
3. **API host** — open question §14-4: Fly.io, Render or Railway. The API ships
   as a container (`api/Dockerfile`), so all three work unchanged.
4. **Vercel** (web) — import the repository.

## Settings

Variable names only; values go in each service's dashboard, never in git.

| Where | Variable | Value |
| --- | --- | --- |
| API host | `DATABASE_URL` | Neon connection string (`postgresql://…?sslmode=require`) |
| API host | `CLERK_JWKS_URL` | `https://<clerk-frontend-api>/.well-known/jwks.json` |
| API host | `CLERK_ISSUER` | `https://<clerk-frontend-api>` |
| API host | `CLERK_AUTHORIZED_PARTIES` | the Vercel URL, e.g. `https://ahuverify.vercel.app` |
| API host | `CORS_ORIGINS` | the same Vercel URL |
| API host | `PORT` | set by the host (default 8000) |
| Vercel | `VITE_API_URL` | the API's public URL |
| Vercel | `VITE_CLERK_PUBLISHABLE_KEY` | from Clerk |

`ENV` defaults to `production` in the container, where `AUTH_MODE=dev` is refused.

## API

Build from the repository root: `docker build -f api/Dockerfile -t ahuverify-api .`
On start the container applies database migrations, then serves on `$PORT`.

Verified locally (2026-10-03): image builds; against Postgres 16 it migrates a
fresh database to revision 0001, serves, answers an unsigned request with
401 and a plain sentence, and refuses to start with `AUTH_MODE=dev`.

## Web

Vercel project root: `web/`. `web/vercel.json` sets the build and sends every
route to `index.html` (client-side routing).

## Local development (no accounts needed)

```bash
. .venv/bin/activate
cd api && ENV=development AUTH_MODE=dev uvicorn app.main:app --reload    # http://localhost:8000
cd web && VITE_AUTH_MODE=dev npm run dev                                 # http://localhost:5173
cd web && npm run e2e    # smoke test: builds the §6.1 unit from blank (starts its own servers)
```
