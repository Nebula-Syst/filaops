import { describe, it, expect, beforeEach } from "vitest";
import { convertInline, convertSplit, parseAmount, _setCurrencyForTests } from "../currency";

const nbsp = (s) => s.replace(/\u00a0|\u202f/g, " ");

function siblings(...texts) {
  const p = document.createElement("span");
  const nodes = texts.map((t) => document.createTextNode(t));
  nodes.forEach((n) => p.appendChild(n));
  return nodes;
}

describe("Nebula: importes con $ fijo → moneda de la empresa", () => {
  beforeEach(() => _setCurrencyForTests({ currency: "EUR", locale: "es-ES" }));

  it("convierte importes dentro del texto", () => {
    expect(nbsp(convertInline("$43.50"))).toBe("43,50 €");
    expect(nbsp(convertInline("Total: $1,234.50"))).toBe("Total: 1234,50 €");
    expect(nbsp(convertInline("Mat: $1.00 · Labor: $2.50"))).toBe("Mat: 1,00 € · Labor: 2,50 €");
    expect(nbsp(convertInline("$12.00/kg"))).toBe("12,00 €/kg");
    expect(nbsp(convertInline("-$5.00"))).toBe("-5,00 €");
    expect(nbsp(convertInline("$0.1250/unit"))).toBe("0,1250 €/unit");
  });

  it("no toca lo que no es un importe ni los precios de licencias en dólares", () => {
    expect(convertInline("Sin dólares")).toBeNull();
    expect(convertInline("${variable}")).toBeNull();
    expect(convertInline("49 $ / mes")).toBeNull();
    expect(convertInline("$49 / month")).toBeNull();
  });

  it("con la empresa en USD no cambia nada", () => {
    _setCurrencyForTests({ currency: "USD", locale: "en-US" });
    expect(convertInline("$43.50")).toBeNull();
  });

  it("interpreta separadores de miles y decimales", () => {
    expect(parseAmount("1,234.50")).toEqual({ value: 1234.5, digits: 2 });
    expect(parseAmount("43.5")).toEqual({ value: 43.5, digits: 1 });
    expect(parseAmount("1,234,567")).toEqual({ value: 1234567, digits: 0 });
    expect(parseAmount("0.125")).toEqual({ value: 0.125, digits: 3 });
    expect(parseAmount("1.234,5")).toEqual({ value: 1234.5, digits: 1 });
  });

  it("trata el $ y el número en nodos hermanos (JSX `${valor}`)", () => {
    const [dollar, num] = siblings("$", "43.50");
    const changes = convertSplit(dollar);
    expect(changes.map(([n, t]) => [n === dollar ? "d" : "n", nbsp(t)])).toEqual([
      ["d", ""],
      ["n", "43,50 €"],
    ]);
    // React cambia el número más tarde: se vuelve a formatear
    dollar.data = "";
    num.data = "99.00";
    expect(nbsp(convertSplit(num)[0][1])).toBe("99,00 €");
  });

  it("'Total: $' + número", () => {
    const [label] = siblings("Total: $", "10.00 (IVA incl.)");
    const changes = convertSplit(label);
    expect(nbsp(changes[0][1])).toBe("Total: ");
    expect(nbsp(changes[1][1])).toBe("10,00 € (IVA incl.)");
  });

  it("un $ solo delante de un campo pasa a ser el símbolo de la moneda", () => {
    const [dollar] = siblings("$");
    expect(convertSplit(dollar)[0][1]).toBe("€");
  });
});
