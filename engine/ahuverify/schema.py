"""Pydantic models for the unit configuration (the config contract, spec §6).

Every user-entered quantity is stored as {"value": ..., "unit": ...} exactly as
entered. Conversion to SI happens later, in `units.py` (M1-1), not here.

Scope (M0-3): only what the §6.1 example uses. Cross-references (lane ids,
sensor ids, actuator refs) are NOT checked here; that is compile-time
validation (§5.5) and static checks (§5.8).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.2"

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class _Model(BaseModel):
    # Unknown keys are rejected so a typo in a config fails loudly.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- Quantities: one class per physical dimension, units listed per class ---


class Temperature(_Model):
    value: float
    unit: Literal["F", "C"]


class Enthalpy(_Model):
    value: float
    unit: Literal["Btu/lb", "kJ/kg"]


class Length(_Model):
    value: float
    unit: Literal["ft", "m"]


class Area(_Model):
    value: float
    unit: Literal["ft2", "m2"]


class Velocity(_Model):
    value: float
    unit: Literal["fpm", "m/s"]


class Pressure(_Model):
    value: float
    unit: Literal["Pa", "in_wc"]


class Airflow(_Model):
    value: float
    unit: Literal["cfm", "m3/s", "L/s", "m3/h"]


class AirflowAt(Airflow):
    """A volumetric airflow and the location whose air state converts it to mass."""

    at: str


class PressurizationBias(Airflow):
    sign: Literal["supply_minus_return", "return_minus_supply"]


# --- Unit and airflows ---


class UnitInfo(_Model):
    name: str
    altitude: Length
    pressure_override: Pressure | None = None


class Airflows(_Model):
    supply: AirflowAt
    min_oa: AirflowAt
    pressurization_bias: PressurizationBias


class Lanes(_Model):
    supply: list[str]
    return_: list[str] = Field(alias="return")


# --- Components (discriminated on "type") ---


class Damper(_Model):
    free_area: Area
    max_velocity: Velocity


class MixingBoxDampers(_Model):
    oa: Damper
    ra: Damper
    relief: Damper


class MixingBox(_Model):
    type: Literal["mixing_box"]
    dampers: MixingBoxDampers


class CoolingCoilRating(_Model):
    eat_db: Temperature
    eat_wb: Temperature
    lat_db: Temperature
    lat_wb: Temperature
    airflow: Airflow
    chws: Temperature
    chwr: Temperature


class CoolingCoilChw(_Model):
    type: Literal["cooling_coil_chw"]
    mode: Literal["design"]
    face_area: Area
    rating: CoolingCoilRating


class EnergyWheel(_Model):
    type: Literal["energy_wheel"]
    eps_sens: Fraction
    eps_lat: Fraction
    purge: bool
    eatr: Annotated[float, Field(ge=0.0, le=0.05)]


Component = Annotated[
    MixingBox | CoolingCoilChw | EnergyWheel, Field(discriminator="type")
]


# --- Sensors ---


class Sensor(_Model):
    id: str
    type: Literal["temperature", "temperature_averaging"]
    at: str = Field(pattern=r"^after:\S+$")


# --- Structured conditions (spec §5.6) — data only, never eval'd ---

TEMPERATURE_VARS = {"oa_db", "oa_dp", "ra_db", "space_t"}
ENTHALPY_VARS = {"oa_h", "ra_h"}


class Comparison(_Model):
    var: Literal["oa_db", "oa_h", "oa_dp", "ra_db", "ra_h", "space_t", "schedule"]
    op: Literal["<", "<=", ">", ">=", "=="]
    value: str | Temperature | Enthalpy

    @model_validator(mode="after")
    def value_matches_var(self) -> Comparison:
        if self.var == "schedule":
            ok = isinstance(self.value, str)
            expected = "a schedule name (text)"
        elif self.var in TEMPERATURE_VARS:
            ok = isinstance(self.value, Temperature)
            expected = "a temperature in F or C"
        else:
            ok = isinstance(self.value, Enthalpy)
            expected = "an enthalpy in Btu/lb or kJ/kg"
        if not ok:
            raise ValueError(f"Condition on '{self.var}' needs {expected}.")
        return self


class AllOf(_Model):
    all: list[Condition] = Field(min_length=1)


class AnyOf(_Model):
    any: list[Condition] = Field(min_length=1)


class NotOf(_Model):
    not_: Condition = Field(alias="not")


Condition = AllOf | AnyOf | NotOf | Comparison


# --- Sequence ---


class Mode(_Model):
    id: str
    priority: int
    enter: Condition
    fixed: dict[str, Fraction] = {}
    loops: list[str] = []


class Stage(_Model):
    actuator: str
    action: Literal["direct", "reverse"]


class Loop(_Model):
    sensor: str
    setpoint: Temperature
    stages: list[Stage] = Field(min_length=1)


class Sequence(_Model):
    modes: list[Mode]
    loops: dict[str, Loop]


class Conditions(_Model):
    weather_file: str | None = None
    scenarios: list[str] = []


# --- Top level ---


class UnitConfig(_Model):
    schema_version: Literal["0.2"]
    unit: UnitInfo
    airflows: Airflows
    lanes: Lanes
    components: dict[str, Component]
    sensors: list[Sensor]
    sequence: Sequence
    conditions: Conditions


def export_json_schema() -> dict:
    """JSON Schema of `UnitConfig`, using the JSON key names ("return", "not")."""
    return UnitConfig.model_json_schema(by_alias=True)
