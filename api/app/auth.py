"""Clerk session-token verification (spec §7: every endpoint, checked server-side).

A Clerk session token is an RS256 JWT. It is accepted only if its signature
matches a key in Clerk's JWKS, it is unexpired, its issuer is our Clerk
instance, and (when configured) its `azp` is one of our web origins.
AUTH_MODE=dev skips all this for local work and is refused in production.
"""

from dataclasses import dataclass

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User

DEV_USER = "dev_local_user"


class AuthError(Exception):
    def __init__(self, message: str):
        self.message = message


@dataclass(frozen=True)
class Principal:
    clerk_id: str


def verify_session_token(token: str, settings, jwks_client) -> Principal:
    try:
        key = jwks_client.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
            leeway=5,
        )
    except jwt.PyJWTError as e:
        raise AuthError(
            f"Your sign-in could not be verified ({e}). Please sign in again."
        ) from None
    azp = claims.get("azp")
    if (
        settings.clerk_authorized_parties
        and azp not in settings.clerk_authorized_parties
    ):
        raise AuthError("This sign-in was issued for a different website.")
    return Principal(claims["sub"])


def principal(request: Request) -> Principal:
    s = request.app.state.settings
    if s.auth_mode == "dev":
        return Principal(DEV_USER)
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise AuthError("Please sign in: this request has no session token.")
    return verify_session_token(header[7:].strip(), s, request.app.state.jwks_client)


def get_session(request: Request):
    yield from request.app.state.db.session()


def current_user(
    p: Principal = Depends(principal), db: Session = Depends(get_session)
) -> User:
    """The signed-in user's row, created on first sight of a new Clerk id."""
    user = db.scalar(select(User).where(User.clerk_id == p.clerk_id))
    if user is None:
        user = User(clerk_id=p.clerk_id)
        db.add(user)
        db.commit()
    return user
