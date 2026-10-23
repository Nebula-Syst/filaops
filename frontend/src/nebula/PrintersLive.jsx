import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_URL } from "../config/api";
import { formatDuration, finishTime } from "./printers";

const POLL_MS = 10000;

const BADGE = {
  printing: "bg-emerald-500/15 text-emerald-300 ring-emerald-400/30",
  paused: "bg-yellow-500/15 text-yellow-300 ring-yellow-400/30",
  idle: "bg-blue-500/15 text-blue-300 ring-blue-400/30",
  offline: "bg-slate-500/15 text-slate-300 ring-slate-400/20",
  error: "bg-red-500/15 text-red-300 ring-red-400/30",
};

const STATE_LABEL = {
  PREPARE: "Preparing",
  SLICING: "Preparing",
  RUNNING: "Printing",
  PAUSE: "Paused",
  FINISH: "Finished",
  FAILED: "Failed",
  IDLE: "Idle",
};

const MISSING_LABEL = {
  ip_address: "IP address",
  serial_number: "serial number",
  access_code: "access code",
};

function Temp({ label, value }) {
  if (!value || value.current == null) return null;
  return (
    <div className="rounded-lg bg-[var(--paper-sunk)] px-3 py-2">
      <div className="text-xs text-[var(--ink-3)]">{label}</div>
      <div className="font-medium text-[var(--ink)]">
        {Math.round(value.current)}°C
        {value.target ? <span className="text-[var(--ink-3)]"> / {Math.round(value.target)}°C</span> : null}
      </div>
    </div>
  );
}

function OfflineReason({ printer }) {
  if (printer.missing.length) {
    return (
      <span>
        <span>Missing:</span>{" "}
        {printer.missing.map((field, i) => (
          <span key={field}>
            {i > 0 ? ", " : ""}
            <span>{MISSING_LABEL[field]}</span>
          </span>
        ))}
      </span>
    );
  }
  if (printer.live?.connect_error === "bad_access_code") return <span>Wrong access code.</span>;
  return <span>Not responding. Check that it is on and connected to the network.</span>;
}

/**
 * PrintFlow: estado en vivo de las impresoras Bambu (lo lee el backend por
 * MQTT en la red local). Solo lectura; si no hay impresoras Bambu no se pinta.
 */
export default function PrintersLive({ onEdit }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch(`${API_URL}/api/v1/printers/nebula/live`, { credentials: "include" })
        .then((res) => (res.ok ? res.json() : null))
        .then((json) => !cancelled && json && setData(json))
        .catch(() => {});
    load();
    const timer = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  if (!data?.printers?.length) return null;

  return (
    <section className="space-y-3" aria-label="Live status">
      <h2 className="text-lg font-semibold text-[var(--ink)]">Live status</h2>
      <div className="grid gap-4 md:grid-cols-2">
        {data.printers.map((printer) => {
          const live = printer.live;
          const online = Boolean(live?.online);
          const hasError = online && (live.print_error || live.hms?.length);
          const status = !online ? "offline" : hasError ? "error" : live.status;
          const active = online && (live.status === "printing" || live.status === "paused");
          const percent = Math.max(0, Math.min(100, Number(live?.percent) || 0));
          const remaining = formatDuration(live?.remaining_minutes);
          return (
            <article
              key={printer.id}
              data-testid={`printer-live-${printer.id}`}
              className="rounded-xl border border-[var(--rule-hair)] bg-[var(--paper)] p-5 shadow-[var(--shadow-pop)]"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-base font-semibold text-[var(--ink)]">{printer.name}</h3>
                  <p className="text-sm text-[var(--ink-3)]">
                    {printer.code}
                    {printer.model ? ` · ${printer.model}` : ""}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${BADGE[status] || BADGE.offline}`}>
                  {online ? STATE_LABEL[live.state] || "Idle" : "Offline"}
                </span>
              </div>

              {!online ? (
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-[var(--ink-2)]">
                  <OfflineReason printer={printer} />
                  {onEdit && (
                    <button
                      type="button"
                      onClick={() => onEdit(printer.id)}
                      className="rounded-lg border border-[var(--rule-hair)] bg-[var(--paper-sunk)] px-3 py-1.5 text-[var(--ink-2)] hover:text-[var(--ink)]"
                    >
                      Edit
                    </button>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {hasError ? (
                    <div className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-2 text-sm text-red-200">
                      {`Printer error ${live.hms?.[0] ? `HMS ${live.hms[0]}` : live.print_error}`}
                    </div>
                  ) : null}

                  {active && (
                    <div>
                      <div className="mb-1 flex justify-between gap-2 text-sm">
                        <span className="truncate font-medium text-[var(--ink)]" title={live.file || ""}>
                          {live.file || "—"}
                        </span>
                        <span className="shrink-0 text-[var(--ink-2)]">{Math.round(percent)}%</span>
                      </div>
                      <div
                        className="h-2 overflow-hidden rounded-full bg-[var(--paper-sunk)]"
                        role="progressbar"
                        aria-valuenow={Math.round(percent)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <div className="h-full bg-emerald-400" style={{ width: `${percent}%` }} />
                      </div>
                      <p className="mt-1 text-sm text-[var(--ink-3)]">
                        {remaining ? <span>{`${remaining} left · finishes at ${finishTime(live.remaining_minutes)}`}</span> : null}
                        {live.total_layers ? <span>{` · layer ${live.layer || 0} of ${live.total_layers}`}</span> : null}
                      </p>
                      {printer.product && (
                        <p className="mt-1 text-sm text-[var(--ink-2)]">
                          {printer.product.sku} · {printer.product.name}
                          {printer.product.production_orders.map((order) => (
                            <Link
                              key={order.id}
                              to={`/admin/production/${order.id}`}
                              className="ml-2 text-[var(--accent,#60a5fa)] hover:underline"
                            >
                              {order.code}
                            </Link>
                          ))}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                    {live.nozzles?.map((nozzle, i) => (
                      <Temp
                        key={i}
                        label={live.nozzles.length > 1 ? (i === 0 ? "Right nozzle" : "Left nozzle") : "Nozzle"}
                        value={nozzle}
                      />
                    ))}
                    <Temp label="Bed" value={live.bed} />
                    <Temp label="Chamber" value={live.chamber} />
                  </div>

                  {live.ams?.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {live.ams.map((tray) => (
                        <span
                          key={`${tray.unit}-${tray.slot}`}
                          title={tray.remaining != null ? `${tray.remaining}%` : undefined}
                          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs text-[var(--ink-2)] ${
                            tray.active ? "border-emerald-400" : "border-[var(--rule-hair)]"
                          }`}
                        >
                          <span
                            className="h-3 w-3 rounded-full border border-black/20"
                            style={{ background: tray.color || "transparent" }}
                          />
                          {tray.material}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
