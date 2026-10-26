import { useEffect, useState } from "react";
import { API_URL } from "../config/api";

/**
 * PrintFlow: los colores que ve el cliente en las tiendas online. Salen de las
 * bobinas que quedan; aquí se les pone el nombre de la tienda (los de PrintFlow
 * vienen del fabricante, en inglés) o se ocultan.
 */
const url = (path = "") => `${API_URL}/api/v1/items/nebula/shop-colors${path}`;

function Swatch({ hex, hex2 }) {
  const background = hex2 ? `linear-gradient(135deg, ${hex} 50%, ${hex2} 50%)` : hex || "#888";
  return <span className="inline-block h-6 w-6 shrink-0 rounded-full border border-gray-600" style={{ background }} />;
}

// El nombre va por color: el negro de PLA y el de ABS son una sola fila
const byColor = (colors) => {
  const rows = new Map();
  for (const c of colors) {
    const row = rows.get(c.color_id);
    if (!row) {
      rows.set(c.color_id, { ...c, materials: [c.material].filter(Boolean), brands: [...c.brands] });
      continue;
    }
    if (c.material && !row.materials.includes(c.material)) row.materials.push(c.material);
    for (const b of c.brands) if (!row.brands.includes(b)) row.brands.push(b);
    row.remaining_g += c.remaining_g;
  }
  return [...rows.values()];
};

function ColorRow({ color }) {
  const [name, setName] = useState(color.name === color.color_name ? "" : color.name);
  const [hidden, setHidden] = useState(color.hidden);
  const [state, setState] = useState(null);

  const save = async (next) => {
    setState("saving");
    try {
      const res = await fetch(url(`/${color.color_id}`), {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shop_name: next.name, hidden: next.hidden }),
      });
      if (!res.ok) throw new Error();
      setState("saved");
    } catch {
      setState("error");
    }
  };

  const original = color.name === color.color_name ? "" : color.name;
  return (
    <li className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1 rounded-lg border border-gray-700 p-2 sm:grid-cols-[auto_12rem_1fr_auto]">
      <Swatch hex={color.hex} hex2={color.hex_secondary} />
      <div className="min-w-0 text-sm">
        <div className="truncate text-gray-200">{color.color_name}</div>
        <div className="truncate text-xs text-gray-500">
          {[color.materials.join(", "), color.brands.join(", "), `${Math.round(color.remaining_g)} g`].filter(Boolean).join(" · ")}
        </div>
      </div>
      <input
        aria-label="Name in the shop"
        value={name}
        maxLength={100}
        placeholder={color.color_name}
        onChange={(e) => {
          setName(e.target.value);
          setState(null);
        }}
        onBlur={() => name.trim() !== original && save({ name, hidden })}
        className="col-span-2 rounded-lg border border-gray-700 bg-gray-900 px-2 py-1.5 text-sm text-white sm:col-span-1"
      />
      <label className="col-span-2 flex items-center gap-2 text-xs text-gray-400 sm:col-span-1">
        <input
          type="checkbox"
          checked={hidden}
          onChange={(e) => {
            setHidden(e.target.checked);
            save({ name, hidden: e.target.checked });
          }}
        />
        <span>Hide</span>
        {state === "saved" && <span className="text-emerald-400">✓</span>}
        {state === "error" && <span className="text-red-400">Could not save. Try again.</span>}
      </label>
    </li>
  );
}

export default function ShopColors() {
  const [colors, setColors] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(url(), { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((d) => !cancelled && d && setColors(byColor(d.colors)))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!colors) return null;

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold text-white mb-1">Colours in the shop</h2>
      <p className="text-sm text-gray-400 mb-4">
        The shop offers the colours with spools in stock. Give each one the name customers will see, or hide it.
      </p>
      {colors.length === 0 ? (
        <p className="text-sm text-gray-500">There are no spools in stock.</p>
      ) : (
        <ul className="space-y-2">
          {colors.map((c) => (
            <ColorRow key={c.color_id} color={c} />
          ))}
        </ul>
      )}
    </div>
  );
}
