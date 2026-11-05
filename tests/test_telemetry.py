import pytest

from jarvis import telemetry


class IpGeo:
    def json(self):
        return {"latitude": "-22.9056", "longitude": "-47.0608", "city": "Campinas"}


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setattr(telemetry, "_place", None)
    monkeypatch.setattr(telemetry, "_place_ts", 0.0)
    monkeypatch.setattr(telemetry.config, "LOCATION", "")
    monkeypatch.setattr(telemetry.config, "LOCAL_PRECISO", True)
    monkeypatch.setattr(telemetry.httpx, "get", lambda *_a, **_k: IpGeo())
    names = {(-22.73, -47.65): "Piracicaba/SP", (-22.9056, -47.0608): "Campinas/SP"}
    monkeypatch.setattr(telemetry, "reverse_geocode", lambda lat, lon: names[(round(lat, 4), round(lon, 4))])


def test_mac_location_wins_over_ip(fresh, monkeypatch):
    monkeypatch.setattr(telemetry.location, "current", lambda: {"lat": -22.73, "lon": -47.65, "acc": 35})
    assert telemetry.place() == {"name": "Piracicaba/SP", "lat": -22.73, "lon": -47.65, "approx": False}


def test_without_mac_location_ip_is_marked_approximate(fresh, monkeypatch):
    monkeypatch.setattr(telemetry.location, "current", lambda: None)
    p = telemetry.place()
    assert p["name"] == "Campinas/SP" and p["approx"]


def test_mac_hiccup_keeps_last_precise_place(fresh, monkeypatch):
    monkeypatch.setattr(telemetry.location, "current", lambda: {"lat": -22.73, "lon": -47.65, "acc": 35})
    telemetry.place()
    monkeypatch.setattr(telemetry, "_place_ts", 0.0)  # venceu os 30 min
    monkeypatch.setattr(telemetry.location, "current", lambda: None)
    assert telemetry.place()["name"] == "Piracicaba/SP"


def test_precise_location_can_be_turned_off(fresh, monkeypatch):
    monkeypatch.setattr(telemetry.config, "LOCAL_PRECISO", False)
    monkeypatch.setattr(telemetry.location, "current", lambda: pytest.fail("não devia pedir a localização ao Mac"))
    assert telemetry.place()["approx"]
