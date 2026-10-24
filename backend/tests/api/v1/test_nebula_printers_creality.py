"""PrintFlow: Creality y Klipper se pueden dar de alta y salen en el estado en vivo."""
import uuid


def test_creality_brand_allowed_and_listed_live(client):
    brands = {b["code"] for b in client.get("/api/v1/printers/brands/info").json()}
    assert {"bambulab", "creality", "klipper"} <= brands

    uid = uuid.uuid4().hex[:6]
    res = client.post("/api/v1/printers/", json={
        "code": f"CRE-{uid}",
        "name": "Ender",
        "model": "Ender-3 V3",
        "brand": "creality",
        "ip_address": "192.168.31.45",
    })
    assert res.status_code == 200, res.text

    live = client.get("/api/v1/printers/nebula/live").json()
    ender = next(p for p in live["printers"] if p["code"] == f"CRE-{uid}")
    assert ender["missing"] == []  # basta con la IP, sin serie ni código
