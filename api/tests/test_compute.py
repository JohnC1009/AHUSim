"""/v1/solve, /v1/scenario, /v1/checks, /v1/chart-grid, /v1/schema."""

import copy

import pytest

from .conftest import auth

SUMMER = {
    "id": "summer_design",
    "oa_db": {"value": 91, "unit": "F"},
    "oa_wb": {"value": 74, "unit": "F"},
    "ra_db": {"value": 75, "unit": "F"},
    "ra_rh": {"value": 50, "unit": "%"},
    "schedule": "occupied",
}
WARMUP = {
    "id": "winter_warmup",
    "oa_db": {"value": 13, "unit": "F"},
    "oa_rh": {"value": 50, "unit": "%"},
    "ra_db": {"value": 62, "unit": "F"},
    "ra_rh": {"value": 30, "unit": "%"},
    "schedule": "pre_occupancy",
}


def test_solve_returns_display_units(client, example_config):
    r = client.post(
        "/v1/solve",
        headers=auth(),
        json={"config": example_config, "condition": WARMUP, "units": "ip"},
    )
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    assert res["mode"] == "warmup" and res["units"]["db"] == "°F"
    sat = next(s for s in res["states"] if s["key"] == "after:sf1")
    assert sat["db"] == pytest.approx(90.0, abs=0.02)
    assert any(f["component"] == "mix1.ra" for f in res["failures"])


def test_solve_si(client, example_config):
    r = client.post(
        "/v1/solve",
        headers=auth(),
        json={"config": example_config, "condition": WARMUP, "units": "si"},
    )
    sat = next(s for s in r.json()["result"]["states"] if s["key"] == "after:sf1")
    assert sat["db"] == pytest.approx(32.22, abs=0.02)


def test_scenario_runs_all_conditions(client, example_config):
    r = client.post(
        "/v1/scenario",
        headers=auth(),
        json={"config": example_config, "conditions": [SUMMER, WARMUP]},
    )
    assert r.status_code == 200
    by_id = {x["condition_id"]: x for x in r.json()["results"]}
    assert by_id["summer_design"]["mode"] is None  # §6.1 has no occupied mode
    assert by_id["winter_warmup"]["mode"] == "warmup"
    assert r.json()["p"] == pytest.approx(101204, abs=2)  # 33 ft standard atmosphere


def test_checks(client, example_config):
    bad = copy.deepcopy(example_config)
    del bad["components"]["phc1"]
    bad["lanes"]["supply"].remove("phc1")
    r = client.post("/v1/checks", headers=auth(), json={"config": bad})
    msgs = [f["message"] for f in r.json()["failures"]]
    assert "Loop sat_heating names phc1.valve, but there is no component phc1." in msgs


def test_invalid_config_is_one_plain_sentence(client, example_config):
    bad = copy.deepcopy(example_config)
    bad["airflows"]["supply"]["unit"] = "gpm"
    r = client.post("/v1/checks", headers=auth(), json={"config": bad})
    assert r.status_code == 422
    msg = r.json()["message"]
    assert "airflows" in msg and "supply" in msg and "unit" in msg
    assert "\n" not in msg


def test_chart_grid(client):
    r = client.get(
        "/v1/chart-grid", params={"p": 101325, "units": "ip"}, headers=auth()
    )
    g = r.json()
    assert g["units"] == "ip" and any(ln["kind"] == "saturation" for ln in g["lines"])


def test_schema_endpoint(client):
    s = client.get("/v1/schema", headers=auth()).json()
    assert "lanes" in s["properties"]
