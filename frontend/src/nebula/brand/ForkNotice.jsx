import { getLanguage } from "../i18n";

export const ORIGINAL_REPO = "https://github.com/BLB3DPrinting/filaops";
export const FORK_REPO = "https://github.com/Nebula-Syst/filaops";

/**
 * Aviso de que PrintFlow es un fork modificado de FilaOps (BSL 1.1).
 * Va con `notranslate` porque la capa i18n cambia "FilaOps" por "PrintFlow"
 * en toda la interfaz, y aquí el nombre original tiene que quedarse.
 */
export default function ForkNotice({ detailed = false, className = "" }) {
  const es = getLanguage() === "es";
  const link = (href, text) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline hover:text-white">
      {text}
    </a>
  );

  if (!detailed) {
    return (
      <p className={`notranslate text-xs text-center text-gray-500 ${className}`}>
        {es ? "PrintFlow es un fork modificado de " : "PrintFlow is a modified fork of "}
        {link(ORIGINAL_REPO, "FilaOps")}
        {es ? " de BLB3D Printing." : " by BLB3D Printing."}
      </p>
    );
  }

  return (
    <div className={`notranslate text-sm text-gray-400 space-y-2 ${className}`}>
      <p>
        {es
          ? "PrintFlow es un fork modificado de "
          : "PrintFlow is a modified fork of "}
        {link(ORIGINAL_REPO, "FilaOps")}
        {es
          ? ", el ERP para granjas de impresión 3D de BLB3D Printing. Incluye cambios propios (idioma, móvil, usuarios, clientes sin email…) y se actualiza con las versiones del original."
          : ", the 3D print farm ERP by BLB3D Printing. It adds its own changes (language, mobile, users, customers without email…) and keeps up with the original's releases."}
      </p>
      <p>
        {es ? "Licencia: " : "License: "}Business Source License 1.1 ·{" "}
        {link(FORK_REPO, es ? "código de PrintFlow" : "PrintFlow source")} ·{" "}
        {link(ORIGINAL_REPO, es ? "proyecto original" : "original project")}
      </p>
    </div>
  );
}
