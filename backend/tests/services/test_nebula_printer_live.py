"""PrintFlow: resumen de la telemetría de las impresoras Bambu."""
from datetime import datetime, timezone

from app.api.v1.endpoints.nebula_printers import _stem
from app.services.nebula_printer_live import LiveClient, _deep_merge, summarize


def _now():
    return datetime.now(timezone.utc).isoformat()


def test_p1s_printing():
    s = summarize({
        "connected": True,
        "last_update": _now(),
        "gcode_state": "RUNNING",
        "mc_percent": 42,
        "mc_remaining_time": 75,
        "layer_num": 30,
        "total_layer_num": 120,
        "subtask_name": "Nazareno 20cm",
        "nozzle_temper": 219.5,
        "nozzle_target_temper": 220,
        "bed_temper": 59.8,
        "bed_target_temper": 60,
        "print_error": 0,
        "hms": [{"attr": 0x05000500, "code": 0x00010007}],
        "ams": {
            "tray_now": "1",
            "ams": [{"id": "0", "tray": [
                {"id": "0", "tray_type": "PLA", "tray_color": "FF0000FF", "remain": 80},
                {"id": "1", "tray_type": "PETG", "tray_color": "00FF00FF", "remain": -1},
                {"id": "2"},
            ]}],
        },
    })
    assert s["online"] and s["status"] == "printing"
    assert s["percent"] == 42 and s["remaining_minutes"] == 75
    assert s["file"] == "Nazareno 20cm"
    assert s["nozzles"] == [{"current": 219.5, "target": 220}]
    assert s["bed"] == {"current": 59.8, "target": 60}
    assert s["hms"] == ["05000500_00010007"]
    assert s["print_error"] is None
    assert [t["material"] for t in s["ams"]] == ["PLA", "PETG"]
    assert s["ams"][1]["active"] and not s["ams"][0]["active"]
    assert s["ams"][0]["color"] == "#FF0000" and s["ams"][1]["remaining"] is None


def test_h2d_packed_temps():
    s = summarize({
        "connected": True,
        "last_update": _now(),
        "gcode_state": "IDLE",
        "device": {
            "extruder": {"info": [{"id": 1, "temp": (0 << 16) | 30}, {"id": 0, "temp": (220 << 16) | 215}]},
            "bed": {"info": {"temp": (60 << 16) | 58}},
            "ctc": {"info": {"temp": 35}},
        },
    })
    assert s["status"] == "idle"
    assert s["nozzles"] == [{"current": 215, "target": 220}, {"current": 30, "target": 0}]
    assert s["bed"] == {"current": 58, "target": 60}
    assert s["chamber"]["current"] == 35


def test_offline_when_stale_or_disconnected():
    assert summarize({"connected": False})["status"] == "offline"
    old = "2020-01-01T00:00:00+00:00"
    assert summarize({"connected": True, "last_update": old, "gcode_state": "RUNNING"})["status"] == "offline"


def test_error_code_hex():
    s = summarize({"connected": True, "last_update": _now(), "gcode_state": "FAILED", "print_error": 0x0300400C})
    assert s["print_error"] == "0300400C"
    assert s["status"] == "idle"


def test_deep_merge_keeps_nested_values():
    cache = {"device": {"bed": {"info": {"temp": 1}}, "ctc": {"info": {"temp": 2}}}}
    _deep_merge(cache, {"device": {"bed": {"info": {"temp": 3}}}, "mc_percent": None})
    assert cache == {"device": {"bed": {"info": {"temp": 3}}, "ctc": {"info": {"temp": 2}}}}


def test_bad_access_code_is_reported():
    client = LiveClient(printer_id=1, host="127.0.0.1", serial="X", access_code="bad")
    client._on_connect(client.client, None, None, "Not authorized", None)
    assert client.connect_error == "bad_access_code"
    assert summarize(client.get_cached_status(), client.connect_error)["connect_error"] == "bad_access_code"


def test_file_stem():
    assert _stem("Nazareno 20cm.gcode.3mf") == "nazareno 20cm"
    assert _stem("Nazareno_20cm_plate_1") == "nazareno 20cm"
    assert _stem("Nazareno-20cm.3mf") == "nazareno 20cm"
