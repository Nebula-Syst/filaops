import { LANGUAGES, getLanguage, setLanguage } from "./index";

// La app móvil (nebula-erp-mobile) añade este marcador al User-Agent
const IN_MOBILE_APP =
  typeof navigator !== "undefined" && /NebulaErpApp/.test(navigator.userAgent);
// Origen local de Capacitor en Android: ahí vive la pantalla de servidores de la app
const APP_SERVER_PICKER_URL = "https://localhost/?select=1";

/** Tarjetas de Nebula para la página de Settings: idioma y, dentro de la app, servidor. */
export default function LanguageSettings() {
  const current = getLanguage();

  return (
    <>
      {IN_MOBILE_APP && (
        <div className="bg-gray-800 rounded-lg p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-white mb-1">
              Mobile app
            </h2>
            <p className="text-sm text-gray-400">
              Connected to{" "}
              <span className="notranslate text-gray-200">
                {window.location.host}
              </span>
            </p>
          </div>
          <a
            href={APP_SERVER_PICKER_URL}
            className="shrink-0 text-center bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg"
          >
            Change server
          </a>
        </div>
      )}
      <div className="bg-gray-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-white mb-1">Language</h2>
        <p className="text-sm text-gray-400 mb-4">
          Interface language for this browser. The page reloads to apply the
          change.
        </p>
        <label
          htmlFor="nebula-language"
          className="block text-sm font-medium text-gray-300 mb-1"
        >
          Language
        </label>
        <select
          id="nebula-language"
          value={current}
          onChange={(e) => setLanguage(e.target.value)}
          className="notranslate w-full md:w-1/2 bg-gray-700 border border-gray-600 rounded-lg px-4 py-2 text-white"
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
