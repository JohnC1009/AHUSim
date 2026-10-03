"""Configuration from environment variables (names listed in /.env.example)."""

import os
from dataclasses import dataclass


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    env: str = "development"  # development | test | production
    auth_mode: str = "clerk"  # clerk | dev
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""
    clerk_authorized_parties: tuple[str, ...] = ()
    database_url: str = "sqlite:///./ahuverify-dev.db"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)

    def validate(self) -> "Settings":
        if self.auth_mode not in ("clerk", "dev"):
            raise SettingsError(
                f"AUTH_MODE must be clerk or dev, not {self.auth_mode!r}."
            )
        if self.auth_mode == "dev" and self.env == "production":
            raise SettingsError(
                "AUTH_MODE=dev skips sign-in and is refused in production."
            )
        if (
            self.auth_mode == "clerk"
            and self.env != "test"
            and not (self.clerk_jwks_url and self.clerk_issuer)
        ):
            raise SettingsError(
                "AUTH_MODE=clerk needs CLERK_JWKS_URL and CLERK_ISSUER."
            )
        return self


def _list(name: str, default: str = "") -> tuple[str, ...]:
    return tuple(
        x.strip() for x in os.environ.get(name, default).split(",") if x.strip()
    )


def load_settings() -> Settings:
    return Settings(
        env=os.environ.get("ENV", "development"),
        auth_mode=os.environ.get("AUTH_MODE", "clerk"),
        clerk_jwks_url=os.environ.get("CLERK_JWKS_URL", ""),
        clerk_issuer=os.environ.get("CLERK_ISSUER", ""),
        clerk_authorized_parties=_list("CLERK_AUTHORIZED_PARTIES"),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./ahuverify-dev.db"),
        cors_origins=_list("CORS_ORIGINS", "http://localhost:5173"),
    ).validate()
