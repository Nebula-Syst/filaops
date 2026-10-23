"""PrintFlow: estado en vivo de las impresoras Bambu por MQTT en la red local.

Usa el cliente MQTT de FilaOps (app.services.mqtt.client) pero con conexión
asíncrona y reconexión automática: una impresora apagada al arrancar se conecta
sola cuando se enciende. Cada minuto se releen las impresoras de la base de
datos, así que basta con poner IP, número de serie y código de acceso en
Impresoras para que empiece a leerla. Solo lectura: no se manda ninguna orden
a la impresora salvo "pushall" (pedir el estado completo).
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.db.session import SessionLocal
from app.logging_config import get_logger
from app.models import Printer
from app.services.mqtt.client import BambuMQTTClient

logger = get_logger(__name__)

SYNC_SECONDS = 60
FLUSH_SECONDS = 15
STALE_SECONDS = 120  # sin mensajes en este tiempo = no responde

# gcode_state de Bambu → estado de impresora de FilaOps
STATE_TO_STATUS = {
    "IDLE": "idle",
    "FINISH": "idle",
    "FAILED": "idle",  # el error se ve aparte; la impresora queda libre
    "PREPARE": "printing",
    "SLICING": "printing",
    "RUNNING": "printing",
    "PAUSE": "paused",
}

# Códigos de conexión MQTT que merece la pena explicar
CONNECT_ERRORS = {
    "Bad user name or password": "bad_access_code",
    "Not authorized": "bad_access_code",
}


def _deep_merge(target: Dict[str, Any], delta: Dict[str, Any]) -> None:
    """Las impresoras mandan solo lo que cambia, también dentro de "device"."""
    for key, value in delta.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


class LiveClient(BambuMQTTClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect_error: Optional[str] = None

    def connect(self) -> bool:
        # connect_async no bloquea y loop_start reintenta solo si no responde
        self.client.reconnect_delay_set(min_delay=5, max_delay=120)
        self.client.connect_async(self.host, 8883, keepalive=60)
        self.client.loop_start()
        return True

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connect_error = None if reason_code == 0 else CONNECT_ERRORS.get(str(reason_code), str(reason_code))
        super()._on_connect(client, userdata, flags, reason_code, properties)

    def _merge_print_status(self, print_data: Dict[str, Any]):
        _deep_merge(self._status_cache, print_data)
        self._update_friendly_fields()


# ---------------------------------------------------------------------------
# Resumen de la telemetría
# ---------------------------------------------------------------------------


def _num(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _packed_temp(value) -> Optional[Dict[str, float]]:
    """La H2D manda temperatura actual y objetivo en un entero (16 bits cada una)."""
    n = _num(value)
    if n is None:
        return None
    n = int(n)
    return {"current": n & 0xFFFF, "target": (n >> 16) & 0xFFFF}


def _temps(cache: Dict[str, Any]) -> Dict[str, Any]:
    device = cache.get("device") if isinstance(cache.get("device"), dict) else {}

    nozzles = []
    extruders = (device.get("extruder") or {}).get("info") if isinstance(device.get("extruder"), dict) else None
    if isinstance(extruders, list):
        for info in sorted(extruders, key=lambda i: i.get("id", 0) if isinstance(i, dict) else 0):
            temp = _packed_temp(info.get("temp")) if isinstance(info, dict) else None
            if temp:
                nozzles.append(temp)
    if not nozzles and cache.get("nozzle_temper") is not None:
        nozzles.append({"current": _num(cache.get("nozzle_temper")), "target": _num(cache.get("nozzle_target_temper"))})

    bed = None
    bed_info = (device.get("bed") or {}).get("info") if isinstance(device.get("bed"), dict) else None
    if isinstance(bed_info, dict) and bed_info.get("temp") is not None:
        bed = _packed_temp(bed_info.get("temp"))
    elif cache.get("bed_temper") is not None:
        bed = {"current": _num(cache.get("bed_temper")), "target": _num(cache.get("bed_target_temper"))}

    chamber = None
    ctc_info = (device.get("ctc") or {}).get("info") if isinstance(device.get("ctc"), dict) else None
    if isinstance(ctc_info, dict) and ctc_info.get("temp") is not None:
        chamber = _packed_temp(ctc_info.get("temp"))
    elif cache.get("chamber_temper") is not None:
        chamber = {"current": _num(cache.get("chamber_temper")), "target": None}

    return {"nozzles": nozzles, "bed": bed, "chamber": chamber}


def _ams(cache: Dict[str, Any]) -> list:
    ams = cache.get("ams") if isinstance(cache.get("ams"), dict) else {}
    tray_now = str(ams.get("tray_now", ""))
    trays = []
    for unit in ams.get("ams") or []:
        if not isinstance(unit, dict):
            continue
        for tray in unit.get("tray") or []:
            if not isinstance(tray, dict) or not tray.get("tray_type"):
                continue
            unit_id, slot = int(_num(unit.get("id")) or 0), int(_num(tray.get("id")) or 0)
            color = str(tray.get("tray_color") or "")[:6]
            trays.append({
                "unit": unit_id,
                "slot": slot + 1,
                "material": tray.get("tray_type"),
                "color": f"#{color}" if len(color) == 6 else None,
                "remaining": _num(tray.get("remain")) if (_num(tray.get("remain")) or -1) >= 0 else None,
                "active": tray_now == str(unit_id * 4 + slot),
            })
    return trays


def _hms(cache: Dict[str, Any]) -> list:
    codes = []
    for item in cache.get("hms") or []:
        if isinstance(item, dict) and item.get("attr") is not None and item.get("code") is not None:
            codes.append(f"{int(item['attr']):08X}_{int(item['code']):08X}")
    return codes


def summarize(status: Dict[str, Any], connect_error: Optional[str] = None) -> Dict[str, Any]:
    last_update = status.get("last_update")
    stale = True
    if last_update:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds()
        stale = age > STALE_SECONDS
    online = bool(status.get("connected")) and not stale
    state = str(status.get("gcode_state") or "").upper() or None
    print_error = int(_num(status.get("print_error")) or 0)
    return {
        "online": online,
        "connect_error": connect_error,
        "last_update": last_update,
        "state": state,
        "status": STATE_TO_STATUS.get(state, "idle") if online else "offline",
        "percent": _num(status.get("mc_percent")),
        "remaining_minutes": _num(status.get("mc_remaining_time")),
        "layer": _num(status.get("layer_num")),
        "total_layers": _num(status.get("total_layer_num")),
        "file": status.get("subtask_name") or status.get("gcode_file") or None,
        "print_error": f"{print_error:08X}" if print_error else None,
        "hms": _hms(status),
        "ams": _ams(status),
        "wifi_signal": status.get("wifi_signal"),
        **_temps(status),
    }


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------


def _credentials(printer: Printer):
    config = printer.connection_config or {}
    host = config.get("mqtt_host") or config.get("ip_address") or printer.ip_address
    serial = config.get("mqtt_serial") or config.get("serial") or printer.serial_number
    code = config.get("mqtt_access_code") or config.get("access_code")
    if host and serial and code:
        return (host.strip(), serial.strip(), str(code).strip())
    return None


class PrinterLiveService:
    def __init__(self):
        self._clients: Dict[int, LiveClient] = {}
        self._creds: Dict[int, tuple] = {}
        self._task: Optional[asyncio.Task] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self):
        if not self.running:
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        for printer_id in list(self._clients):
            self._drop(printer_id)

    async def _loop(self):
        elapsed = SYNC_SECONDS
        while True:
            try:
                if elapsed >= SYNC_SECONDS:
                    await asyncio.to_thread(self.sync)
                    elapsed = 0
                await asyncio.to_thread(self.flush)
            except Exception:  # que un fallo puntual no pare el servicio
                logger.exception("Error leyendo impresoras")
            await asyncio.sleep(FLUSH_SECONDS)
            elapsed += FLUSH_SECONDS

    def _drop(self, printer_id: int):
        client = self._clients.pop(printer_id, None)
        self._creds.pop(printer_id, None)
        if client:
            try:
                client.disconnect()
            except Exception:
                pass

    def sync(self):
        """Conecta impresoras nuevas, reconecta si cambian sus datos y suelta las borradas."""
        db = SessionLocal()
        try:
            printers = db.query(Printer).filter(Printer.active.is_(True), Printer.brand == "bambulab").all()
            wanted = {p.id: _credentials(p) for p in printers}
        finally:
            db.close()

        for printer_id in list(self._clients):
            if wanted.get(printer_id) != self._creds.get(printer_id):
                self._drop(printer_id)
        for printer_id, creds in wanted.items():
            if creds and printer_id not in self._clients:
                host, serial, code = creds
                client = LiveClient(printer_id=printer_id, host=host, serial=serial, access_code=code)
                client.connect()
                self._clients[printer_id] = client
                self._creds[printer_id] = creds
                logger.info(f"Leyendo impresora {printer_id} en {host}")

    def flush(self):
        """Guarda estado y última conexión, para que el resto de FilaOps lo vea."""
        if not self._clients:
            return
        live = self.live()
        db = SessionLocal()
        try:
            for printer_id, summary in live.items():
                printer = db.get(Printer, printer_id)
                if printer is None:
                    continue
                printer.status = summary["status"]
                if summary["online"]:
                    printer.last_seen = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def live(self) -> Dict[int, Dict[str, Any]]:
        return {
            printer_id: summarize(client.get_cached_status(), client.connect_error)
            for printer_id, client in list(self._clients.items())
        }

    def configured(self, printer_id: int) -> bool:
        return printer_id in self._clients


service = PrinterLiveService()


def enabled() -> bool:
    return os.environ.get("NEBULA_PRINTER_LIVE", "1") != "0"
