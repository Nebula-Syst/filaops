import { DELIVERY_METHODS } from "./delivery";

/**
 * PrintFlow: selector del método de entrega (envío / entrega en mano / recogida).
 * Botones segmentados para que se pulse bien también en el móvil.
 */
export default function DeliveryMethodSelect({ value, onChange, disabled = false }) {
  const current = value || "ship";
  return (
    <div role="radiogroup" aria-label="Delivery method" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {DELIVERY_METHODS.map((method) => {
        const selected = current === method.value;
        return (
          <button
            key={method.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(method.value)}
            className={`rounded-lg border px-3 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              selected
                ? "border-[var(--orange)] bg-[var(--orange)]/10 text-[var(--ink)]"
                : "border-[var(--rule-hair)] bg-[var(--paper-sunk)] text-[var(--ink-2)] hover:border-[var(--ink-4)]"
            }`}
          >
            <div className="text-sm font-medium">{method.label}</div>
            <div className="text-xs text-[var(--ink-3)]">{method.hint}</div>
          </button>
        );
      })}
    </div>
  );
}
