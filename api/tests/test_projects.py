"""M3-2: save and load your own projects, units and versions."""

from .conftest import auth


def make_project(client, name="Hospital Wing B", user="user_a"):
    r = client.post("/v1/projects", headers=auth(user), json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_list_rename_delete(client):
    p = make_project(client)
    assert [x["name"] for x in client.get("/v1/projects", headers=auth()).json()] == [
        "Hospital Wing B"
    ]
    r = client.patch(f"/v1/projects/{p['id']}", headers=auth(), json={"name": "Wing B"})
    assert r.json()["name"] == "Wing B"
    assert client.delete(f"/v1/projects/{p['id']}", headers=auth()).status_code == 204
    assert client.get("/v1/projects", headers=auth()).json() == []


def test_unit_round_trip_and_versions(client, example_config):
    p = make_project(client)
    r = client.post(
        f"/v1/projects/{p['id']}/units",
        headers=auth(),
        json={"name": "AHU-1", "config": example_config},
    )
    assert r.status_code == 201, r.text
    unit = r.json()
    assert unit["version"] == 1
    got = client.get(f"/v1/units/{unit['id']}", headers=auth()).json()
    assert got["config"] == example_config  # exactly what was saved
    changed = dict(example_config, unit={**example_config["unit"], "name": "AHU-1A"})
    r = client.post(
        f"/v1/units/{unit['id']}/versions", headers=auth(), json={"config": changed}
    )
    assert r.json()["version"] == 2
    assert (
        client.get(f"/v1/units/{unit['id']}", headers=auth()).json()["config"]["unit"][
            "name"
        ]
        == "AHU-1A"
    )
    versions = client.get(f"/v1/units/{unit['id']}/versions", headers=auth()).json()
    assert [v["version"] for v in versions] == [2, 1]
    detail = client.get(f"/v1/projects/{p['id']}", headers=auth()).json()
    assert detail["units"][0]["name"] == "AHU-1" and detail["units"][0]["version"] == 2


def test_blank_unit_is_a_valid_config(client):
    p = make_project(client)
    unit = client.post(
        f"/v1/projects/{p['id']}/units", headers=auth(), json={"name": "New AHU"}
    ).json()
    cfg = client.get(f"/v1/units/{unit['id']}", headers=auth()).json()["config"]
    assert cfg["lanes"] == {"supply": ["oa"], "return": ["ra"]}
    assert (
        client.post("/v1/checks", headers=auth(), json={"config": cfg}).status_code
        == 200
    )


def test_other_users_cannot_see_or_touch(client, example_config):
    p = make_project(client, user="user_a")
    unit = client.post(
        f"/v1/projects/{p['id']}/units",
        headers=auth("user_a"),
        json={"name": "AHU-1", "config": example_config},
    ).json()
    assert client.get("/v1/projects", headers=auth("user_b")).json() == []
    assert (
        client.get(f"/v1/projects/{p['id']}", headers=auth("user_b")).status_code == 404
    )
    assert (
        client.patch(
            f"/v1/projects/{p['id']}", headers=auth("user_b"), json={"name": "x"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/v1/projects/{p['id']}", headers=auth("user_b")).status_code
        == 404
    )
    assert (
        client.get(f"/v1/units/{unit['id']}", headers=auth("user_b")).status_code == 404
    )
    assert (
        client.post(
            f"/v1/units/{unit['id']}/versions",
            headers=auth("user_b"),
            json={"config": example_config},
        ).status_code
        == 404
    )
