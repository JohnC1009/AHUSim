// Generates the static-mockup assets from web/src/design/tokens.ts.
//   node --experimental-strip-types web/scripts/mockup-assets.mjs          write assets
//   node --experimental-strip-types web/scripts/mockup-assets.mjs --check  verify only
// --check fails if the assets are stale, or if any mockup HTML/CSS contains a
// raw colour or size instead of a token.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { symbolDefs, tokensCss } from "../src/design/css.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const mockups = join(root, "mockups");
const header = "Generated from web/src/design/tokens.ts by web/scripts/mockup-assets.mjs. Do not edit.";

function buildCss() {
  return `/* ${header} */
${tokensCss()}`;
}

function buildSymbolsJs() {
  return `// ${header}
document.currentScript.insertAdjacentHTML("afterend", ${JSON.stringify(
    `<svg width="0" height="0" style="position:absolute" aria-hidden="true">${symbolDefs()}</svg>`,
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
  const files = [
    ...readdirSync(mockups).filter((f) => f.endsWith(".html") || f.endsWith(".css")).map((f) => join(mockups, f)),
    ...readdirSync(join(root, "src")).filter((f) => f.endsWith(".css")).map((f) => join(root, "src", f)),
  ];
  for (const f of files) {
    readFileSync(f, "utf8").split("\n").forEach((line, i) => {
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
