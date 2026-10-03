// CSS variables, helper rules and the SVG symbol sprite, built from tokens.ts.
// Used by the app (injected at start-up) and by scripts/mockup-assets.mjs.
import * as t from "./tokens.ts";

const px = (n: number) => (n === 0 ? "0" : `${n}px`);

function cssVars(): string[] {
  const v: string[] = [];
  v.push(`--font-ui: ${t.font.family.ui};`, `--font-mono: ${t.font.family.mono};`);
  for (const [k, n] of Object.entries(t.font.size)) v.push(`--text-${k}: ${px(n)};`);
  for (const [k, n] of Object.entries(t.font.weight)) v.push(`--weight-${k}: ${n};`);
  for (const [k, n] of Object.entries(t.font.lineHeight)) v.push(`--lh-${k}: ${n};`);
  for (const [k, n] of Object.entries(t.space)) v.push(`--space-${k}: ${px(n)};`);
  for (const [k, n] of Object.entries(t.radius)) v.push(`--radius-${k}: ${px(n)};`);
  for (const [k, n] of Object.entries(t.border)) v.push(`--border-${k}: ${px(n)};`);
  for (const [k, c] of Object.entries(t.color.neutral)) v.push(`--neutral-${k}: ${c};`);
  v.push(`--accent: ${t.color.accent.base};`, `--accent-strong: ${t.color.accent.strong};`, `--accent-weak: ${t.color.accent.weak};`);
  for (const [k, s] of Object.entries(t.color.status)) {
    v.push(`--${k}: ${s.mark};`, `--${k}-text: ${s.text};`, `--${k}-bg: ${s.bg};`);
  }
  for (const [k, n] of Object.entries(t.layout)) v.push(`--layout-${k}: ${px(n)};`);
  for (const [k, n] of Object.entries(t.chart)) v.push(`--chart-${k}: ${n};`);
  v.push(`--symbol-stroke: ${t.symbolStroke};`);
  return v;
}

export function tokensCss(): string {
  const bp = t.breakpoint;
  return `:root {
${cssVars().map((l) => `  ${l}`).join("\n")}
}
.num, table { font-variant-numeric: tabular-nums lining-nums; font-feature-settings: ${t.font.numeric}; }
.sym { fill: none; stroke: currentColor; stroke-width: var(--symbol-stroke); stroke-linejoin: round; }
.status-icon, .marker { fill: currentColor; stroke: currentColor; stroke-width: 0; }
.glyph { fill: none; stroke: var(--neutral-0); stroke-width: ${t.border.thick}; stroke-linecap: round; }
/* Breakpoints (spec §8.4): hidden below editor width / below tablet width. */
@media (max-width: ${bp.editor - 1}px) { .bp-editor-only { display: none !important; } }
@media (max-width: ${bp.tablet - 1}px) { .bp-tablet-up { display: none !important; } .bp-readonly-note { display: block !important; } }
`;
}

export function symbolDefs(): string {
  return [
    ...Object.entries(t.symbols).map(([k, s]) => `<symbol id="sym-${k}" viewBox="0 0 48 48" class="sym">${s}</symbol>`),
    ...Object.entries(t.statusIcons).map(([k, s]) => `<symbol id="status-${k}" viewBox="0 0 16 16" class="status-icon">${s}</symbol>`),
    ...Object.entries(t.failureMarkers).map(([k, s]) => `<symbol id="marker-${k}" viewBox="0 0 16 16" class="marker">${s}</symbol>`),
  ].join("");
}
