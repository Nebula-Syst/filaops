// PrintFlow: toda la app usa el modo oscuro del sistema de diseño de upstream
// (ver theme.css). Se fija en <html> antes de que React pinte nada.
import "./theme.css";

document.documentElement.dataset.theme = "dim";
