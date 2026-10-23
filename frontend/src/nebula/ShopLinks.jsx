import { useEffect, useState } from "react";
import { API_URL } from "../config/api";

/**
 * PrintFlow: enlaces del artículo en las tiendas online, para abrirlo o
 * copiarlo y mandárselo a un cliente. Los guarda la sincronización de las
 * tiendas; si el artículo no está en ninguna, no se pinta.
 */
export default function ShopLinks({ item }) {
  const [links, setLinks] = useState([]);
  const [copied, setCopied] = useState(null);

  useEffect(() => {
    if (!item?.id) return undefined;
    let cancelled = false;
    fetch(`${API_URL}/api/v1/items/${item.id}/shop-links`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => !cancelled && setLinks(Array.isArray(data) ? data : []))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [item?.id]);

  if (!links.length) return null;

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
      <h3 className="mb-2 text-sm font-medium text-gray-300">In the online shop</h3>
      <ul className="space-y-2">
        {links.map((link) => (
          <li key={link.url} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-gray-400">{link.store}</span>
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
          </li>
        ))}
      </ul>
    </div>
  );
}
