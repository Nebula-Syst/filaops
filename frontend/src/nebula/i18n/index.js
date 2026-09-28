/**
 * Nebula i18n — capa de traducción de la interfaz, independiente del código de FilaOps.
 *
 * FilaOps no tiene sistema de traducciones (los textos están en inglés dentro de
 * cada componente). En vez de tocar cientos de archivos del upstream, esta capa
 * observa el DOM y sustituye los textos que aparecen en el diccionario del idioma
 * activo. Así los merges con BLB3DPrinting/filaops no generan conflictos: lo nuevo
 * que llegue se verá en inglés hasta que se añada al diccionario
 * (ver frontend/scripts/nebula-i18n-missing.cjs).
 *
 * - Textos exactos: dictionary.texts["Save"] = "Guardar"
 * - Textos con variables: dictionary.patterns [["Select {0}", "Seleccionar {0}"]]
 * - Para excluir un elemento: class="notranslate" o translate="no".
 */
import es from "./locales/es.json";

const STORAGE_KEY = "nebula.lang";
const DICTIONARIES = { es };

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
];

const TRANSLATED_ATTRS = ["placeholder", "title", "aria-label", "alt"];
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "CODE", "PRE", "svg"]);

export function getLanguage() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && (saved === "en" || DICTIONARIES[saved])) return saved;
  } catch {
    // localStorage no disponible: usar el idioma del navegador
  }
  const nav = (navigator.language || "en").toLowerCase().slice(0, 2);
  return DICTIONARIES[nav] ? nav : "en";
}

export function setLanguage(code) {
  try {
    localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // sin persistencia; se aplica igualmente en esta carga
  }
  // Recargar es lo más fiable: React vuelve a pintar los textos originales
  // y la capa traduce desde cero con el diccionario nuevo.
  window.location.reload();
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function compile(dictionary) {
  const texts = new Map(Object.entries(dictionary.texts || {}));
  const patterns = (dictionary.patterns || []).map(([src, out]) => {
    const parts = src.split(/\{\d+\}/);
    const order = [...src.matchAll(/\{(\d+)\}/g)].map((m) => Number(m[1]));
    const regex = new RegExp("^" + parts.map(escapeRegExp).join("([\\s\\S]+?)") + "$");
    const literalLength = parts.join("").trim().length;
    return { prefix: parts[0], suffix: parts[parts.length - 1], regex, order, out, literalLength };
  });
  return { texts, patterns };
}

const looksLikeEnglishSentence = (v) =>
  /(\S+\s+){5}/.test(v) || /\s(to|the|and|of|for|with|your|is|are|from|on|in)\s/i.test(` ${v} `);

export function createTranslator(dictionary) {
  const { texts, patterns } = compile(dictionary);
  const cache = new Map();

  const translateCore = (core) => {
    const exact = texts.get(core);
    if (exact !== undefined) return exact;
    for (const p of patterns) {
      if (!core.startsWith(p.prefix) || !core.endsWith(p.suffix)) continue;
      const m = core.match(p.regex);
      if (!m) continue;
      // Un patrón corto ("Add {0}") no debe tragarse una frase entera que aún no
      // está en el diccionario: mejor dejarla en inglés que traducirla a medias.
      if (p.literalLength < 15 && m.slice(1).some(looksLikeEnglishSentence)) continue;
      const values = {};
      p.order.forEach((idx, i) => {
        const v = m[i + 1];
        values[idx] = texts.get(v) ?? v;
      });
      return p.out.replace(/\{(\d+)\}/g, (_, idx) => values[idx] ?? "");
    }
    return null;
  };

  return (value) => {
    if (!value || !/[A-Za-z]/.test(value)) return null;
    if (cache.has(value)) return cache.get(value);
    const [, lead, body, trail] = value.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const core = body.replace(/\s+/g, " ");
    const t = translateCore(core);
    const result = t == null || t === core ? null : lead + t + trail;
    if (cache.size > 20000) cache.clear();
    cache.set(value, result);
    return result;
  };
}

function isSkipped(el) {
  for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
    if (SKIP_TAGS.has(n.tagName)) return true;
    if (n.isContentEditable) return true;
    if (n.getAttribute("translate") === "no" || n.classList.contains("notranslate")) return true;
  }
  return false;
}

function start(lang) {
  const translate = createTranslator(DICTIONARIES[lang]);
  // Guarda lo último que escribimos en cada nodo para no retraducirlo en bucle
  const written = new WeakMap();

  const translateText = (node) => {
    const current = node.data;
    if (written.get(node) === current) return;
    if (!node.parentElement || isSkipped(node.parentElement)) return;
    const out = translate(current);
    if (out != null) {
      written.set(node, out);
      node.data = out;
    }
  };

  const translateAttrs = (el) => {
    if (isSkipped(el)) return;
    let marks = written.get(el);
    for (const attr of TRANSLATED_ATTRS) {
      const current = el.getAttribute(attr);
      if (current == null || marks?.[attr] === current) continue;
      const out = translate(current);
      if (out != null) {
        marks = marks || {};
        marks[attr] = out;
        written.set(el, marks);
        el.setAttribute(attr, out);
      }
    }
    if (el.tagName === "INPUT" && (el.type === "button" || el.type === "submit")) {
      const out = translate(el.value);
      if (out != null) el.value = out;
    }
  };

  const walk = (root) => {
    if (root.nodeType === 3) return translateText(root);
    if (root.nodeType !== 1 || SKIP_TAGS.has(root.tagName)) return;
    translateAttrs(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (n.nodeType === 3) translateText(n);
      else translateAttrs(n);
    }
  };

  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "characterData") translateText(m.target);
      else if (m.type === "attributes") translateAttrs(m.target);
      else m.addedNodes.forEach(walk);
    }
  });

  walk(document.documentElement);
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: TRANSLATED_ATTRS,
  });

  // Diálogos nativos (confirm/alert/prompt) que no pasan por el DOM
  for (const fn of ["alert", "confirm", "prompt"]) {
    const original = window[fn].bind(window);
    window[fn] = (message, ...rest) =>
      original(typeof message === "string" ? translate(message) ?? message : message, ...rest);
  }
}

const lang = getLanguage();
document.documentElement.lang = lang;
if (DICTIONARIES[lang]) start(lang);
