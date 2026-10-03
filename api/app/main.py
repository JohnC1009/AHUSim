"""FastAPI app (spec §7). Run: cd api && uvicorn app.main:app --reload"""

from ahuverify.lanes import ConfigError
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jwt import PyJWKClient
from starlette.exceptions import HTTPException

from app.auth import AuthError
from app.db import Database
from app.routes import compute, projects
from app.settings import Settings, load_settings


def _plain(err: dict) -> str:
    """One validation error as a plain sentence: where, then what."""
    loc = [str(x) for x in err.get("loc", ()) if x not in ("body",)]
    where = " → ".join(loc) if loc else "request"
    return f"{where}: {err.get('msg', 'invalid value')}."


def create_app(settings: Settings | None = None, *, jwks_client=None) -> FastAPI:
    settings = (settings or load_settings()).validate()
    app = FastAPI(title="AHU Sequence Verifier API", version="0.3.0")
    app.state.settings = settings
    app.state.db = Database(settings.database_url)
    app.state.jwks_client = jwks_client or (
        PyJWKClient(settings.clerk_jwks_url) if settings.auth_mode == "clerk" else None
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AuthError)
    async def auth_error(_: Request, e: AuthError):
        return JSONResponse({"message": e.message}, status_code=401)

    @app.exception_handler(ConfigError)
    async def config_error(_: Request, e: ConfigError):
        return JSONResponse({"message": str(e)}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError):
        errors = e.errors()
        return JSONResponse(
            {
                "message": _plain(errors[0]) if errors else "Invalid request.",
                "errors": [_plain(x) for x in errors],
            },
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException):
        return JSONResponse({"message": str(e.detail)}, status_code=e.status_code)

    app.include_router(compute.router)
    app.include_router(projects.router)
    return app


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the app lazily so importing this module
    # (tests, tools) never needs production environment variables.
    if name == "app":
        return create_app()
    raise AttributeError(name)
