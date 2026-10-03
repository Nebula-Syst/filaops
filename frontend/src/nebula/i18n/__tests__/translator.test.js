import { describe, it, expect } from "vitest";
import { createTranslator } from "../index";
import es from "../locales/es.json";

const t = createTranslator({
  texts: { Save: "Guardar", Printer: "Impresora", "Add Item": "Añadir artículo" },
  patterns: [
    ["Select {0}", "Seleccionar {0}"],
    ["Add {0}", "Añadir {0}"],
    ["Showing {0} - {1} of {2} items", "Mostrando {0} - {1} de {2} artículos"],
  ],
});

describe("Nebula i18n translator", () => {
  it("traduce textos exactos conservando los espacios de alrededor", () => {
    expect(t("Save")).toBe("Guardar");
    expect(t("  Save ")).toBe("  Guardar ");
    expect(t("Add   Item")).toBe("Añadir artículo");
  });

  it("devuelve null si no hay traducción o no hay letras", () => {
    expect(t("Unknown thing")).toBeNull();
    expect(t("42.50")).toBeNull();
    expect(t("")).toBeNull();
  });

  it("aplica patrones con variables y traduce la variable si está en el diccionario", () => {
    expect(t("Showing 1 - 25 of 300 items")).toBe("Mostrando 1 - 25 de 300 artículos");
    expect(t("Select Printer")).toBe("Seleccionar Impresora");
    expect(t("Select PLA-BLK-01")).toBe("Seleccionar PLA-BLK-01");
  });

  it("no traduce a medias una frase entera con un patrón corto", () => {
    expect(t("Add your first product, material, or component to get started.")).toBeNull();
    expect(t("Add ?sslmode=require to DATABASE_URL")).toBeNull();
  });

  it("el diccionario español es coherente", () => {
    for (const [src, out] of es.patterns) {
      const srcVars = new Set(src.match(/\{\d+\}/g));
      for (const v of out.match(/\{\d+\}/g) || []) expect(srcVars.has(v)).toBe(true);
    }
    expect(Object.keys(es.texts).length).toBeGreaterThan(3000);
  });
});

describe("Marca PrintFlow", () => {
  const brand = { name: "PrintFlow", pattern: /\bFilaOps\b(?!\s+(?:PRO|Pro|Core|Enterprise)\b)/g };
  const en = createTranslator({ texts: {}, patterns: [] }, { brand });
  const esT = createTranslator(
    { texts: { "Welcome to FilaOps!": "¡Bienvenido a FilaOps!" }, patterns: [["Access {0}", "Acceder a {0}"]] },
    { brand },
  );

  it("cambia FilaOps por PrintFlow en inglés y después de traducir", () => {
    expect(en("Sign in to access FilaOps ERP")).toBe("Sign in to access PrintFlow ERP");
    expect(esT("Welcome to FilaOps!")).toBe("¡Bienvenido a PrintFlow!");
    expect(esT("Access FilaOps")).toBe("Acceder a PrintFlow");
  });

  it("respeta las licencias/ediciones del original", () => {
    expect(en("Upgrade to FilaOps PRO for more.")).toBeNull();
    expect(en("FilaOps Core")).toBeNull();
    expect(en("FilaOps Enterprise integrates with Bambu Cloud")).toBeNull();
  });

  it("no toca textos sin la marca ni dominios en minúsculas", () => {
    expect(en("Save")).toBeNull();
    expect(en("e.g., filaops.local or mycompany.com")).toBeNull();
  });
});

describe("Paso Factura / pago (diccionario real)", () => {
  const t = createTranslator(es);
  it("estados de factura en el paso", () => {
    expect(t("INV-2026-001 · partially paid")).toBe("INV-2026-001 · pagada en parte");
    expect(t("INV-2026-001 · draft")).toBe("INV-2026-001 · borrador");
    expect(t("INV-2026-001 · sent")).toBe("INV-2026-001 · enviada");
  });
  it("botones del paso", () => {
    expect(t("Download Invoice")).toBe("Descargar factura");
    expect(t("Open Invoice")).toBe("Abrir factura");
  });
});

describe("Órdenes de trabajo en el paso 3", () => {
  const t = createTranslator(es);
  it("singular y plural", () => {
    expect(t("1 work order")).toBe("1 orden de trabajo");
    expect(t("3 work orders")).toBe("3 órdenes de trabajo");
  });
});
