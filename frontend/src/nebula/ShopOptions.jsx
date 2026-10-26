import { useEffect, useMemo, useState } from "react";
import { API_URL } from "../config/api";
import { formatCurrency } from "../lib/number";

/**
 * PrintFlow: tamaños y caja del artículo en las tiendas online.
 *
 * - Tamaños: este artículo agrupa otros (cada uno un tamaño con su SKU, precio
 *   y stock). La tienda muestra una sola ficha con selector de tamaño, con el
 *   nombre, descripción, foto, categoría y tiendas de este artículo.
 * - Caja: un artículo de embalaje cuyo coste se suma al precio en la tienda.
 *   Con tamaños, cada tamaño lleva la suya.
 * - Personalización: qué elige el cliente (un color, colores y una descripción,
 *   o pintarlo en la web). Con tamaños, la del producto vale para todos.
 *
 * Se aplica en la tienda en su siguiente sincronización (cada 5 minutos).
 */
const request = async (path, options = {}) => {
  const res = await fetch(`${API_URL}/api/v1/items/${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Could not save. Try again.");
  return data;
};

const toRows = (sizes) =>
  (sizes || []).map((s) => ({ product_id: String(s.id), size_label: s.size_label || "", box_id: s.box_id ? String(s.box_id) : "" }));

const CUSTOMIZATIONS = [
  ["none", "Nothing: always the same"],
  ["color", "One colour"],
  ["describe", "Colours and a description"],
  ["paint", "Paint it on the web"],
];

function BoxSelect({ boxes, value, onChange, disabled, id }) {
  return (
    <select
      id={id}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white"
    >
      <option value="">No box</option>
      {boxes.map((b) => (
        <option key={b.id} value={String(b.id)}>
          {b.name} · {formatCurrency(b.cost)}
        </option>
      ))}
    </select>
  );
}

export default function ShopOptions({ item }) {
  const [data, setData] = useState(null);
  const [goods, setGoods] = useState([]);
  const [rows, setRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!item?.id) return undefined;
    let cancelled = false;
    request(`${item.id}/shop-options`, { method: "GET" })
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setRows(toRows(d.sizes));
      })
      .catch(() => !cancelled && setData(null));
    const params = new URLSearchParams({ item_type: "finished_good", exclude_variants: "false", limit: "2000", offset: "0" });
    fetch(`${API_URL}/api/v1/items?${params}`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((d) => !cancelled && setGoods((d.items || []).filter((g) => g.id !== item.id && !g.is_template)))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item?.id]);

  const sortedGoods = useMemo(() => [...goods].sort((a, b) => a.name.localeCompare(b.name)), [goods]);

  if (!item?.id || !data) return null;

  const boxes = data.boxes || [];
  const dirty = JSON.stringify(rows) !== JSON.stringify(toRows(data.sizes));
  const incomplete = rows.some((r) => !r.product_id || !r.size_label.trim());

  const run = async (fn) => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await fn();
      setSaved(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const saveOwnBox = (boxId) =>
    run(async () => {
      setData(await request(`${item.id}/shop-box`, { method: "PUT", body: JSON.stringify({ box_id: boxId ? Number(boxId) : null }) }));
    });

  const saveCustomization = (value) =>
    run(async () => {
      setData(await request(`${item.id}/shop-customization`, { method: "PUT", body: JSON.stringify({ customization: value }) }));
    });

  const saveSizes = () =>
    run(async () => {
      let next = await request(`${item.id}/shop-sizes`, {
        method: "PUT",
        body: JSON.stringify({ sizes: rows.map((r) => ({ product_id: Number(r.product_id), size_label: r.size_label.trim() })) }),
      });
      const current = new Map((next.sizes || []).map((s) => [String(s.id), s.box_id ? String(s.box_id) : ""]));
      for (const r of rows) {
        if (current.get(r.product_id) !== r.box_id) {
          await request(`${r.product_id}/shop-box`, { method: "PUT", body: JSON.stringify({ box_id: r.box_id ? Number(r.box_id) : null }) });
          next = null;
        }
      }
      if (!next) next = await request(`${item.id}/shop-options`, { method: "GET" });
      setData(next);
      setRows(toRows(next.sizes));
    });

  const update = (i, field, value) => {
    setSaved(false);
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, [field]: value } : r)));
  };
  const move = (i, step) =>
    setRows((prev) => {
      const next = [...prev];
      [next[i], next[i + step]] = [next[i + step], next[i]];
      return next;
    });

  const status = (
    <>
      {saved && !dirty && <p className="mt-3 text-xs text-emerald-400">Saved. The shop will update in a few minutes.</p>}
      {error && <p className="mt-3 text-xs text-red-400">{error}</p>}
    </>
  );

  // Este artículo es un tamaño de otro: solo su caja
  if (data.group) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
        <h3 className="mb-1 text-sm font-medium text-gray-300">Size in the shop</h3>
        <p className="mb-3 text-xs text-gray-500">
          <span>This item is sold in the shop as a size of:</span>{" "}
          <span className="text-gray-200">{data.group.name}</span> <span className="text-gray-400">({data.size_label})</span>
        </p>
        <label htmlFor={`box-${item.id}`} className="mb-1 block text-xs text-gray-400">
          Box (its cost is added to the shop price)
        </label>
        <BoxSelect id={`box-${item.id}`} boxes={boxes} value={data.box_id ? String(data.box_id) : ""} onChange={saveOwnBox} disabled={saving} />
        {status}
      </div>
    );
  }

  const used = new Set(rows.map((r) => r.product_id));
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
      <h3 className="mb-1 text-sm font-medium text-gray-300">Sizes and box in the shop</h3>
      <p className="mb-3 text-xs text-gray-500">
        Add other items as sizes of this product. The shop shows a single product with a size selector, using the name, description, photo, category and shops of this item.
      </p>

      <div className="mb-4">
        <label htmlFor={`customization-${item.id}`} className="mb-1 block text-xs text-gray-400">
          What the customer chooses
        </label>
        <select
          id={`customization-${item.id}`}
          value={data.customization || "none"}
          disabled={saving}
          onChange={(e) => saveCustomization(e.target.value)}
          className="w-full rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white"
        >
          {CUSTOMIZATIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">The colours offered are the ones with spools in stock.</p>
      </div>

      {rows.length > 0 && (
        <ul className="mb-3 space-y-2">
          {rows.map((r, i) => (
            <li key={i} className="grid grid-cols-1 gap-2 rounded-lg border border-gray-700 p-2 sm:grid-cols-[1fr_8rem_1fr_auto]">
              <select
                aria-label="Item"
                value={r.product_id}
                onChange={(e) => update(i, "product_id", e.target.value)}
                className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white"
              >
                <option value="">Choose item…</option>
                {sortedGoods
                  .filter((g) => String(g.id) === r.product_id || !used.has(String(g.id)))
                  .map((g) => (
                    <option key={g.id} value={String(g.id)}>
                      {g.name} ({g.sku})
                    </option>
                  ))}
              </select>
              <input
                aria-label="Size name"
                value={r.size_label}
                maxLength={100}
                onChange={(e) => update(i, "size_label", e.target.value)}
                placeholder="Size name"
                className="rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white"
              />
              <BoxSelect boxes={boxes} value={r.box_id} onChange={(v) => update(i, "box_id", v)} disabled={saving} />
              <div className="flex items-center gap-1">
                <button type="button" aria-label="Move up" disabled={i === 0} onClick={() => move(i, -1)} className="rounded px-2 py-1 text-gray-400 hover:text-white disabled:opacity-30">
                  ↑
                </button>
                <button type="button" aria-label="Move down" disabled={i === rows.length - 1} onClick={() => move(i, 1)} className="rounded px-2 py-1 text-gray-400 hover:text-white disabled:opacity-30">
                  ↓
                </button>
                <button
                  type="button"
                  aria-label="Remove size"
                  onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
                  className="rounded px-2 py-1 text-red-400 hover:text-red-300"
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, { product_id: "", size_label: "", box_id: "" }])}
          className="rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:text-white"
        >
          Add size
        </button>
        {dirty && (
          <button
            type="button"
            onClick={saveSizes}
            disabled={saving || incomplete}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Save sizes
          </button>
        )}
      </div>

      {rows.length === 0 && (
        <div className="mt-4">
          <label htmlFor={`box-${item.id}`} className="mb-1 block text-xs text-gray-400">
            Box (its cost is added to the shop price)
          </label>
          <BoxSelect id={`box-${item.id}`} boxes={boxes} value={data.box_id ? String(data.box_id) : ""} onChange={saveOwnBox} disabled={saving} />
        </div>
      )}
      {!boxes.length && (
        <p className="mt-3 text-xs text-gray-500">To choose boxes, create them as items of type Packaging with their cost.</p>
      )}
      {status}
    </div>
  );
}
