import { useState } from "react";
import { API_URL } from "../config/api";
import Modal from "../components/Modal";

/**
 * PrintFlow: importar artículos desde un CSV (el de Excel en español vale).
 *
 * Usa POST /items/nebula/import, que entiende cabeceras en español, comas
 * decimales y las columnas de precio por cantidad (precio_desde_4…).
 */
export default function ImportItemsModal({ isOpen, onClose, onImported }) {
  const [file, setFile] = useState(null);
  const [updateExisting, setUpdateExisting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const close = () => {
    if (busy) return;
    setFile(null);
    setResult(null);
    setError(null);
    onClose();
  };

  const submit = async () => {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const params = new URLSearchParams({ update_existing: String(updateExisting) });
      const res = await fetch(`${API_URL}/api/v1/items/nebula/import?${params}`, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Import failed");
      setResult(data);
      if (data.created || data.updated) onImported?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={close} title="Import items" className="w-full max-w-xl" disableClose={busy}>
      <div className="space-y-4 p-6">
        <h2 className="text-lg font-semibold text-white">Import items</h2>
        <div className="space-y-2 text-sm text-gray-300">
          <p>
            Upload a CSV with one item per row. From Excel: File → Save as → CSV (semicolon delimited).
          </p>
          <p className="text-gray-400">
            Columns: sku, nombre, descripcion, tipo, categoria, precio, coste. For quantity prices add columns like
            precio_desde_4 or precio_desde_200 (price per unit from that quantity).
          </p>
          <a
            href={`${API_URL}/api/v1/items/nebula/import-template`}
            download="plantilla-articulos.csv"
            className="inline-block text-blue-400 hover:underline"
          >
            Download template
          </a>
        </div>

        <label className="block text-sm text-gray-300">
          CSV file
          <input
            type="file"
            accept=".csv,.txt,text/csv"
            data-testid="import-file-input"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setResult(null);
            }}
            className="mt-1 block w-full text-sm text-gray-300 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-700 file:px-3 file:py-2 file:text-white"
          />
        </label>

        <label className="flex items-center gap-2 text-sm text-gray-300">
          <input
            type="checkbox"
            checked={updateExisting}
            onChange={(e) => setUpdateExisting(e.target.checked)}
          />
          Update items that already exist (same SKU)
        </label>

        {error && <p role="alert" className="text-sm text-red-400">{error}</p>}

        {result && (
          <div role="status" className="space-y-2 rounded-lg border border-gray-700 bg-gray-800/50 p-3 text-sm">
            <p className="text-green-400">
              {`Created: ${result.created} · Updated: ${result.updated} · Skipped: ${result.skipped}`}
            </p>
            {result.tiers_updated > 0 && (
              <p className="text-gray-300">{`Quantity prices saved for ${result.tiers_updated} items`}</p>
            )}
            {result.skipped > 0 && !updateExisting && (
              <p className="text-gray-400">Items whose SKU already existed were left as they were.</p>
            )}
            {result.errors?.length > 0 && (
              <ul className="max-h-40 space-y-0.5 overflow-auto text-red-300">
                {result.errors.map((e, i) => (
                  <li key={i}>
                    {e.row ? `Row ${e.row}` : e.sku}
                    {e.row && e.sku ? ` (${e.sku})` : ""}
                    {`: ${e.error}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="flex justify-end gap-3 border-t border-gray-700 pt-4">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-gray-300 hover:bg-gray-700"
          >
            {result ? "Close" : "Cancel"}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!file || busy}
            className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Importing..." : "Import"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
