// Generates the static-mockup assets from web/src/design/tokens.ts.
//   node --experimental-strip-types web/scripts/mockup-assets.mjs          write assets
//   node --experimental-strip-types web/scripts/mockup-assets.mjs --check  verify only
// --check fails if the assets are stale, or if any mockup HTML/CSS contains a
// raw colour or size instead of a token.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as t from "../src/design/tokens.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const mockups = join(root, "mockups");
const header = "Generated from web/src/design/tokens.ts by web/scripts/mockup-assets.mjs. Do not edit.";

function cssVars() {
  const v = [];
  const px = (n) => (n === 0 ? "0" : `${n}px`);
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

function buildCss() {
  const bp = t.breakpoint;
  return `/* ${header} */
:root {
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

function buildSymbolsJs() {
  const defs = [
    ...Object.entries(t.symbols).map(([k, s]) => `<symbol id="sym-${k}" viewBox="0 0 48 48" class="sym">${s}</symbol>`),
    ...Object.entries(t.statusIcons).map(([k, s]) => `<symbol id="status-${k}" viewBox="0 0 16 16" class="status-icon">${s}</symbol>`),
    ...Object.entries(t.failureMarkers).map(([k, s]) => `<symbol id="marker-${k}" viewBox="0 0 16 16" class="marker">${s}</symbol>`),
  ].join("");
  return `// ${header}
document.currentScript.insertAdjacentHTML("afterend", ${JSON.stringify(
    `<svg width="0" height="0" style="position:absolute" aria-hidden="true">${defs}</svg>`,
  )});
`;
}

const outputs = {
  [join(mockups, "assets", "tokens.css")]: buildCss(),
  [join(mockups, "assets", "symbols.js")]: buildSymbolsJs(),
};

// Raw values that must come from tokens instead.
const forbidden = [
  [/#[0-9a-fA-F]{3,8}\b(?![-\w])/g, "hex colour"],
  [/\b(rgb|rgba|hsl|hsla)\(/g, "colour function"],
  [/\b\d*\.?\d+(px|rem|em|pt)\b/g, "raw size"],
  [/\sstyle="/g, "inline style attribute"],
];

function scanMockups() {
  const problems = [];
  const files = readdirSync(mockups).filter((f) => f.endsWith(".html") || f.endsWith(".css"));
  for (const f of files) {
    readFileSync(join(mockups, f), "utf8").split("\n").forEach((line, i) => {
      // Fragment links like href="#sym-coil" are not colours.
      const text = line.replace(/href="#[\w-]+"/g, "");
      for (const [re, what] of forbidden) {
        for (const m of text.matchAll(re)) problems.push(`${f}:${i + 1}: ${what} "${m[0].trim()}"`);
      }
    });
  }
  return problems;
}

if (process.argv.includes("--check")) {
  const problems = scanMockups();
  for (const [path, content] of Object.entries(outputs)) {
    let onDisk = "";
    try { onDisk = readFileSync(path, "utf8"); } catch {}
    if (onDisk !== content) problems.push(`${path}: stale — rerun without --check`);
  }
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  console.log("mockups use tokens only; assets up to date");
} else {
  mkdirSync(join(mockups, "assets"), { recursive: true });
  for (const [path, content] of Object.entries(outputs)) writeFileSync(path, content);
  console.log("wrote", Object.keys(outputs).length, "files");
}
