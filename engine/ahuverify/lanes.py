"""Compile a unit config into engine components and lane solve order (spec §5.5).

Lanes are ordered lists: the supply lane starts at "oa", the return lane at
"ra". Cross-lane components appear as "<id>.supply" in the supply lane and
"<id>.exhaust" in the return lane; the mixing box appears by bare id in both.
Problems raise ConfigError with a plain-English message.
"""

from dataclasses import dataclass

from ahuverify import schema
from ahuverify.components.adiabatic_humidifier import AdiabaticHumidifier
from ahuverify.components.cooling_coil import (
    CoolingCoilDesignMode,
    CoolingCoilMeasuredMode,
)
from ahuverify.components.desiccant_wheel import DesiccantWheel
from ahuverify.components.electric_heater import ElectricHeater
from ahuverify.components.energy_wheel import EnergyWheel
from ahuverify.components.fan import Fan
from ahuverify.components.filter import Filter
from ahuverify.components.heating_coil import HeatingCoilHw
from ahuverify.components.mixing_box import MixingBox
from ahuverify.components.sensible_hx import SensibleHx
from ahuverify.components.space import Space
from ahuverify.components.steam_humidifier import SteamHumidifier
from ahuverify.psychro import si

CROSS_LANE = {"energy_wheel", "plate_hx", "runaround", "heat_pipe", "desiccant_wheel"}
NAMED_LOCATIONS = {"supply_fan_discharge"}


class ConfigError(ValueError):
    """A configuration the engine cannot solve, explained in one sentence."""


@dataclass(frozen=True)
class Slot:
    token: str  # as written in the lane, e.g. "erw1.supply"
    comp: str  # component id
    port: str | None  # "supply" / "exhaust" for cross-lane components


@dataclass
class CompiledUnit:
    cfg: schema.UnitConfig
    p: float  # Pa
    components: dict[str, object]
    supply: list[Slot]
    return_: list[Slot]
    mixing_box: str | None
    space: str | None
    supply_flow_location: str  # state key whose v converts supply cfm to mass


def site_pressure(unit: schema.UnitInfo) -> float:
    """Barometric pressure, Pa: the override if given, else the standard atmosphere
    at the stated altitude (ASHRAE Fundamentals 2017 Ch. 1 Eq. 3, via PsychroLib)."""
    if unit.pressure_override is not None:
        return unit.pressure_override.si
    return si.GetStandardAtmPressure(unit.altitude.si)


def _parse_lane(name: str, tokens: list[str], start: str, comps: dict) -> list[Slot]:
    if not tokens or tokens[0] != start:
        raise ConfigError(f'The {name} lane must start at "{start}".')
    slots = [Slot(start, start, None)]
    for token in tokens[1:]:
        comp, _, port = token.partition(".")
        if comp not in comps:
            raise ConfigError(
                f'The {name} lane names "{token}", but there is no component {comp}.'
            )
        kind = comps[comp].type
        want = {"supply": "supply", "return": "exhaust"}[name]
        if kind in CROSS_LANE and port != want:
            raise ConfigError(
                f'{comp} spans both lanes: write it as "{comp}.{want}" in the {name} lane.'
            )
        if kind not in CROSS_LANE and port:
            raise ConfigError(
                f'{comp} is a single-lane component: write it as "{comp}", not "{token}".'
            )
        slots.append(Slot(token, comp, port or None))
    return slots


def _check_placement(
    cfg: schema.UnitConfig, supply: list[Slot], ret: list[Slot]
) -> None:
    comps = cfg.components
    boxes = [c for c, m in comps.items() if m.type == "mixing_box"]
    if len(boxes) > 1:
        raise ConfigError(
            f"A unit can have only one mixing box; found {len(boxes)}: {', '.join(boxes)}."
        )
    seen: dict[str, list[str]] = {}
    for lane, slots in (("supply", supply), ("return", ret)):
        for s in slots[1:]:
            seen.setdefault(s.comp, []).append(lane)
    for comp, model in comps.items():
        lanes = seen.get(comp, [])
        if model.type == "space":
            if lanes:
                raise ConfigError(
                    f"Space {comp} sits between the lanes; do not list it in a lane."
                )
            continue
        if not lanes:
            raise ConfigError(f"Component {comp} is not placed in any lane.")
        both = model.type in CROSS_LANE or model.type == "mixing_box"
        if both and sorted(lanes) != ["return", "supply"]:
            raise ConfigError(
                f"{comp} must appear once in the supply lane and once in the return lane."
            )
        if not both and len(lanes) > 1:
            raise ConfigError(f"Component {comp} appears more than once in the lanes.")
    if len([c for c, m in comps.items() if m.type == "space"]) > 1:
        raise ConfigError("A unit can have only one space node.")
    if len(supply) < 2 or comps[supply[-1].comp].type != "fan":
        raise ConfigError("The supply lane must end at a fan.")
    if len(ret) > 1 and comps[ret[-1].comp].type not in ("fan", "mixing_box"):
        raise ConfigError(
            "The return lane must end at a fan or at the mixing box relief."
        )


