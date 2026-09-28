"""Nebula (fork): el límite de usuarios del plan community se configura por entorno."""
import importlib

import pytest

import app.core.seat_limits as seat_limits


@pytest.fixture
def reload_seat_limits(monkeypatch):
    def _reload(value):
        if value is None:
            monkeypatch.delenv("NEBULA_COMMUNITY_SEAT_CAP", raising=False)
        else:
            monkeypatch.setenv("NEBULA_COMMUNITY_SEAT_CAP", value)
        return importlib.reload(seat_limits)

    yield _reload
    # Dejar el módulo como estaba para el resto de la suite
    monkeypatch.delenv("NEBULA_COMMUNITY_SEAT_CAP", raising=False)
    importlib.reload(seat_limits)


def test_sin_variable_mantiene_el_limite_de_upstream(reload_seat_limits):
    mod = reload_seat_limits(None)
    assert mod.seat_cap_for_tier("community") == 1


@pytest.mark.parametrize("value", ["unlimited", "UNLIMITED", "none", "0"])
def test_unlimited_quita_el_limite(reload_seat_limits, value):
    mod = reload_seat_limits(value)
    assert mod.seat_cap_for_tier("community") is None
    assert mod.seat_cap_for_tier("") is None  # tier desconocido cae en community


def test_numero_fija_el_limite(reload_seat_limits):
    mod = reload_seat_limits("5")
    assert mod.seat_cap_for_tier("community") == 5
    assert mod.seat_cap_for_tier("professional") is None
