// PrintFlow: formato de tiempos del estado en vivo de las impresoras.

export function formatDuration(minutes) {
  const n = Math.round(Number(minutes));
  if (!Number.isFinite(n) || n <= 0) return null;
  const h = Math.floor(n / 60);
  const m = n % 60;
  return h > 0 ? `${h} h ${m} min` : `${m} min`;
}

export function finishTime(minutes, now = new Date()) {
  const n = Number(minutes);
  if (!Number.isFinite(n) || n <= 0) return null;
  const end = new Date(now.getTime() + n * 60000);
  const sameDay = end.toDateString() === now.toDateString();
  const time = end.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${end.toLocaleDateString(undefined, { weekday: "short" })} ${time}`;
}
