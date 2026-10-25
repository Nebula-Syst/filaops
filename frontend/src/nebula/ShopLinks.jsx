import { useEffect, useState } from "react";
import { API_URL } from "../config/api";

/**
 * PrintFlow: en qué tiendas online se vende el artículo y su enlace en cada
 * una. Las casillas se guardan al momento y la tienda las aplica en su
 * siguiente sincronización (cada 5 minutos). Los enlaces los guarda la
 * sincronización cuando el artículo ya está publicado en esa tienda.
 */
export default function ShopLinks({ item }) {
  const [stores, setStores] = useState([]);
  const [links, setLinks] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    if (!item?.id) return undefined;
    let cancelled = false;
    const get = (path, fallback) =>
      fetch(`${API_URL}/api/v1/items/${item.id}/${path}`, { credentials: "include" })
        .then((res) => (res.ok ? res.json() : fallback))
        .catch(() => fallback);
    Promise.all([get("shops", { stores: [] }), get("shop-links", [])]).then(([shops, shopLinks]) => {
      if (cancelled) return;
      setStores(Array.isArray(shops?.stores) ? shops.stores : []);
      setLinks(Array.isArray(shopLinks) ? shopLinks : []);
    });
    return () => {
      cancelled = true;
    };
  }, [item?.id]);

  if (!item?.id || !stores.length) return null;

  const toggle = async (storeId) => {
    const next = stores.map((s) => (s.id === storeId ? { ...s, selected: !s.selected } : s));
    setStores(next);
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/items/${item.id}/shops`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ store_ids: next.filter((s) => s.selected).map((s) => s.id) }),
      });
      if (!res.ok) throw new Error();
      setStores((await res.json()).stores);
      setSaved(true);
    } catch {
      setStores(stores);
      setError(true);
    } finally {
      setSaving(false);
    }
  };

  const copy = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      window.prompt("Copy the link", url);
    }
  };

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-4">
      <h3 className="mb-1 text-sm font-medium text-gray-300">Online shops</h3>
      <p className="mb-3 text-xs text-gray-500">Choose the shops where this item is sold.</p>
      <ul className="space-y-3">
        {stores.map((store) => {
          const link = links.find((l) => l.store === store.name);
          return (
            <li key={store.id} className="text-sm">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={store.selected}
                  disabled={saving}
                  onChange={() => toggle(store.id)}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-900"
                />
                <span className="text-gray-200">{store.name}</span>
                {store.domains?.[0] && <span className="text-xs text-gray-500">{store.domains[0]}</span>}
              </label>
              {store.selected && link && (
                <div className="ml-6 mt-1 flex flex-wrap items-center gap-2">
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="min-w-0 flex-1 truncate text-blue-400 hover:underline"
                  >
                    {link.url}
                  </a>
                  <button
                    type="button"
                    onClick={() => copy(link.url)}
                    className="rounded-lg border border-gray-700 px-3 py-1 text-gray-300 hover:text-white"
                  >
                    {copied === link.url ? "Copied" : "Copy link"}
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {saved && <p className="mt-3 text-xs text-emerald-400">Saved. The shop will update in a few minutes.</p>}
      {error && <p className="mt-3 text-xs text-red-400">Could not save. Try again.</p>}
    </div>
  );
}
