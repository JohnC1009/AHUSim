"""Pydantic models for the unit configuration (the config contract, spec §6).

Every user-entered quantity is stored as {"value": ..., "unit": ...} exactly as
entered, so a config round-trips unchanged. `quantity.si` gives the SI value
(conversion in `units.py`); engine code reads only `.si`.

Scope (M0-3): only what the §6.1 example uses. Cross-references (lane ids,
sensor ids, actuator refs) are NOT checked here; that is compile-time
validation (§5.5) and static checks (§5.8).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ahuverify import units

SCHEMA_VERSION = "0.2"

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]


class _Model(BaseModel):
    # Unknown keys are rejected so a typo in a config fails loudly.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --- Quantities: one class per physical dimension, units listed per class ---


class _Quantity(_Model):
    value: float
    unit: str

    @property
    def si(self) -> float:
        """Value in the engine's SI unit (°C, m, m², m/s, Pa, m³/s, kJ/kg, W, kg/s, 0–1)."""
        return units.to_si(self.value, self.unit)


class Temperature(_Quantity):
    value: float
    unit: Literal["F", "C"]


class Enthalpy(_Quantity):
    value: float
    unit: Literal["Btu/lb", "kJ/kg"]


class Length(_Quantity):
    value: float
    unit: Literal["ft", "m"]


class Area(_Quantity):
    value: float
    unit: Literal["ft2", "m2"]


class Velocity(_Quantity):
    value: float
    unit: Literal["fpm", "m/s"]


class Pressure(_Quantity):
    value: float
    unit: Literal["Pa", "in_wc"]


class Airflow(_Quantity):
    value: float
    unit: Literal["cfm", "m3/s", "L/s", "m3/h"]


class Power(_Quantity):
    value: float
    unit: Literal["W", "kW", "Btu/h", "MBH"]


class MassFlow(_Quantity):
    value: float
    unit: Literal["kg/s", "kg/h", "lb/h"]


class RelHum(_Quantity):
    value: Annotated[float, Field(ge=0.0, le=100.0)]
    unit: Literal["%"]


QUANTITY_TYPES = (
    Temperature,
    Enthalpy,
    Length,
    Area,
    Velocity,
    Pressure,
    Airflow,
    Power,
    MassFlow,
    RelHum,
)


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
    # Optional: mixed-air temperature below this fails the freeze check.
    freeze_threshold: Temperature | None = None


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
    # Optional: when absent the face-velocity check is skipped with a warning.
    max_face_velocity: Velocity | None = None


class EnergyWheel(_Model):
    type: Literal["energy_wheel"]
    eps_sens: Fraction
    eps_lat: Fraction
    purge: bool
    eatr: Annotated[float, Field(ge=0.0, le=0.05)]


class Filter(_Model):
    type: Literal["filter"]
    dp_clean: Pressure
    dp_dirty: Pressure


class Fan(_Model):
    """Supply, return or exhaust fan. Airflow is fixed per mode in v1."""

    type: Literal["fan"]
    design_airflow: Airflow  # at the fan inlet
    total_static: Pressure  # excluding filter banks; their ΔP is added
    eta_fan: Annotated[float, Field(gt=0.0, le=1.0)]
    eta_motor: Annotated[float, Field(gt=0.0, le=1.0)]
    motor_in_airstream: bool


class HeatingCoilRating(_Model):
    eat: Temperature
    lat: Temperature
    airflow: Airflow  # at entering air conditions
    ewt: Temperature
    lwt: Temperature


class HeatingCoilHw(_Model):
    """Hot-water coil (preheat or reheat)."""

    type: Literal["heating_coil_hw"]
    face_area: Area
    rating: HeatingCoilRating
    # Optional: when absent the face-velocity check is skipped with a warning.
    max_face_velocity: Velocity | None = None


class ElectricHeater(_Model):
    type: Literal["electric_heater"]
    power: Power
    # Number of equal stages; None = modulating (SCR).
    stages: Annotated[int, Field(ge=1)] | None = None


Component = Annotated[
    MixingBox
    | CoolingCoilChw
    | EnergyWheel
    | Filter
    | Fan
    | HeatingCoilHw
    | ElectricHeater,
    Field(discriminator="type"),
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
