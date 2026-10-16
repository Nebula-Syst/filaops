/**
 * Nebula — moneda de la empresa en los importes que FilaOps escribe con "$" fijo.
 *
 * Muchas pantallas del original pintan `${total.toFixed(2)}` en vez de usar
 * formatCurrency, así que con la empresa en EUR salían "$43.50" junto a otras
 * que ya decían "43,50 €". Igual que las traducciones, se corrige en el DOM para
 * no tocar decenas de archivos del upstream: cada importe "$1,234.50" se vuelve a
 * formatear con la moneda y el locale de Ajustes → Empresa.
 *
 * React suele separar `$` y `{valor}` en dos nodos de texto hermanos ("$" y
 * "43.50"); ese caso también se trata. Con la moneda en USD no se cambia nada.
 */
import { API_URL } from "../../config/api";

let settings = null; // { currency, locale }
let loading = false;
let lastTry = 0;
const listeners = new Set();

/** Pide la moneda de la empresa (requiere sesión; reintenta cada 5 s si aún no la hay). */
function ensureSettings() {
  if (settings || loading || Date.now() - lastTry < 5000) return;
  if (import.meta.env?.MODE === "test") return; // los tests fijan la moneda a mano
  loading = true;
  lastTry = Date.now();
  fetch(`${API_URL}/api/v1/settings/company`, { credentials: "include" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (!data) return;
      settings = { currency: data.currency_code || "USD", locale: data.locale || "en-US" };
      listeners.forEach((fn) => fn());
    })
    .catch(() => {})
    .finally(() => {
      loading = false;
    });
}

export function onCurrencyReady(fn) {
  listeners.add(fn);
}

export function _setCurrencyForTests(value) {
  settings = value;
}

function active() {
  if (!settings) {
    ensureSettings();
    return null;
  }
  return settings.currency === "USD" ? null : settings;
}

const formatters = new Map();
function formatter(s, digits) {
  const key = `${s.locale}|${s.currency}|${digits}`;
  if (!formatters.has(key)) {
    formatters.set(
      key,
      new Intl.NumberFormat(s.locale, {
        style: "currency",
        currency: s.currency,
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
    );
  }
  return formatters.get(key);
}

function browserDecimalIsComma() {
  try {
    return (1.5).toLocaleString().includes(",");
  } catch {
    return false;
  }
}

/**
 * "1,234.50" (toFixed/en-US) o "1.234,5" (toLocaleString en un móvil en español)
 * → { value, digits }.
 */
export function parseAmount(raw) {
  const s = raw.replace(/\s/g, "");
  let intPart = s;
  let frac = "";
  const lastDot = s.lastIndexOf(".");
  const lastComma = s.lastIndexOf(",");
  if (lastDot >= 0 && lastComma >= 0) {
    const sep = lastDot > lastComma ? lastDot : lastComma;
    intPart = s.slice(0, sep);
    frac = s.slice(sep + 1);
  } else if (lastComma >= 0 || lastDot >= 0) {
    const sep = Math.max(lastComma, lastDot);
    const sepChar = s[sep];
    const after = s.slice(sep + 1);
    const repeated = s.indexOf(sepChar) !== sep; // "1,234,567": separador de miles
    const comma = browserDecimalIsComma();
    const isGroup =
      repeated ||
      (after.length === 3 && (sepChar === "," ? !comma : comma) && !/^0+$/.test(s.slice(0, sep)));
    if (!isGroup) {
      intPart = s.slice(0, sep);
      frac = after;
    }
  }
  const value = Number(`${intPart.replace(/[.,]/g, "")}.${frac || "0"}`);
  return Number.isFinite(value) ? { value, digits: frac.length } : null;
}

function formatAmount(s, raw, scale, negative) {
  const parsed = parseAmount(raw);
  if (!parsed) return null;
  if (scale) {
    // "$1.2k" del dashboard: se mantiene la forma corta
    const short = formatter(s, parsed.digits).format(parsed.value);
    return (negative ? "-" : "") + short.replace(/(\d)(?!.*\d)/, `$1${scale}`);
  }
  const digits = parsed.digits > 2 ? parsed.digits : parsed.digits === 0 && !raw.includes(".") && !raw.includes(",") ? 0 : 2;
  return (negative ? "-" : "") + formatter(s, digits).format(parsed.value);
}

const AMOUNT = /(-?)\$\s?(\d[\d.,]*\d|\d)(\s?[kKM](?![A-Za-z]))?/g;
const NUMBER_START = /^(\s*)(-?)(\d[\d.,]*\d|\d)(\s?[kKM](?![A-Za-z]))?/;
// Precios de las licencias de FilaOps (en dólares de verdad)
const KEEP = /\/\s*(month|mes|year|año)\b/i;

/** "$" dentro del propio texto: "Total: $43.50" → "Total: 43,50 €". */
export function convertInline(text) {
  if (!text.includes("$") || KEEP.test(text)) return null;
  const s = active();
  if (!s) return null;
  let changed = false;
  const out = text.replace(AMOUNT, (match, neg, raw, scale, offset) => {
    if (text[offset + match.length] === "{") return match;
    const f = formatAmount(s, raw, scale ? scale.trim() : "", !!neg);
    if (f == null) return match;
    changed = true;
    return f;
  });
  return changed ? out : null;
}

const stripped = new WeakSet(); // nodos "$" que se han vaciado porque el número va en el siguiente

/**
 * Nodos hermanos: "$" + "43.50" (o "Total: $" + "43.50"). Devuelve los cambios a
 * aplicar [[nodo, texto], ...] o null.
 */
export function convertSplit(node) {
  const data = node.data;
  const prevNode = node.previousSibling;
  if (!data.includes("$") && !(prevNode && stripped.has(prevNode))) return null;
  const s = active();
  if (!s) return null;

  // Nodo con el "$" al final y el número en el siguiente
  if (/(^|[^\w$])\$\s*$/.test(data) && !KEEP.test(data)) {
    const next = node.nextSibling;
    if (next && next.nodeType === 3) {
      const m = next.data.match(NUMBER_START);
      if (m) {
        const f = formatAmount(s, m[3], m[4] ? m[4].trim() : "", !!m[2]);
        if (f != null) {
          stripped.add(node);
          return [
            [node, data.replace(/\$\s*$/, "")],
            [next, m[1] + f + next.data.slice(m[0].length)],
          ];
        }
      }
    }
    // "$" suelo delante de un campo de importe → símbolo de la moneda
    if (data.trim() === "$" && !next) {
      const symbol = formatter(s, 0)
        .formatToParts(0)
        .find((p) => p.type === "currency")?.value;
      return symbol ? [[node, data.replace("$", symbol)]] : null;
    }
    return null;
  }

  // React ha cambiado el número y el "$" (ya vaciado) está en el nodo anterior
  const prev = node.previousSibling;
  if (prev && prev.nodeType === 3 && stripped.has(prev)) {
    const m = data.match(NUMBER_START);
    if (m && !/[€£¥]|[A-Z]{3}/.test(data)) {
      const f = formatAmount(s, m[3], m[4] ? m[4].trim() : "", !!m[2]);
      if (f != null) return [[node, m[1] + f + data.slice(m[0].length)]];
    }
  }
  return null;
}
