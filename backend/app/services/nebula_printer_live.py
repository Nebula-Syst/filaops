"""PrintFlow: estado en vivo de las impresoras en la red local.

Bambu por MQTT y Creality/Klipper por la API HTTP de Moonraker.

Usa el cliente MQTT de FilaOps (app.services.mqtt.client) pero con conexión
asíncrona y reconexión automática: una impresora apagada al arrancar se conecta
sola cuando se enciende. Cada minuto se releen las impresoras de la base de
datos, así que basta con poner IP, número de serie y código de acceso en
Impresoras para que empiece a leerla. Solo lectura: no se manda ninguna orden
a la impresora salvo "pushall" (pedir el estado completo).

Las Creality (K1, K2, Hi, Ender-3 V3...) y cualquier Klipper llevan Moonraker:
se pregunta su estado por HTTP en cada guardado (cada 15 s), solo hace falta la IP.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

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

# print_stats.state de Moonraker → el mismo código que usan las Bambu
MOONRAKER_STATES = {
    "standby": "IDLE",
    "printing": "RUNNING",
    "paused": "PAUSE",
    "complete": "FINISH",
    "cancelled": "IDLE",
    "error": "FAILED",
}

MOONRAKER_BRANDS = ("creality", "klipper")
LIVE_BRANDS = ("bambulab",) + MOONRAKER_BRANDS

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

    def poll(self):
        pass  # las Bambu mandan solas lo que cambia

    def summary(self) -> Dict[str, Any]:
        return summarize(self.get_cached_status(), self.connect_error)


MOONRAKER_OBJECTS = {
    "print_stats": None,
    "display_status": ["progress"],
    "virtual_sdcard": ["progress", "layer", "layer_count"],
    "extruder": ["temperature", "target"],
    "heater_bed": ["temperature", "target"],
    "temperature_sensor chamber_temp": ["temperature"],
}


class MoonrakerClient:
    """Pregunta el estado a Moonraker; si no contesta se queda con el último."""

    def __init__(self, printer_id: int, host: str, port: int = 7125, api_key: Optional[str] = None):
        self.printer_id = printer_id
        self.url = f"http://{host}:{port}/printer/objects/query"
        self.headers = {"X-Api-Key": api_key} if api_key else {}
        self.status: Dict[str, Any] = {}
        self.last_update: Optional[str] = None
        self.connect_error: Optional[str] = None

    def poll(self):
        try:
            response = httpx.post(self.url, json={"objects": MOONRAKER_OBJECTS}, headers=self.headers, timeout=5)
            if response.status_code in (401, 403):
                self.connect_error = "bad_api_key"
                return
            response.raise_for_status()
            self.status = response.json()["result"]["status"]
            self.last_update = datetime.now(timezone.utc).isoformat()
            self.connect_error = None
        except (httpx.HTTPError, ValueError, KeyError) as e:
            logger.debug(f"Moonraker {self.url}: {e}")

    def summary(self) -> Dict[str, Any]:
        return summarize_moonraker(self.status, self.last_update, self.connect_error)

    def disconnect(self):
        pass


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


def summarize_moonraker(status: Dict[str, Any], last_update: Optional[str], connect_error: Optional[str] = None) -> Dict[str, Any]:
    """Lo mismo que summarize() pero con lo que devuelve Moonraker."""
    stale = True
    if last_update:
        stale = (datetime.now(timezone.utc) - datetime.fromisoformat(last_update)).total_seconds() > STALE_SECONDS
    online = not stale
    stats = status.get("print_stats") or {}
    sdcard = status.get("virtual_sdcard") or {}
    info = stats.get("info") or {}
    state = MOONRAKER_STATES.get(str(stats.get("state") or "").lower()) if stats else None

    progress = _num((status.get("display_status") or {}).get("progress")) or _num(sdcard.get("progress")) or 0
    duration = _num(stats.get("print_duration")) or 0
    remaining = None
    if state in ("RUNNING", "PAUSE") and progress > 0.01 and duration > 0:
        remaining = round((duration / progress - duration) / 60)

    def temp(name):
        heater = status.get(name) or {}
        if heater.get("temperature") is None:
            return None
        return {"current": _num(heater.get("temperature")), "target": _num(heater.get("target"))}

    nozzle = temp("extruder")
    return {
        "online": online,
        "connect_error": connect_error,
        "last_update": last_update,
        "state": state,
        "status": STATE_TO_STATUS.get(state, "idle") if online else "offline",
        "percent": round(progress * 100) if state in ("RUNNING", "PAUSE", "FINISH") else None,
        "remaining_minutes": remaining,
        "layer": _num(info.get("current_layer")) or _num(sdcard.get("layer")) or None,
        "total_layers": _num(info.get("total_layer")) or _num(sdcard.get("layer_count")) or None,
        "file": stats.get("filename") or None,
        "print_error": None,
        "hms": [],
        "ams": [],
        "wifi_signal": None,
        "nozzles": [nozzle] if nozzle else [],
        "bed": temp("heater_bed"),
        "chamber": temp("temperature_sensor chamber_temp"),
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


def _moonraker_credentials(printer: Printer):
    config = printer.connection_config or {}
    host = config.get("ip_address") or printer.ip_address
    if not host:
        return None
    port = int(_num(config.get("port")) or 7125)
    return ("moonraker", host.strip(), port, config.get("api_key") or None)


class PrinterLiveService:
    def __init__(self):
        self._clients: Dict[int, Any] = {}  # LiveClient o MoonrakerClient
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
            printers = db.query(Printer).filter(Printer.active.is_(True), Printer.brand.in_(LIVE_BRANDS)).all()
            wanted = {
                p.id: _moonraker_credentials(p) if p.brand in MOONRAKER_BRANDS else _credentials(p)
                for p in printers
            }
        finally:
            db.close()

        for printer_id in list(self._clients):
            if wanted.get(printer_id) != self._creds.get(printer_id):
                self._drop(printer_id)
        for printer_id, creds in wanted.items():
            if creds and printer_id not in self._clients:
                if creds[0] == "moonraker":
                    _, host, port, api_key = creds
                    client = MoonrakerClient(printer_id, host, port, api_key)
                else:
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
        for client in list(self._clients.values()):
            client.poll()
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
        return {printer_id: client.summary() for printer_id, client in list(self._clients.items())}

    def configured(self, printer_id: int) -> bool:
        return printer_id in self._clients


service = PrinterLiveService()


def enabled() -> bool:
    return os.environ.get("NEBULA_PRINTER_LIVE", "1") != "0"