def _filter_dp_per_fan(comps: dict, lanes: list[list[Slot]]) -> dict[str, float]:
    """Each filter's ΔP is added to the nearest fan downstream in its lane
    (or, if none, the nearest upstream), because that fan overcomes it."""
    dp: dict[str, float] = {}
    for slots in lanes:
        for i, s in enumerate(slots):
            if comps.get(s.comp) is None or comps[s.comp].type != "filter":
                continue
            fans = [t.comp for t in slots[i + 1 :] if comps[t.comp].type == "fan"]
            fans = fans or [
                t.comp for t in reversed(slots[1:i]) if comps[t.comp].type == "fan"
            ]
            if not fans:
                raise ConfigError(
                    f"Filter {s.comp} has no fan in its lane to overcome its pressure drop."
                )
            dp[fans[0]] = dp.get(fans[0], 0.0) + comps[s.comp].dp_dirty.si
    return dp


def _build(
    name: str, model, p: float, cfg: schema.UnitConfig, fan_dp: dict[str, float]
):
    t = model.type
    if t == "mixing_box":
        return MixingBox(name, model, min_oa_flow=cfg.airflows.min_oa.si)
    if t == "cooling_coil_chw":
        return (
            CoolingCoilDesignMode(name, model, p=p)
            if model.mode == "design"
            else CoolingCoilMeasuredMode(name, model)
        )
    if t == "heating_coil_hw":
        return HeatingCoilHw(name, model, p=p)
    if t == "fan":
        return Fan(name, model, filter_dp=fan_dp.get(name, 0.0))
    if t in ("plate_hx", "runaround", "heat_pipe"):
        return SensibleHx(name, model)
    simple = {
        "filter": Filter,
        "electric_heater": ElectricHeater,
        "energy_wheel": EnergyWheel,
        "desiccant_wheel": DesiccantWheel,
        "steam_humidifier": SteamHumidifier,
        "adiabatic_humidifier": AdiabaticHumidifier,
        "space": Space,
    }
    return simple[t](name, model)


def _supply_flow_location(cfg: schema.UnitConfig, supply: list[Slot]) -> str:
    at = cfg.airflows.supply.at
    if at == "supply_fan_discharge":
        return f"after:{supply[-1].token}"
    if at.startswith("after:") and at[len("after:") :] in {s.token for s in supply[1:]}:
        return at
    raise ConfigError(
        f'Supply airflow location "{at}" is not supply_fan_discharge or after:<a supply-lane item>.'
    )


def compile_unit(cfg: schema.UnitConfig) -> CompiledUnit:
    comps = cfg.components
    supply = _parse_lane("supply", cfg.lanes.supply, "oa", comps)
    ret = (
        _parse_lane("return", cfg.lanes.return_, "ra", comps)
        if cfg.lanes.return_
        else [Slot("ra", "ra", None)]
    )
    _check_placement(cfg, supply, ret)
    p = site_pressure(cfg.unit)
    fan_dp = _filter_dp_per_fan(comps, [supply, ret])
    return CompiledUnit(
        cfg=cfg,
        p=p,
        components={name: _build(name, m, p, cfg, fan_dp) for name, m in comps.items()},
        supply=supply,
        return_=ret,
        mixing_box=next((c for c, m in comps.items() if m.type == "mixing_box"), None),
        space=next((c for c, m in comps.items() if m.type == "space"), None),
        supply_flow_location=_supply_flow_location(cfg, supply),
    )
