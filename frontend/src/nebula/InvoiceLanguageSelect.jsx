import { useState } from "react";
import { useApi } from "../hooks/useApi";
import { useLocale } from "../contexts/LocaleContext";
import { useToast } from "../components/Toast";

/**
 * PrintFlow: idioma del PDF de una factura (español / inglés).
 * Sin idioma guardado, la factura sale en el de la empresa (Ajustes → Formato de
 * números y fechas). Solo cambia los textos del PDF, nunca importes ni estado.
 */
export default function InvoiceLanguageSelect({ invoice, onChange }) {
  const api = useApi();
  const { locale } = useLocale();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const companyDefault = (locale || "").toLowerCase().startsWith("es") ? "es" : "en";
  const value = invoice?.language || companyDefault;

  const handleChange = async (e) => {
    const language = e.target.value;
    setSaving(true);
    try {
      const updated = await api.put(`/api/v1/invoices/${invoice.id}/language`, { language });
      onChange?.(updated);
    } catch (err) {
      toast.error(err.message || "Failed to update invoice language");
    } finally {
      setSaving(false);
    }
  };

  return (
    <label className="flex items-center gap-2 text-sm text-[var(--ink-2)]">
      <span>Invoice language</span>
      <select
        value={value}
        onChange={handleChange}
        disabled={saving || !invoice}
        className="notranslate rounded-lg bg-[var(--paper-sunk)] text-[var(--ink)] border border-[var(--rule-hair)] px-2 py-2 text-sm disabled:opacity-50"
      >
        <option value="es">Español</option>
        <option value="en">English</option>
      </select>
    </label>
  );
}
