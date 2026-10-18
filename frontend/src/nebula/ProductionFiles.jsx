import { useEffect, useState } from "react";
import { API_URL } from "../config/api";
import { formatSize } from "./files";

/**
 * PrintFlow: archivos de impresión del artículo en su orden de trabajo, para
 * descargarlos al lanzar la impresión sin buscarlos. Si no tiene, no se pinta.
 */
export default function ProductionFiles({ productId }) {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    if (!productId) return undefined;
    let cancelled = false;
    fetch(`${API_URL}/api/v1/items/${productId}/files`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => !cancelled && setFiles(Array.isArray(data) ? data : []))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [productId]);

  if (!files.length) return null;

  return (
    <div className="bg-[var(--paper)] border border-[var(--rule-hair)] rounded-xl p-6 shadow-[var(--shadow-pop)]">
      <h2 className="text-lg font-semibold text-[var(--ink)] mb-4">Print files</h2>
      <ul className="divide-y divide-[var(--rule-hair)]">
        {files.map((file) => (
          <li key={file.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <div className="min-w-0">
              <p className="truncate font-medium text-[var(--ink)]">{file.file_name}</p>
              <p className="text-sm text-[var(--ink-3)]">
                {formatSize(file.file_size)}
                {file.notes ? ` · ${file.notes}` : ""}
              </p>
            </div>
            <a
              href={`${API_URL}${file.download_url}`}
              download={file.file_name}
              className="rounded-lg bg-[var(--paper-sunk)] border border-[var(--rule-hair)] px-4 py-2 text-sm text-[var(--ink-2)] hover:text-[var(--ink)]"
            >
              Download
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
