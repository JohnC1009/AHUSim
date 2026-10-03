# 0006 — M3 web app: decisions and deviations

Status: made during M3 under CLAUDE.md rules 7 and 9; ⚑ = owner may overturn.

## Waiting on the owner

- **⚑ M3-8 deploy** needs Clerk, Neon, an API host (§14-4) and Vercel — see
  `docs/deploy.md`. Everything else in M3 runs locally.

## API

- Every endpoint needs a Clerk session token (RS256 JWT checked against Clerk's
  JWKS: signature, expiry, issuer, and `azp` when configured).
- **⚑ `AUTH_MODE=dev`** skips sign-in for local work and the Playwright smoke
  test. It is refused when `ENV=production` (tested, and checked in the container).
- Access is owner-only until M5 brings organizations and `require()`. Another
  user's project or unit answers **404**, so ids do not leak.
- **⚑ `GET /v1/schema`** (not in the spec's endpoint list) serves the config
  JSON Schema; the web app uses the committed copy, so it is a convenience.
- Responses carry the site pressure `p` (the browser must not compute it from
  altitude) and every number already in I-P or SI (`ahuverify/report.py`,
  `chart.py`): the web app converts nothing.
- A new unit starts from a valid blank config: boundaries only, 10,000 cfm
  supply, 2,000 cfm minimum OA, no pressurization bias.
- Unit versions store config / sequence / conditions as JSONB (spec §7.1);
  the `runs` table exists and is written from M5.
- ⚑ Failure messages stay in I-P even in SI view (they are built in the
  engine); values and limits in the response are SI. Revisit if an SI user
  needs them.

## Schema

- `Conditions.operating`: a unit stores its named operating points, so a
  saved unit carries the conditions it is checked at.

## Web

- **Schema-driven inspector**: forms come from the engine's JSON Schema, so
  every component type has an editor and new ones need no UI work.
- **Component templates**: a part dropped in starts at the §6.1 / 0002 values
  (I-P), so a first-time user can build a unit quickly.
- Palette rule: one + slot → single-lane parts (return lane: fan, filter);
  a slot in each lane → wheels, exchangers, mixing box (one max).
- Return lane drawn right-to-left under the supply lane, with parts in both
  lanes in one column (as on a drawing).
- New operating conditions start at illustrative 91 °F / 74 °F (not ASHRAE
  data, §14-3).
- Parameter edits re-solve the selected condition after 300 ms (spec §8.2).

## Dependencies (pinned)

Python: fastapi 0.142.2, uvicorn 0.54.0, sqlalchemy 2.1.3, alembic 1.20.0,
psycopg[binary] 3.3.6, pyjwt 2.15.1, cryptography 50.0.2; dev httpx 0.28.1.

npm: react / react-dom 19.3.0, react-router-dom 7.18.4 (**⚑ not in §3**: the
spec's page list needs routing), @clerk/react 6.17.5 (supersedes
@clerk/clerk-react), @xyflow/react 12.12.0, d3-scale 4.0.2,
@tanstack/react-table 9.2.4 (v9 API), zustand 5.0.15; dev vite 8.3.2,
typescript 7.0.2, vitest 5.0.3, jsdom 27.4.0 (30.x needs Node ≥ 22.22.2),
@testing-library/react 16.3.3, json-schema-to-typescript 16.0.0,
@playwright/test 1.56.1 (matches the installed browsers).

## Known limits

- The JS bundle is ~1 MB (Clerk + React Flow); code-splitting can come later.
- Breakpoint behaviour follows the mockups; the tablet/read-only layouts
  were not separately tested in the app.
