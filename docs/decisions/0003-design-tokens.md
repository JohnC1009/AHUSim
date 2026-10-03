# 0003 — Design tokens and M0 mockups

Status: proposed (awaiting owner approval at the M0 gate). Sweep shapes,
face-velocity limit and bin units decided by owner 2026-10-03 (below).

## What exists

- `web/src/design/tokens.ts` — the only source of colours, sizes, symbols.
- `web/mockups/*.html` — Unit, Sequence, Results, Export, static HTML.
- `web/scripts/mockup-assets.mjs` — turns `tokens.ts` into
  `web/mockups/assets/tokens.css` (CSS variables + breakpoint rules) and
  `symbols.js` (SVG symbol sprite). `--check` fails if the assets are stale
  or if any mockup HTML/CSS contains a hex colour, rgb()/hsl(), a px/rem/em/pt
  size or an inline style. Runs on Node 22's built-in TypeScript stripping:
  no new dependency.

## Choices

- **Colours.** Warm-grey neutrals; one accent (blue); status pass / warning /
  fail. Each status has a mark colour, a text colour and a background. Text
  colours were checked for ≥ 4.5:1 contrast on their backgrounds. Hues are
  taken from a palette already validated for colour-blind separation.
- **Status = colour + shape + word.** Circle-check = pass, triangle = warning,
  octagon = fail, always with a label.
- **Sweep overlay.** Spec §8.3 says "coloured by failure kind, with a distinct
  marker shape per kind", but §8.4 allows one accent and three status
  colours. Ten failure kinds would need ten more colours. Choice made: every
  failure uses the fail colour; the **shape** carries the kind (11 shapes,
  pass included). **Approved by owner 2026-10-03.**
- **Breakpoints.** ≥ 1280 px full editor. 1024–1279 px: palette hidden
  (no topology edits), inspector kept (parameter edits). < 1024 px:
  inspector hidden too, read-only notice shown.
- **No dark mode.** The spec doesn't ask for one; adding it later means a
  second set of colour tokens.
- **Mockup numbers** come from PsychroLib (each state row is self-consistent),
  but the process itself (wheel, mixing, coil) is hand-made, not the engine's.
  Every page says so in a banner.

## Gaps found in the schema / spec while drawing

1. **Coil face-velocity limit — decided: add `max_face_velocity`.**
   Added to `cooling_coil_chw` now (optional, a velocity in fpm or m/s).
   When absent, the face-velocity check is skipped and a static-check warning
   says so. The heating coil gets the same field when its model lands (M1-5);
   see the draft in 0002.
2. **Annual bins — decided: SI bins, switchable to I-P.** Bin edges are
   always the SI grid of §5.9 (2 K × 1 g/kg), so totals never change with the
   unit system. The page-wide I-P/SI toggle only relabels the edges:
   2 K = 3.6 °F and 1 g/kg = 7 gr/lb, so −10…−8 °C reads 14.0…17.6 °F.
   The API returns the edges in both systems; `web/` only picks one
   (hard rule 1).
