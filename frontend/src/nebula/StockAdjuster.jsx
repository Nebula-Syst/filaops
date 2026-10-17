import { useState } from "react";
import { API_URL } from "../config/api";

/**
 * PrintFlow: añadir o quitar unidades de un artículo desde su ficha.
 *
 * En la tabla de Artículos la cantidad solo se edita en una columna que en el
 * móvil queda fuera de la pantalla y hay que escribir el total exacto. Aquí se
 * suman o restan unidades con botones grandes. Usa el mismo ajuste de
 * inventario que la tabla (POST /inventory/adjust-quantity), así que queda en
 * el historial de movimientos. No depende de que el artículo tenga lista de
 * materiales ni rutas de producción.
 */
const REASONS = {
  add: ["Found inventory", "Physical count", "Returned goods", "System correction"],
  remove: ["Damaged goods", "Physical count", "Theft/Loss", "Quality issue", "System correction"],
};

const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};

export default function StockAdjuster({ item, onAdjusted }) {
  const isMaterial = Boolean(item.material_type_id);
  const unit = isMaterial ? "g" : item.unit || "EA";
  const [onHand, setOnHand] = useState(num(item.on_hand_qty));
  const [available, setAvailable] = useState(
    item.available_qty != null ? num(item.available_qty) : num(item.on_hand_qty)
  );
  const [mode, setMode] = useState(null); // null | "add" | "remove"
  const [amount, setAmount] = useState("1");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null);

  const open = (next) => {
    setMode(next);
    setAmount("1");
    setReason(REASONS[next][0]);
    setError(null);
    setDone(null);
  };

  const qty = num(amount);
  const newOnHand = mode === "remove" ? onHand - qty : onHand + qty;
  const invalid = qty <= 0 || newOnHand < 0;

  const save = async () => {
    if (invalid || saving) return;
    setSaving(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        product_id: String(item.id),
        location_id: "1",
        new_on_hand_quantity: String(newOnHand),
        adjustment_reason: reason,
        input_unit: isMaterial ? "G" : item.unit || "EA",
      });
      const res = await fetch(`${API_URL}/api/v1/inventory/adjust-quantity?${params}`, {
        method: "POST",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Failed to adjust inventory quantity"
        );
      }
      setOnHand(num(data.new_quantity));
      setAvailable(num(data.available_quantity));
      setDone(`${num(data.previous_quantity)} → ${num(data.new_quantity)}`);
      setMode(null);
      onAdjusted?.(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section
      aria-label="Stock"
      className="mb-6 rounded-xl border border-gray-700 bg-gray-800/50 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium text-gray-300">Units in stock</h3>
          <p className="text-2xl font-semibold text-white">
            {onHand} <span className="text-sm font-normal text-gray-400">{unit}</span>
          </p>
          {available !== onHand && (
            <p className="text-xs text-gray-400">{`Available: ${available} ${unit}`}</p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => open("remove")}
            disabled={saving || onHand <= 0}
            className="min-w-[3rem] rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-2 text-lg font-semibold text-red-300 hover:bg-red-500/20 disabled:opacity-40"
            aria-label="Remove units"
          >
            −
          </button>
          <button
            type="button"
            onClick={() => open("add")}
            disabled={saving}
            className="min-w-[3rem] rounded-lg border border-green-500/40 bg-green-500/10 px-4 py-2 text-lg font-semibold text-green-300 hover:bg-green-500/20 disabled:opacity-40"
            aria-label="Add units"
          >
            +
          </button>
        </div>
      </div>

      {mode && (
        <div className="mt-4 space-y-3 border-t border-gray-700 pt-4">
          <div className="text-sm font-medium text-gray-200">
            {mode === "add" ? "Add units" : "Remove units"}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="block text-sm text-gray-300">
              {`Quantity (${unit})`}
              <input
                type="number"
                inputMode="decimal"
                min="0"
                step={isMaterial ? "1" : "any"}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              />
            </label>
            <label className="block text-sm text-gray-300">
              Reason
              <select
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                className="mt-1 w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
              >
                {REASONS[mode].map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className={`text-sm ${newOnHand < 0 ? "text-red-400" : "text-gray-400"}`}>
            {newOnHand < 0
              ? `There are only ${onHand} ${unit} in stock.`
              : `Stock after the change: ${newOnHand} ${unit}`}
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setMode(null)}
              disabled={saving}
              className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={invalid || saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : mode === "add" ? "Add units" : "Remove units"}
            </button>
          </div>
        </div>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
      {done && !mode && (
        <p role="status" className="mt-3 text-sm text-green-400">
          {`Stock updated: ${done}`}
        </p>
      )}
    </section>
  );
}
