# CLAUDE.md — AHU Sequence Verifier

Read `docs/SPEC.md` before doing anything. It is the source of truth. If this file and the spec disagree, the spec wins; tell the owner about the conflict.

## Current milestone

**M0** — see `docs/SPEC.md` §12. Update this line when the owner confirms a milestone's exit gate has passed. Never start work on a later milestone before then.

## Who you are working for

The owner is an HVAC controls engineer and a novice-to-intermediate Python programmer. He audits the physics, not the plumbing. So:

- Explain every change in plain words: what changed, why, how it was verified.
- Keep functions short and named after the engineering concept (`mix_airstreams`, not `combine`).
- Every physics function gets a docstring with the equation in words and its source (ASHRAE Handbook — Fundamentals, Ch. 1, or the spec section).
- State assumptions out loud. Never guess silently. If the spec is ambiguous, stop and ask.
- Minimum code. Nothing speculative, no features the current ticket does not ask for.
- Surgical changes. Do not refactor code outside the ticket unless asked.

## Hard rules

1. **One engine.** All psychrometric and component physics lives in `engine/` (Python). `web/` never computes a physical property, load or state; it displays what the API returns.
2. **Never hand-write psychrometric property equations.** Use PsychroLib (vendored at `engine/ahuverify/_vendor/psychrolib.py`). SI units internally.
3. **SI inside, I-P at the edges.** Convert I-P input to SI once, at the schema boundary. Convert to I-P for display with I-P equations — never divide SI enthalpy by 2.326 (that factor is valid for differences only).
4. **Mass basis.** Convert every volumetric airflow to dry-air mass flow once (`m = Q / v` at the stated location). Mixing, wheels and loads use mass flow. Never hardcode 1.08, 4.5 or 0.68 in the engine.
5. **Tests first for physics.** For any physics ticket: write the failing test from the spec's fixtures, show it fails, then implement. A ticket is not done until `pytest` passes in full.
6. **No `eval`, no `exec`.** Sequence conditions are structured data (spec §6.3), evaluated by our own code.
7. **Ask before adding a dependency.** List it, say why, and wait for a yes.
8. **Never commit secrets.** Keys live in `.env` (git-ignored); `.env.example` lists names only.
9. **Stop and ask** on anything listed in spec §14 (open questions), any change to the data schema, and any change to a fixture value.

## Commands

```bash
# engine
cd engine && python -m pytest -q
cd engine && python -m ruff check . && python -m ruff format --check .
# api (from M3)
cd api && uvicorn app.main:app --reload
# web (from M3)
cd web && npm run dev
cd web && npm test
```

## Definition of done (every ticket)

- Acceptance criteria in the ticket are all met and demonstrated.
- `pytest` (and `npm test` once `web/` exists) passes.
- Lint passes.
- A short plain-English note to the owner: what changed, how it was verified, any assumption made.
