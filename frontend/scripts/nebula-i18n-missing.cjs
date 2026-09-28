#!/usr/bin/env node
/**
 * Lista los textos de la interfaz que aún no están en el diccionario de Nebula i18n.
 * Úsalo después de traer cambios de upstream (scripts/sync-upstream.sh):
 *
 *   node frontend/scripts/nebula-i18n-missing.cjs          # lista + resumen
 *   node frontend/scripts/nebula-i18n-missing.cjs --json   # JSON {texto: [archivos]}
 *
 * Añade las traducciones a frontend/src/nebula/i18n/locales/es.json
 * ("texts" para textos exactos, "patterns" para textos con variables {0}).
 */
const fs = require("fs"), path = require("path");
const ts = require("typescript");
const root = path.join(__dirname, "..", "src");
const files = [];
(function walk(d){ for (const f of fs.readdirSync(d)) { const p = path.join(d,f);
  if (fs.statSync(p).isDirectory()) { if (!/__tests__|test|stories|nebula/.test(f)) walk(p); }
  else if (/\.(jsx?|tsx?)$/.test(f) && !/\.(test|spec|stories)\./.test(f)) files.push(p); } })(root);
const texts = new Map(), templates = new Map();
const norm = s => s.replace(/\s+/g, " ").trim();
const looksHuman = s => {
  if (!/[A-Za-z]{2}/.test(s)) return false;
  if (/^(https?:|\/|\.|#|@)/.test(s)) return false;
  if (/^[a-z0-9_\-.:\/]+$/.test(s)) return false;           // identifiers, keys, paths
  if (/^[A-Z0-9_]+$/.test(s) && s.length > 4 && s.includes("_")) return false; // CONSTANTS
  if (/^[a-z][a-zA-Z0-9]*$/.test(s)) return false;          // camelCase
  if (/(^|\s)(bg|text|px|py|mt|mb|flex|rounded|border|w|h|p|m|gap|grid|hover:|focus:)[-:]/.test(s)) return false; // tailwind
  if (/[{};=<>]/.test(s) && !/\s/.test(s)) return false;
  if (/^[\w-]+\/[\w.+-]+$/.test(s)) return false;           // mime
  if (/^\d/.test(s) && !/[a-z]{3}/i.test(s)) return false;
  return /^[A-Z¡¿"'(]/.test(s) || /\s/.test(s);
};
const add = (m, s, f) => { if (!m.has(s)) m.set(s, new Set()); m.get(s).add(path.relative(root, f)); };
for (const f of files) {
  const src = ts.createSourceFile(f, fs.readFileSync(f, "utf8"), ts.ScriptTarget.Latest, true, f.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const visit = n => {
    if (ts.isImportDeclaration(n) || ts.isExportDeclaration(n)) return;
    if (ts.isCallExpression(n) && /^(console\.|require|import|fetch|new URL|localStorage|sessionStorage|document\.|querySelector)/.test(n.expression.getText(src))) return;
    if (ts.isJsxAttribute(n) && /^(data-.*|aria-(controls|describedby|labelledby)|className|href|to|src|type|name|id|key|role|htmlFor|autoComplete|method|target|rel|d|fill|stroke|viewBox|path|inputMode|pattern|accept|style|variant|size|color|icon|testid|x|y|cx|cy|r|width|height|strokeWidth|strokeLinecap|strokeLinejoin|transform|mode|state|tone|status|align|as|form|enterKeyHint|capture)$/.test(n.name.getText(src))) return;
    if (ts.isPropertyAssignment(n) && /^["']?(className|href|to|path|key|value|id|type|icon|color|variant|endpoint|url|method|field|accessor|sortKey|name|status|queryKey|route|badgeColor|bg|text)["']?$/.test(n.name.getText(src)) && ts.isStringLiteral(n.initializer)) return;
    if (ts.isJsxText(n)) { const s = norm(n.text); if (s && /[A-Za-z]/.test(s)) add(texts, s, f); }
    else if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) { const s = norm(n.text); if (looksHuman(s)) add(texts, s, f); }
    else if (ts.isTemplateExpression(n)) {
      let s = n.head.text; n.templateSpans.forEach((sp,i) => { s += "{" + i + "}" + sp.literal.text; });
      s = norm(s); if (/[A-Za-z]{3}.*\s|\s.*[A-Za-z]{3}/.test(s.replace(/\{\d+\}/g,"")) && !/(bg|text|px|py|border|rounded|flex)-/.test(s) && !/^\/|\/api|https?:|\?|=/.test(s)) add(templates, s, f);
    }
    ts.forEachChild(n, visit);
  };
  visit(src);
}
const decode = (s) => s.replace(/&apos;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&nbsp;/g, " ").replace(/&mdash;/g, "—").replace(/&rarr;/g, "→").replace(/&larr;/g, "←").replace(/&times;/g, "×").trim();
const dict = JSON.parse(fs.readFileSync(path.join(root, "nebula/i18n/locales/es.json"), "utf8"));
const known = new Set([...Object.keys(dict.texts), ...dict.patterns.map((p) => p[0]), ...(dict.ignored || [])]);
const missing = {};
for (const m of [texts, templates]) for (const [k, v] of m) { const s = decode(k); if (!known.has(s)) missing[s] = [...v].slice(0, 3); }
if (process.argv.includes("--json")) console.log(JSON.stringify(missing, null, 1));
else { for (const [s, f] of Object.entries(missing)) console.log(`${s}    [${f.join(", ")}]`); console.log(`\n${Object.keys(missing).length} textos sin traducir (de ${texts.size + templates.size}).`); }
