import { LANGUAGES, getLanguage, setLanguage } from "./index";

/** Tarjeta de idioma para la página de Settings (preferencia por navegador). */
export default function LanguageSettings() {
  const current = getLanguage();

  return (
    <div className="bg-gray-800 rounded-lg p-6">
      <h2 className="text-xl font-semibold text-white mb-1">Language</h2>
      <p className="text-sm text-gray-400 mb-4">
        Interface language for this browser. The page reloads to apply the change.
      </p>
      <label htmlFor="nebula-language" className="block text-sm font-medium text-gray-300 mb-1">
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
  );
}
