/**
 * Decimal-safe parsing/formatting for quantities and prices.
 * Avoids locale pitfalls and floating drift in UI calcs.
 */

/**
 * Ambient locale defaults — set once at app init by LocaleContext.
 * Allows non-hook code (module-level functions, production modals) to pick
 * up the company locale without requiring React context.
 *
 * Call setLocaleDefaults(currency, locale) from LocaleContext when settings load.
 */
let _defaultCurrency = "USD";
let _defaultLocale = "en-US";

/** Set module-level defaults. Called by LocaleContext after settings fetch. */
export function setLocaleDefaults(currency, locale) {
  _defaultCurrency = currency || "USD";
  _defaultLocale = locale || "en-US";
}

/** @param {string|number|null|undefined} v */
export function parseDecimal(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = String(v).trim();
  if (!s) return null;
  // support "1,234.56" or "1 234,56" by normalizing
  const normalized = s
    .replace(/[\s,_]/g, "")
    .replace(/(\d)[,](\d{3}\b)/g, "$1$2")
    .replace(/,/, "."); // last comma -> dot for decimals
  const n = Number(normalized);
  return Number.isFinite(n) ? n : null;
}

/** @param {number|null|undefined} n */
export function toFixedSafe(n, digits = 2) {
  if (n === null || n === undefined || !Number.isFinite(n)) return "";
  const factor = Math.pow(10, digits);
  return String(Math.round(n * factor) / factor);
}

/**
 * @param {number|null|undefined} n
 * @param {string} [currency] — defaults to company currency (set by setLocaleDefaults)
 * @param {string} [locale] — defaults to company locale (set by setLocaleDefaults)
 */
export function formatCurrency(n, currency = _defaultCurrency, locale = _defaultLocale) {
  // Nebula (fork): la API manda los importes Decimal como texto ("25.00");
  // sin convertirlos, Number.isFinite("25.00") es false y el total salía vacío.
  const value = typeof n === "string" ? parseDecimal(n) : n;
  if (value === null || value === undefined || !Number.isFinite(value)) return "";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

