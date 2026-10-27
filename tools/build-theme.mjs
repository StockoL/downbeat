// Builds Downbeat's LooseLeaf theme bundle: greyscale chrome, one accent.
import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const [,, llRoot, outDir] = process.argv;
const core = await import(pathToFileURL(`${llRoot}/scripts/tokens-core.mjs`));
const json = JSON.parse(readFileSync(`${llRoot}/design-tokens.json`, "utf8"));
json.$palette.neutral = { hue: 270, chroma: 0.18 };
json.$palette.action = { hue: 270, chroma: 0.18 };
json.$palette.accent = { hue: 270, chroma: 0.18 };
const meta = { $version: "2.0.0", $generated: new Date().toISOString() };
const { css, tokens } = core.compile(json);
writeFileSync(`${outDir}/looseleaf-tokens.css`, core.themeStylesheet(css));
writeFileSync(`${outDir}/tokens.resolved.json`, JSON.stringify(core.resolvedTokens(tokens, meta), null, 2) + "\n");
writeFileSync(`${outDir}/design-tokens.json`, JSON.stringify({ ...meta, ...json }, null, 2) + "\n");
const fails = core.contrastReport(tokens).filter(r => !r.passes);
console.log("contrast failures:", fails.map(r => `${r.foreground} on ${r.background} (${r.scheme}) ${r.ratio.toFixed(2)}`));
