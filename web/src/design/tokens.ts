// Design tokens — the only source of colours, sizes and symbols for web/ (spec §8.4).
// Every component uses these; no ad-hoc values. Sizes are px numbers.
// Mockup CSS is generated from this file: node --experimental-strip-types web/scripts/mockup-assets.mjs

export const font = {
  family: {
    ui: '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
    mono: '"JetBrains Mono", "Cascadia Mono", Consolas, monospace',
  },
  // Type scale (px). Body is md.
  size: { xs: 11, sm: 12, md: 14, lg: 16, xl: 20, xxl: 24 },
  weight: { regular: 400, medium: 500, semibold: 600 },
  lineHeight: { tight: 1.25, normal: 1.5 },
  // Tabular numerals: required in every table and numeric readout.
  numeric: '"tnum" 1, "lnum" 1',
} as const;

// Spacing scale: multiples of 4 only.
export const space = { 0: 0, 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48 } as const;

export const radius = { sm: 2, md: 4, lg: 8, pill: 999 } as const;

export const border = { hairline: 1, thick: 2 } as const;

export const color = {
  // Warm grey neutrals. Text: 900 primary, 700 secondary, 600 muted (all ≥ 4.5:1 on surface).
  // 500 and lighter are for borders, grid lines and disabled states only, never text.
  neutral: {
    0: '#ffffff',
    25: '#fcfcfb', // page surface
    50: '#f7f6f4', // panel surface
    100: '#f0efec', // inset / table header
    200: '#e2e1dc', // dividers
    300: '#cbcac4', // input borders, chart grid
    400: '#a9a8a1',
    500: '#85847d',
    600: '#64635d',
    700: '#52514e',
    800: '#33332f',
    900: '#0b0b0b',
  },
  // The one accent: selection, focus, process path, primary action.
  accent: {
    base: '#2a78d6', // marks, focus ring (not text: 4.3:1)
    strong: '#1c5cab', // text, primary button background
    weak: '#cde2fb', // selection / hover background
  },
  // Status: always paired with a status icon (shape) and a word. Never colour alone.
  status: {
    pass: { mark: '#0ca30c', text: '#006300', bg: '#e3f4e3' },
    warning: { mark: '#fab219', text: '#7a5200', bg: '#fdf2d6' },
    fail: { mark: '#d03b3b', text: '#a52a2a', bg: '#fbe4e4' },
  },
} as const;

// Fixed layout dimensions (px, multiples of 4).
export const layout = {
  topBar: 48,
  sidePanel: 240,
  inspector: 320,
  dock: 400,
  failureRow: 32,
  control: 32, // height of inputs and buttons
  icon: 16,
  symbol: 48, // schematic symbol box
  marker: 8, // chart marker
} as const;

// Editor ≥ 1280 px; tablet 1024–1279 edits parameters + views results; < 1024 read-only.
export const breakpoint = { tablet: 1024, editor: 1280 } as const;

export const chart = {
  gridStroke: 1,
  saturationStroke: 2,
  processStroke: 2,
} as const;

// Symbols: SVG inner markup on a 48 × 48 box, drawn with currentColor so they
// take the colour of their context. Stroke width comes from `symbolStroke`.
export const symbolStroke = 2;

export const symbols = {
  coil: '<rect x="8" y="4" width="32" height="40"/><path d="M8 44 L40 4"/>',
  damper:
    '<rect x="8" y="4" width="32" height="40"/><path d="M14 14 L34 8 M14 27 L34 21 M14 40 L34 34"/>',
  fan: '<circle cx="24" cy="24" r="18"/><path d="M14 33 L24 9 L34 33 Z"/>',
  wheel: '<circle cx="24" cy="24" r="18"/><circle cx="24" cy="24" r="3"/><path d="M24 6 V42 M6 24 H42"/>',
  humidifier:
    '<rect x="8" y="4" width="32" height="40"/><path d="M18 10 V38 M30 10 V38" stroke-dasharray="3 4"/>',
  filter: '<rect x="8" y="4" width="32" height="40"/><path d="M8 4 L24 14 L8 24 L24 34 L8 44"/>',
  sensor: '<circle cx="24" cy="18" r="12"/><path d="M24 30 V44"/>',
} as const;

// Status icons on a 16 × 16 box, filled with the status mark colour.
// Shape alone distinguishes them: circle = pass, triangle = warning, octagon = fail.
export const statusIcons = {
  pass: '<circle cx="8" cy="8" r="7"/><path d="M4.5 8.2 L7 10.5 L11.5 5.5" class="glyph"/>',
  warning:
    '<path d="M8 1 L15 14.5 H1 Z"/><path d="M8 5.5 V9.5 M8 11.5 V12.5" class="glyph"/>',
  fail: '<path d="M5 1 H11 L15 5 V11 L11 15 H5 L1 11 V5 Z"/><path d="M5.5 5.5 L10.5 10.5 M10.5 5.5 L5.5 10.5" class="glyph"/>',
} as const;

// Sweep-overlay markers, one distinct shape per outcome (16 × 16 box).
// All failures use status.fail colour; the shape carries the kind (see note in
// docs/decisions/0003-design-tokens.md).
export const failureMarkers = {
  pass: '<circle cx="8" cy="8" r="5"/>',
  setpoint_not_met: '<rect x="3" y="3" width="10" height="10"/>',
  limit_exceeded: '<path d="M8 2 L14 13 H2 Z"/>',
  fighting: '<path d="M8 1.5 L14.5 8 L8 14.5 L1.5 8 Z"/>',
  non_monotonic: '<path d="M2 3 H14 L8 14 Z"/>',
  non_converged: '<circle cx="8" cy="8" r="5" fill="none" stroke-width="2.5"/>',
  engine_residual: '<path d="M8 1.5 L13.6 4.75 V11.25 L8 14.5 L2.4 11.25 V4.75 Z"/>',
  cannot_compute: '<rect x="2" y="6" width="12" height="4"/>',
  config_error: '<path d="M3 3 L13 13 M13 3 L3 13" stroke-width="3"/>',
  mode_gap: '<rect x="3.5" y="3.5" width="9" height="9" fill="none" stroke-width="2.5"/>',
  mode_overlap: '<path d="M8 2 V14 M2 8 H14" stroke-width="3"/>',
} as const;
