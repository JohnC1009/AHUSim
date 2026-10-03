"""Projects, units and unit versions — the signed-in user's own (M3-2).

Access is owner-only for now; organizations and roles arrive in M5 with
require(). Another user's project answers 404, not 403, so ids do not leak.
"""

from ahuverify.schema import UnitConfig
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user, get_session
from app.models import Project, Unit, UnitVersion, User

router = APIRouter(prefix="/v1")


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config: UnitConfig | None = None  # blank unit when omitted


class VersionIn(BaseModel):
    config: UnitConfig


def blank_config(name: str) -> dict:
    """A valid, empty unit: boundaries only, editable defaults for airflows."""
    return {
        "schema_version": "0.2",
        "unit": {
            "name": name,
            "altitude": {"value": 0, "unit": "ft"},
            "pressure_override": None,
        },
        "airflows": {
            "supply": {"value": 10000, "unit": "cfm", "at": "supply_fan_discharge"},
            "min_oa": {"value": 2000, "unit": "cfm", "at": "oa_damper"},
            "pressurization_bias": {
                "value": 0,
                "unit": "cfm",
                "sign": "supply_minus_return",
            },
        },
        "lanes": {"supply": ["oa"], "return": ["ra"]},
        "components": {},
        "sensors": [],
        "sequence": {"modes": [], "loops": {}},
        "conditions": {"weather_file": None, "scenarios": [], "operating": []},
    }


def _split(cfg: dict) -> tuple[dict, dict, dict]:
    rest = {k: v for k, v in cfg.items() if k not in ("sequence", "conditions")}
    return rest, cfg["sequence"], cfg["conditions"]


def _dump(cfg: UnitConfig) -> dict:
    return cfg.model_dump(mode="json", by_alias=True, exclude_unset=True)


def _own_project(db: Session, user: User, project_id: str) -> Project:
    p = db.get(Project, project_id)
    if p is None or p.owner_id != user.id:
        raise HTTPException(404, "No such project.")
    return p


def _own_unit(db: Session, user: User, unit_id: str) -> Unit:
    u = db.get(Unit, unit_id)
    if u is None or u.project.owner_id != user.id:
        raise HTTPException(404, "No such unit.")
    return u


def _add_version(db: Session, unit: Unit, user: User, cfg: dict) -> UnitVersion:
    rest, seq, cond = _split(cfg)
    n = (unit.versions[0].version + 1) if unit.versions else 1
    v = UnitVersion(
        unit=unit,
        version=n,
        config=rest,
        sequence=seq,
        conditions=cond,
        created_by=user.id,
    )
    db.add(v)
    return v


def _project_out(p: Project) -> dict:
    return {"id": p.id, "name": p.name, "updated_at": p.updated_at.isoformat()}


@router.get("/projects")
def list_projects(
    user: User = Depends(current_user), db: Session = Depends(get_session)
) -> list[dict]:
    rows = db.scalars(
        select(Project)
        .where(Project.owner_id == user.id)
        .order_by(Project.updated_at.desc())
    )
    return [_project_out(p) for p in rows]


@router.post("/projects", status_code=201)
def create_project(
    body: ProjectIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    p = Project(name=body.name, owner_id=user.id)
    db.add(p)
    db.commit()
    return _project_out(p)


@router.get("/projects/{project_id}")
def get_project(
    project_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    p = _own_project(db, user, project_id)
    units = [
        {
            "id": u.id,
            "name": u.name,
            "version": u.versions[0].version if u.versions else 0,
        }
        for u in p.units
    ]
    return _project_out(p) | {"units": units}


@router.patch("/projects/{project_id}")
def rename_project(
    project_id: str,
    body: ProjectIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    p = _own_project(db, user, project_id)
    p.name = body.name
    db.commit()
    return _project_out(p)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(
    project_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
):
    db.delete(_own_project(db, user, project_id))
    db.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/units", status_code=201)
def create_unit(
    project_id: str,
    body: UnitIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    p = _own_project(db, user, project_id)
    unit = Unit(project=p, name=body.name)
    db.add(unit)
    cfg = _dump(body.config) if body.config else blank_config(body.name)
    v = _add_version(db, unit, user, cfg)
    db.commit()
    return {"id": unit.id, "name": unit.name, "project_id": p.id, "version": v.version}


@router.get("/units/{unit_id}")
def get_unit(
    unit_id: str, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> dict:
    u = _own_unit(db, user, unit_id)
    latest = u.versions[0]
    return {
        "id": u.id,
        "name": u.name,
        "project_id": u.project_id,
        "version": latest.version,
        "config": latest.unit_config(),
    }


@router.post("/units/{unit_id}/versions", status_code=201)
def save_version(
    unit_id: str,
    body: VersionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_session),
) -> dict:
    u = _own_unit(db, user, unit_id)
    v = _add_version(db, u, user, _dump(body.config))
    db.commit()
    return {"id": u.id, "version": v.version}


@router.get("/units/{unit_id}/versions")
def list_versions(
    unit_id: str, user: User = Depends(current_user), db: Session = Depends(get_session)
) -> list[dict]:
    u = _own_unit(db, user, unit_id)
    return [
        {"version": v.version, "created_at": v.created_at.isoformat()}
        for v in u.versions
    ]
