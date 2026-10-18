import { useEffect, useState } from "react";
import { API_URL } from "../config/api";
import { formatCurrency } from "../lib/number";
import { totalFor } from "./pricing";

/**
 * PrintFlow: precios por cantidad de un artículo.
 *
 * Imprimiendo varias piezas en la misma cama cada una sale más barata, así que
 * se fijan tramos "desde N unidades → precio por unidad". Por debajo del primer
 * tramo se cobra el precio de venta normal. Los pedidos nuevos (y la tienda
 * online) toman el precio del tramo según la cantidad.
 *
 * Con "piezas por cama" el precio va por camas: el pedido se reparte en camas
 * llenas más una con el resto, y los tramos son el precio por pieza según
 * cuántas van en la cama (1 sola sale más cara: la purga se reparte entre menos).
 */
const num = (v) => {
  const n = parseFloat(String(v ?? "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
};

const toRows = (tiers) =>
  tiers.map((t) => ({
    min_quantity: String(t.min_quantity),
    unit_price: String(t.unit_price),
    label: t.label || "",
  }));

export default function PriceTiersEditor({ item }) {
  const [rows, setRows] = useState([]);
  const [saved, setSaved] = useState([]);
  const [perBed, setPerBed] = useState("");
  const [savedPerBed, setSavedPerBed] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/v1/items/${item.id}/price-tiers`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Could not load quantity prices"))))
      .then((data) => {
        if (cancelled) return;
        setRows(toRows(data.tiers || []));
        setSaved(toRows(data.tiers || []));
        setPerBed(data.units_per_bed ? String(data.units_per_bed) : "");
        setSavedPerBed(data.units_per_bed ? String(data.units_per_bed) : "");
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [item.id]);

  const base = num(item.selling_price);
  const bed = parseInt(perBed, 10) > 0 ? parseInt(perBed, 10) : null;
  const perBedInvalid = perBed !== "" && !bed;
  const dirty = JSON.stringify(rows) !== JSON.stringify(saved) || perBed !== savedPerBed;

  const problems = rows.map((r, i) => {
    const q = num(r.min_quantity);
    const p = num(r.unit_price);
    if (q === null || q < 1) return "Quantity must be 1 or more";
    if (p === null || p < 0) return "Enter a price";
    if (rows.some((o, j) => j !== i && num(o.min_quantity) === q)) return "Repeated quantity";
    if (bed && q > bed) return "More pieces than fit in a bed";
    return null;
  });
  const invalid = problems.some(Boolean) || perBedInvalid;

  const update = (i, field, value) => {
    setDone(false);
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, [field]: value } : r)));
  };

  const add = () => {
    setDone(false);
    const last = rows.length ? num(rows[rows.length - 1].min_quantity) || 1 : 1;
    setRows((prev) => [...prev, { min_quantity: String(prev.length ? last * 2 : 4), unit_price: "", label: "" }]);
  };

  const remove = (i) => {
    setDone(false);
    setRows((prev) => prev.filter((_, j) => j !== i));
  };

  const save = async () => {
    if (invalid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/items/${item.id}/price-tiers`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tiers: rows.map((r) => ({
            min_quantity: num(r.min_quantity),
            unit_price: num(r.unit_price),
            label: r.label.trim() || null,
          })),
          units_per_bed: bed,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Could not save quantity prices");
      }
      setRows(toRows(data.tiers));
      setSaved(toRows(data.tiers));
      setPerBed(data.units_per_bed ? String(data.units_per_bed) : "");
      setSavedPerBed(data.units_per_bed ? String(data.units_per_bed) : "");
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const sorted = rows
    .map((r) => ({ q: num(r.min_quantity), p: num(r.unit_price) }))
    .filter((r) => r.q !== null && r.p !== null)
    .sort((a, b) => a.q - b.q);

  // Vista previa por camas: precio por pieza según cuántas van en la cama y
  // algunos pedidos de ejemplo
  const pricing = { units_per_bed: bed, tiers: sorted.map((r) => ({ min_quantity: r.q, unit_price: r.p })) };
  const product = { selling_price: base };
  const fills = bed && bed <= 12 ? Array.from({ length: bed }, (_, i) => i + 1) : bed ? [1, bed] : [];
  const examples = bed ? [...new Set([bed + 1, bed * 2 + Math.max(1, Math.floor(bed / 2)), bed * 5])] : [];

  return (
    <section aria-label="Quantity prices" className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-gray-300">Quantity prices</h3>
          <p className="text-xs text-gray-400">
            The more units per print bed, the cheaper each one. Below the first tier the selling price applies.
          </p>
        </div>
        <button
          type="button"
          onClick={add}
          disabled={loading}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700"
        >
          + Add tier
        </button>
      </div>

      {!loading && (
        <label className="mb-3 flex flex-wrap items-center gap-2 text-sm text-gray-300">
          Pieces per bed
          <input
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            value={perBed}
            placeholder="—"
            onChange={(e) => {
              setDone(false);
              setPerBed(e.target.value);
            }}
            className="w-20 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-white focus:border-blue-500 focus:outline-none"
          />
          <span className="text-xs text-gray-400">
            {bed
              ? "Orders are split into full beds plus one with the rest. Tiers = price per piece by how many go in the bed."
              : "Optional. Fill it in if the price depends on how many pieces share a bed."}
          </span>
        </label>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-gray-400">
          {base !== null
            ? `Same price for any quantity: ${formatCurrency(base)} per unit.`
            : "No quantity prices yet."}
        </p>
      ) : (
        <div className="space-y-2">
          {rows.map((row, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2 sm:grid-cols-[1fr_1fr_1.5fr_auto]">
              <label className="block text-xs text-gray-400">
                {bed ? "Pieces in the bed" : "From (units)"}
                <input
                  type="number"
                  inputMode="numeric"
                  min="1"
                  step="1"
                  value={row.min_quantity}
                  onChange={(e) => update(i, "min_quantity", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                />
              </label>
              <label className="block text-xs text-gray-400">
                Price per unit
                <input
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={row.unit_price}
                  onChange={(e) => update(i, "unit_price", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
                />
              </label>
              <label className="col-span-2 row-start-2 block text-xs text-gray-400 sm:col-span-1 sm:row-start-auto">
                Note (optional)
                <input
                  type="text"
                  maxLength={100}
                  value={row.label}
                  placeholder="4 per bed"
                  onChange={(e) => update(i, "label", e.target.value)}
                  className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                />
              </label>
              <button
                type="button"
                onClick={() => remove(i)}
                aria-label="Remove tier"
                className="mt-5 self-start rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-red-300 hover:bg-red-500/20"
              >
                ×
              </button>
              {problems[i] && <p className="col-span-full text-xs text-red-400">{problems[i]}</p>}
            </div>
          ))}
          {bed && !invalid && base !== null && (
            <div className="mt-2 grid gap-3 text-xs text-gray-400 sm:grid-cols-2">
              <ul className="space-y-0.5">
                {fills.map((k) => (
                  <li key={k}>
                    {`Bed with ${k}: ${formatCurrency(totalFor(product, pricing, k) / k)} each · ${formatCurrency(totalFor(product, pricing, k))}`}
                  </li>
                ))}
              </ul>
              <ul className="space-y-0.5">
                {examples.map((q) => (
                  <li key={q}>{`Order of ${q}: ${formatCurrency(totalFor(product, pricing, q))}`}</li>
                ))}
              </ul>
            </div>
          )}
          {!bed && sorted.length > 0 && !invalid && (
            <ul className="mt-2 space-y-0.5 text-xs text-gray-400">
              {base !== null && sorted[0].q > 1 && (
                <li>{`1 – ${sorted[0].q - 1} units: ${formatCurrency(base)} each`}</li>
              )}
              {sorted.map((r, i) => (
                <li key={r.q}>
                  {i + 1 < sorted.length
                    ? `${r.q} – ${sorted[i + 1].q - 1} units: ${formatCurrency(r.p)} each`
                    : `${r.q} or more units: ${formatCurrency(r.p)} each`}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(dirty || done || error) && (
        <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
          {error && <p role="alert" className="mr-auto text-sm text-red-400">{error}</p>}
          {done && !dirty && <p role="status" className="mr-auto text-sm text-green-400">Quantity prices saved</p>}
          {dirty && (
            <>
              <button
                type="button"
                onClick={() => {
                  setRows(saved);
                  setError(null);
                }}
                disabled={saving}
                className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
              >
                Discard
              </button>
              <button
                type="button"
                onClick={save}
                disabled={invalid || saving}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save prices"}
              </button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
