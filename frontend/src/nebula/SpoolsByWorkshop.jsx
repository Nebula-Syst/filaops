import { useCallback, useEffect, useMemo, useState } from "react";
import { API_URL } from "../config/api";
import { formatGrams, matchesSearch } from "./spools";

/**
 * PrintFlow: bobinas por taller, agrupadas por marca y filamento.
 *
 *   Elegoo · PLA Negro    2 bobinas   100 g · 900 g    1 kg
 *
 * Desde aquí se dan de alta varias bobinas iguales de golpe y se corrige lo que
 * le queda a cada una (o se marca como gastada) pinchando en su peso.
 */
const PRESETS = [1000, 750, 500, 250];

async function send(path, method, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Could not save");
  return data;
}

function AddSpoolsModal({ materials, brands, locations, onClose, onSaved }) {
  const [form, setForm] = useState({
    brand: "",
    search: "",
    product_id: "",
    initial_g: "1000",
    current_g: "",
    quantity: "1",
    location_id: locations.length === 1 ? String(locations[0].id) : "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const matches = useMemo(() => {
    const list = form.search.trim()
      ? materials.filter((m) => matchesSearch(`${m.name} ${m.sku} ${m.color || ""} ${m.material || ""}`, form.search))
      : materials;
    return list.slice(0, 200);
  }, [materials, form.search]);

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await send("/api/v1/spools/nebula/bulk", "POST", {
        product_id: Number(form.product_id),
        brand: form.brand || null,
        location_id: form.location_id ? Number(form.location_id) : null,
        initial_g: Number(form.initial_g),
        current_g: form.current_g === "" ? null : Number(form.current_g),
        quantity: Number(form.quantity) || 1,
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const input = "w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-label="Add spools">
      <form onSubmit={submit} className="w-full max-w-lg space-y-4 rounded-xl border border-gray-700 bg-gray-900 p-6">
        <h2 className="text-lg font-semibold text-white">Add spools</h2>

        <label className="block text-sm text-gray-300">
          Brand
          <input
            className={input}
            list="nebula-spool-brands"
            value={form.brand}
            onChange={(e) => setForm({ ...form, brand: e.target.value })}
            placeholder="Elegoo, Bambu Lab…"
          />
          <datalist id="nebula-spool-brands">
            {brands.map((b) => (
              <option key={b} value={b} />
            ))}
          </datalist>
        </label>

        <div className="space-y-2">
          <label className="block text-sm text-gray-300">
            Filament
            <input
              className={input}
              value={form.search}
              onChange={(e) => setForm({ ...form, search: e.target.value })}
              placeholder="Search: black, PLA, PETG…"
            />
          </label>
          <select
            aria-label="Filament"
            required
            size={6}
            className={input}
            value={form.product_id}
            onChange={(e) => setForm({ ...form, product_id: e.target.value })}
          >
            {matches.map((m) => (
              <option key={m.product_id} value={m.product_id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm text-gray-300">
            Spool weight (g)
            <input
              className={input}
              type="number"
              min="1"
              required
              value={form.initial_g}
              onChange={(e) => setForm({ ...form, initial_g: e.target.value })}
            />
          </label>
          <label className="block text-sm text-gray-300">
            Remaining (g)
            <input
              className={input}
              type="number"
              min="0"
              value={form.current_g}
              onChange={(e) => setForm({ ...form, current_g: e.target.value })}
              placeholder="Full spool"
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => setForm({ ...form, initial_g: String(g) })}
              className={`rounded-full border px-3 py-1 text-xs ${
                Number(form.initial_g) === g ? "border-blue-500 text-white" : "border-gray-700 text-gray-400"
              }`}
            >
              {formatGrams(g)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block text-sm text-gray-300">
            How many
            <input
              className={input}
              type="number"
              min="1"
              max="50"
              value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: e.target.value })}
            />
          </label>
          <label className="block text-sm text-gray-300">
            Workshop
            <select
              className={input}
              value={form.location_id}
              onChange={(e) => setForm({ ...form, location_id: e.target.value })}
            >
              <option value="">No workshop</option>
              {locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-gray-300 hover:text-white">
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving || !form.product_id}
            className="rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Add"}
          </button>
        </div>
      </form>
    </div>
  );
}

function SpoolChip({ spool, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [grams, setGrams] = useState(String(spool.current_g));
  const [error, setError] = useState(null);

  const save = async (patch) => {
    setError(null);
    try {
      await send(`/api/v1/spools/${spool.id}`, "PATCH", patch);
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        title={`${spool.spool_number} · ${formatGrams(spool.initial_g)}`}
        className="rounded-full border border-gray-700 bg-gray-800 px-2.5 py-0.5 text-xs text-gray-200 hover:border-blue-500"
      >
        {formatGrams(spool.current_g)}
      </button>
    );
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1 rounded-lg border border-blue-500 bg-gray-800 px-2 py-1 text-xs">
      <input
        aria-label={`Remaining grams ${spool.spool_number}`}
        type="number"
        min="0"
        value={grams}
        onChange={(e) => setGrams(e.target.value)}
        className="w-20 rounded bg-gray-900 px-1 py-0.5 text-white"
      />
      <span className="text-gray-400">g</span>
      <button type="button" className="text-blue-400" onClick={() => save({ current_weight_g: Number(grams), reason: "Pesada" })}>
        Save
      </button>
      <button type="button" className="text-red-400" onClick={() => save({ current_weight_g: 0, reason: "Gastada", status: "empty" })}>
        Used up
      </button>
      <button type="button" className="text-gray-400" onClick={() => setEditing(false)}>
        Cancel
      </button>
      {error && <span className="w-full text-red-400">{error}</span>}
    </span>
  );
}

export default function SpoolsByWorkshop({ locations = [], onChanged }) {
  const [data, setData] = useState(null);
  const [materials, setMaterials] = useState([]);
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    fetch(`${API_URL}/api/v1/spools/nebula/summary`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => json && setData(json))
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openAdd = () => {
    setAdding(true);
    if (!materials.length) {
      fetch(`${API_URL}/api/v1/spools/nebula/materials`, { credentials: "include" })
        .then((res) => (res.ok ? res.json() : []))
        .then((json) => setMaterials(Array.isArray(json) ? json : []))
        .catch(() => {});
    }
  };

  const changed = () => {
    load();
    onChanged?.();
  };

  const q = search.trim();
  const groups = (data?.locations || [])
    .map((loc) => ({
      ...loc,
      items: q
        ? loc.items.filter((i) => matchesSearch(`${i.brand || ""} ${i.name} ${i.color || ""} ${i.material || ""}`, q))
        : loc.items,
    }))
    .filter((loc) => loc.items.length);

  return (
    <section className="space-y-4" aria-label="Spools by workshop">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-white">Spools by workshop</h2>
        <div className="flex gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search brand or colour…"
            className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-white"
          />
          <button type="button" onClick={openAdd} className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
            Add spools
          </button>
        </div>
      </div>

      {data && !data.locations.length && (
        <p className="text-sm text-gray-400">No spools yet. Use “Add spools” to register the ones you have.</p>
      )}

      {groups.map((loc) => (
        <div key={loc.location_id ?? "none"} className="overflow-hidden rounded-xl border border-gray-700 bg-gray-800/50">
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-gray-700 px-4 py-3">
            <h3 className="font-medium text-white">{loc.location_name || "No workshop"}</h3>
            <span className="text-sm text-gray-400">
              <span>{`${loc.count} spools`}</span> · {formatGrams(loc.total_g)}
            </span>
          </div>
          <ul className="divide-y divide-gray-700/60">
            {loc.items.map((item) => (
              <li key={`${item.brand}-${item.product_id}`} className="flex flex-wrap items-center gap-3 px-4 py-2">
                <span
                  className="h-4 w-4 shrink-0 rounded-full border border-black/30"
                  style={{ background: item.color_hex || "transparent" }}
                />
                <div className="min-w-[12rem] flex-1">
                  <div className="text-sm text-white">
                    {item.brand ? <span className="font-medium">{item.brand} · </span> : null}
                    {item.name}
                  </div>
                  <div className="text-xs text-gray-400">
                    <span>{item.count === 1 ? "1 spool" : `${item.count} spools`}</span> · {formatGrams(item.total_g)}
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {item.spools.map((spool) => (
                    <SpoolChip key={spool.id} spool={spool} onChanged={changed} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {adding && (
        <AddSpoolsModal
          materials={materials}
          brands={data?.brands || []}
          locations={locations}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            changed();
          }}
        />
      )}
    </section>
  );
}
