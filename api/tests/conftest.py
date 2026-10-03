"""Test app: real JWT verification against a locally generated RSA key, and a
fresh migrated SQLite database per test (TEST_DATABASE_URL overrides it, e.g.
a local Postgres)."""

import json
import os
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.db import migrate
from app.main import create_app
from app.settings import Settings

ISSUER = "https://clerk.test.example"
FIXTURE = (
    Path(__file__).parents[2] / "engine" / "tests" / "fixtures" / "example_6_1.json"
)
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class StaticJwks:
    """Stands in for PyJWKClient: always returns the test public key."""

    def get_signing_key_from_jwt(self, token):
        class K:
            key = KEY.public_key()

        return K()


def token(
    sub="user_a", *, exp_in=300, issuer=ISSUER, azp="http://localhost:5173", key=KEY
):
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "nbf": now - 5,
        "exp": now + exp_in,
        "azp": azp,
    }
    return jwt.encode(claims, key, algorithm="RS256")


def auth(sub="user_a"):
    return {"Authorization": f"Bearer {token(sub)}"}


@pytest.fixture
def settings(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    return Settings(
        env="test",
        auth_mode="clerk",
        clerk_jwks_url="unused-in-tests",
        clerk_issuer=ISSUER,
        clerk_authorized_parties=("http://localhost:5173",),
        database_url=url,
    )


@pytest.fixture
def client(settings):
    migrate(settings.database_url, fresh=True)
    app = create_app(settings, jwks_client=StaticJwks())
    with TestClient(app) as c:
        yield c


@pytest.fixture
def example_config():
    return json.loads(FIXTURE.read_text())
