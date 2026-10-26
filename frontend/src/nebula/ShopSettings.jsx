import { useEffect, useState } from "react";
import { API_URL } from "../config/api";

/**
 * PrintFlow: ajustes comunes de las tiendas online. El envío a domicilio se
 * cobra una vez por pedido; recoger en el taller y la entrega en mano son
 * gratis. La tienda lo aplica en su siguiente sincronización.
 */
export default function ShopSettings() {
  const [price, setPrice] = useState("");
  const [savedPrice, setSavedPrice] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/v1/items/nebula/shop-settings`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setPrice(String(d.home_shipping_price));
        setSavedPrice(String(d.home_shipping_price));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (savedPrice === null) return null;

  const value = parseFloat(price.replace(",", "."));
  const invalid = !Number.isFinite(value) || value < 0;

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setError(false);
    try {
      const res = await fetch(`${API_URL}/api/v1/items/nebula/shop-settings`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ home_shipping_price: value }),
      });
      if (!res.ok) throw new Error();
      const d = await res.json();
      setPrice(String(d.home_shipping_price));
      setSavedPrice(String(d.home_shipping_price));
      setSaved(true);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold text-white mb-1">Online shops</h2>
      <p className="text-sm text-gray-400 mb-4">
        Home delivery is charged once per order. Workshop pickup and hand delivery are free.
      </p>
      <label htmlFor="shop-home-shipping" className="block text-sm font-medium text-gray-300 mb-1">
        Home delivery price
      </label>
      <div className="flex flex-wrap items-center gap-3">
        <input
          id="shop-home-shipping"
          type="number"
          step="0.01"
          min="0"
          value={price}
          onChange={(e) => {
            setPrice(e.target.value);
            setSaved(false);
          }}
          className="w-40 px-4 py-2 bg-gray-900 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-blue-500"
        />
        <button
          type="button"
          onClick={save}
          disabled={saving || invalid || price === savedPrice}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          Save
        </button>
      </div>
      {saved && <p className="mt-3 text-xs text-emerald-400">Saved. The shop will update in a few minutes.</p>}
      {error && <p className="mt-3 text-xs text-red-400">Could not save. Try again.</p>}
    </div>
  );
}
