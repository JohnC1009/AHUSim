"""Every endpoint needs a valid Clerk session token (spec §7)."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.settings import Settings, SettingsError

from .conftest import auth, token

ENDPOINTS = [
    ("post", "/v1/solve"),
    ("post", "/v1/scenario"),
    ("post", "/v1/checks"),
    ("get", "/v1/chart-grid"),
    ("get", "/v1/schema"),
    ("get", "/v1/projects"),
]


@pytest.mark.parametrize("method, path", ENDPOINTS)
def test_no_token_is_401(client, method, path):
    r = getattr(client, method)(path)
    assert r.status_code == 401
    assert r.json()["message"]


@pytest.mark.parametrize(
    "bad",
    [
        token(exp_in=-60),
        token(issuer="https://evil.example"),
        token(azp="https://evil.example"),
        token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        "not-a-jwt",
    ],
)
def test_bad_tokens_are_401(client, bad):
    r = client.get("/v1/projects", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_valid_token_creates_user_and_passes(client):
    r = client.get("/v1/projects", headers=auth("user_new"))
    assert r.status_code == 200 and r.json() == []


def test_dev_auth_refused_in_production():
    with pytest.raises(SettingsError, match="production"):
        Settings(env="production", auth_mode="dev", database_url="sqlite://").validate()
