# 0003 — Design tokens and M0 mockups

Status: proposed (awaiting owner approval at the M0 gate)

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
  pass included). Needs owner confirmation.
- **Breakpoints.** ≥ 1280 px full editor. 1024–1279 px: palette hidden
  (no topology edits), inspector kept (parameter edits). < 1024 px:
  inspector hidden too, read-only notice shown.
- **No dark mode.** The spec doesn't ask for one; adding it later means a
  second set of colour tokens.
- **Mockup numbers** come from PsychroLib (each state row is self-consistent),
  but the process itself (wheel, mixing, coil) is hand-made, not the engine's.
  Every page says so in a banner.

## Gaps found in the schema / spec while drawing

1. `cooling_coil_chw` (and the heating coil) list a face-velocity check in
   §5.4, but neither has a maximum-velocity field. The mockup shows
   "No limit" as a warning. Proposal: add `max_face_velocity` to coils when
   their tickets land (M1-5, M1-6).
2. Annual bin edges are SI (2 K × 1 g/kg, §5.9). In I-P view, show SI bin
   edges (as mocked) or convert to e.g. 4 °F × 7 gr/lb bins?
