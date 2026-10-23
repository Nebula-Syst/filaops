// PrintFlow: pesos de bobinas (la API trabaja en gramos).

export function formatGrams(grams) {
  const n = Number(grams);
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1000) {
    const kg = Math.round(n / 10) / 100;
    return `${kg.toLocaleString("es-ES", { maximumFractionDigits: 2 })} kg`;
  }
  return `${Math.round(n)} g`;
}

// Los colores del catálogo están en inglés ("PLA - Black"): buscar "negro"
// también encuentra "black".
const COLOR_ALIASES = {
  negro: "black",
  blanco: "white",
  rojo: "red",
  azul: "blue",
  verde: "green",
  amarillo: "yellow",
  gris: ["grey", "gray"],
  naranja: "orange",
  rosa: "pink",
  morado: "purple",
  lila: "purple",
  marron: "brown",
  marrón: "brown",
  dorado: "gold",
  oro: "gold",
  plata: "silver",
  plateado: "silver",
  transparente: "clear",
  madera: "wood",
};

/** ¿Encaja el texto con todas las palabras buscadas (en español o inglés)? */
export function matchesSearch(text, query) {
  const haystack = text.toLowerCase();
  return query
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => [word, ...[COLOR_ALIASES[word] || []].flat()].some((w) => haystack.includes(w)));
}
