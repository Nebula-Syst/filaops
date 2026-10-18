import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "../config/api";
import { getLanguage } from "./i18n";
import { formatSize } from "./files";

/**
 * PrintFlow: archivos de impresión (3MF, STL, gcode…) de un artículo.
 *
 * Un artículo puede tener varios (una placa por color, piezas sueltas…). Se
 * suben aquí y se descargan desde la ficha o desde la orden de trabajo, sin
 * tener que buscarlos en el ordenador.
 */
const ACCEPTED = ".3mf,.stl,.obj,.step,.stp,.gcode,.gco,.bgcode,.zip,.pdf,.png,.jpg,.jpeg";
const MAX_MB = 100;

function upload(itemId, files, onProgress) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/v1/items/${itemId}/files`);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        /* respuesta sin JSON (p. ej. 413 del proxy) */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data || []);
      else if (xhr.status === 413) reject(new Error(`Files can be up to ${MAX_MB} MB each`));
      else reject(new Error(typeof data?.detail === "string" ? data.detail : "Upload failed"));
    };
    xhr.onerror = () => reject(new Error("Upload failed"));
    xhr.send(form);
  });
}

export default function ProductFiles({ item }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [editing, setEditing] = useState(null); // { id, notes }
  const input = useRef(null);

  const load = useCallback(() => {
    return fetch(`${API_URL}/api/v1/items/${item.id}/files`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Could not load print files"))))
      .then(setFiles)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [item.id]);

  useEffect(() => {
    load();
  }, [load]);

  const send = async (list) => {
    const chosen = Array.from(list || []);
    if (!chosen.length || progress !== null) return;
    const big = chosen.find((f) => f.size > MAX_MB * 1024 * 1024);
    if (big) {
      setError(`${big.name}: files can be up to ${MAX_MB} MB each`);
      return;
    }
    setError(null);
    setProgress(0);
    try {
      const created = await upload(item.id, chosen, setProgress);
      setFiles((prev) => [...prev, ...created]);
    } catch (err) {
      setError(err.message);
    } finally {
      setProgress(null);
      if (input.current) input.current.value = "";
    }
  };

  const remove = async (file) => {
    const question = getLanguage() === "es" ? `¿Borrar ${file.file_name}?` : `Delete ${file.file_name}?`;
    if (!window.confirm(question)) return;
    setError(null);
    const res = await fetch(`${API_URL}/api/v1/items/${item.id}/files/${file.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.ok) setFiles((prev) => prev.filter((f) => f.id !== file.id));
    else setError("Could not delete the file");
  };

  const saveNotes = async () => {
    if (!editing) return;
    const res = await fetch(`${API_URL}/api/v1/items/${item.id}/files/${editing.id}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: editing.notes }),
    });
    if (res.ok) {
      const updated = await res.json();
      setFiles((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
      setEditing(null);
    } else {
      setError("Could not save the note");
    }
  };

  return (
    <section
      aria-label="Print files"
      className={`rounded-xl border bg-gray-800/50 p-4 ${dragging ? "border-blue-500" : "border-gray-700"}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        send(e.dataTransfer.files);
      }}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-medium text-gray-300">Print files</h3>
          <p className="text-xs text-gray-400">3MF, STL, gcode… One or several. Drag them here or pick them.</p>
        </div>
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={progress !== null}
          className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50"
        >
          + Add files
        </button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          data-testid="product-files-input"
          onChange={(e) => send(e.target.files)}
        />
      </div>

      {progress !== null && (
        <div className="mb-3" role="status">
          <div className="h-2 overflow-hidden rounded bg-gray-700">
            <div className="h-full bg-blue-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-1 text-xs text-gray-400">{`Uploading... ${progress}%`}</p>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : files.length === 0 ? (
        <p className="text-sm text-gray-400">No print files yet.</p>
      ) : (
        <ul className="divide-y divide-gray-700">
          {files.map((file) => (
            <li key={file.id} className="flex flex-wrap items-center gap-2 py-2">
              <div className="min-w-0 flex-1">
                <a
                  href={`${API_URL}${file.download_url}`}
                  className="block truncate text-sm font-medium text-blue-400 hover:underline"
                  download={file.file_name}
                >
                  {file.file_name}
                </a>
                {editing?.id === file.id ? (
                  <div className="mt-1 flex gap-2">
                    <input
                      type="text"
                      autoFocus
                      value={editing.notes}
                      placeholder="White PLA, 0.2 mm, 4 per bed..."
                      onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          saveNotes();
                        }
                        if (e.key === "Escape") setEditing(null);
                      }}
                      className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none"
                    />
                    <button type="button" onClick={saveNotes} className="rounded bg-blue-600 px-2 py-1 text-xs text-white">
                      Save
                    </button>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">
                    {formatSize(file.file_size)}
                    {file.notes ? ` · ${file.notes}` : ""}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setEditing({ id: file.id, notes: file.notes || "" })}
                className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
              >
                Note
              </button>
              <a
                href={`${API_URL}${file.download_url}`}
                download={file.file_name}
                className="rounded border border-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
              >
                Download
              </a>
              <button
                type="button"
                onClick={() => remove(file)}
                aria-label={`Delete ${file.file_name}`}
                className="rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-xs text-red-300 hover:bg-red-500/20"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p role="alert" className="mt-3 text-sm text-red-400">{error}</p>}
    </section>
  );
}
