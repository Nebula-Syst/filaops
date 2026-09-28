"""Nebula (fork): clientes sin email."""
import io
import uuid

BASE_URL = "/api/v1/admin/customers"


def _uid():
    return uuid.uuid4().hex[:8]


def test_varios_clientes_sin_email(client):
    """El UNIQUE de users.email admite varios NULL."""
    a = client.post(BASE_URL, json={"first_name": f"Ana {_uid()}"})
    b = client.post(BASE_URL, json={"company_name": f"Taller {_uid()}"})
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["email"] is None and b.json()["email"] is None


def test_email_vacio_se_guarda_como_null(client):
    r = client.post(BASE_URL, json={"email": "  ", "first_name": "Luis"})
    assert r.status_code == 201
    assert r.json()["email"] is None


def test_quitar_y_poner_email_al_editar(client):
    email = f"cli-{_uid()}@example.com"
    c = client.post(BASE_URL, json={"email": email, "first_name": "Eva"}).json()
    r = client.patch(f"{BASE_URL}/{c['id']}", json={"email": ""})
    assert r.status_code == 200 and r.json()["email"] is None
    r = client.patch(f"{BASE_URL}/{c['id']}", json={"email": email})
    assert r.status_code == 200 and r.json()["email"] == email


def test_listado_y_busqueda_con_clientes_sin_email(client):
    name = f"SinMail{_uid()}"
    client.post(BASE_URL, json={"first_name": name})
    r = client.get(BASE_URL, params={"search": name})
    assert r.status_code == 200
    r = client.get(f"{BASE_URL}/search", params={"q": name})
    assert r.status_code == 200
    assert any(c["email"] is None for c in r.json())


def test_importar_csv_con_clientes_sin_email_existentes(client):
    """La importación no debe romper si ya hay clientes sin email en la BD."""
    client.post(BASE_URL, json={"first_name": f"Previo {_uid()}"})
    uid = _uid()
    csv_content = f"email,first_name,company_name\n,Pepe,\n,,Bar {uid}\nimp-{uid}@example.com,Con Email,\n"
    r = client.post(
        f"{BASE_URL}/import",
        files={"file": ("c.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 3
