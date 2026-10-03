"""Mixing box: outdoor, return, mixed and relief air (spec §5.4).

Actuator `oa_fraction` (0–1) is the outdoor share of mixed airflow by
VOLUME at the damper conditions: Q_oa / (Q_oa + Q_recirc), as an engineer
reads "3,000 of 10,000 cfm". It is converted to a dry-air mass fraction
before mixing (F-7).
"""

from ahuverify import schema
from ahuverify.components import (
    Check,
    ComponentResult,
    at_least,
    at_most,
    closure_residuals,
)
from ahuverify.state import AirStream, condense_to_saturation


def oa_mass_fraction(oa_fraction: float, v_oa: float, v_ra: float) -> float:
    """Dry-air mass fraction of outdoor air from its volumetric fraction.

    Volume per kg dry air differs between the two streams, so
    x = (f / v_oa) / (f / v_oa + (1 − f) / v_ra)   (mass basis, spec §4 rule 4).
    """
    oa = oa_fraction / v_oa
    ra = (1.0 - oa_fraction) / v_ra
    return oa / (oa + ra)


def mix_airstreams(streams: list[AirStream], p: float) -> tuple[AirStream, float]:
    """Adiabatic mixing on a dry-air mass basis.

    h_mix = Σ m·h / Σ m and W_mix = Σ m·W / Σ m (ASHRAE Fundamentals 2017,
    Ch. 1, adiabatic mixing of two moist airstreams). If the mix lands beyond
    saturation, the excess condenses as fog at constant enthalpy.
    Returns (mixed stream, condensate in kg/s).
    """
    m = sum(s.m_da for s in streams)
    h = sum(s.m_da * s.state.h for s in streams) / m
    w = sum(s.m_da * s.state.w for s in streams) / m
    state, condensate = condense_to_saturation(h, w, p)
    return AirStream(state, m), condensate * m


def face_velocity(m_da: float, v: float, area: float) -> float:
    """Face velocity (m/s) = volumetric flow / free area = m_da · v / A."""
    return m_da * v / area


class MixingBox:
    type = "mixing_box"

    def __init__(self, name: str, cfg: schema.MixingBox, *, min_oa_flow: float):
        self.name = name
        self.cfg = cfg
        self.min_oa_flow = min_oa_flow  # m³/s at the OA damper

    def solve(
        self,
        inlets: dict[str, AirStream],
        actuators: dict[str, float],
        p: float,
        *,
        m_supply: float,
        m_return: float,
    ) -> ComponentResult:
        """Mix OA and recirculated air to deliver m_supply (kg/s dry air).

        The OA inlet supplies whatever the damper draws (its m_da is ignored).
        Recirculated = m_supply − m_oa. Relief = return − recirculated. If the
        return flow cannot cover the recirculation (OA below the
        pressurization bias), return rises to match, relief is zero and the
        `pressurization_bias` check fails.
        """
        f = actuators["oa_fraction"]
        if not 0.0 <= f <= 1.0:
            raise ValueError(f"{self.name}.oa_fraction {f} must be between 0 and 1.")
        oa, ra = inlets["oa"].state, inlets["ra"].state
        m_oa = oa_mass_fraction(f, oa.v, ra.v) * m_supply
        m_recirc = m_supply - m_oa
        m_ra = max(m_return, m_recirc)
        m_relief = m_ra - m_recirc

        mixed, condensate = mix_airstreams(
            [AirStream(oa, m_oa), AirStream(ra, m_recirc)], p
        )
        relief = AirStream(ra, m_relief)
        return ComponentResult(
            outlets={"mixed": mixed, "relief": relief},
            loads={
                "m_oa": m_oa,
                "m_ra": m_ra,
                "m_relief": m_relief,
                "condensate": condensate,
            },
            checks=self._checks(
                oa, ra, mixed.state, m_oa, m_recirc, m_relief, m_return
            ),
            residuals=closure_residuals(
                [AirStream(oa, m_oa), AirStream(ra, m_ra)],
                [mixed, relief],
                water_removed=condensate,
            ),
        )

    def _checks(self, oa, ra, mixed, m_oa, m_recirc, m_relief, m_return) -> list[Check]:
        d = self.cfg.dampers
        checks = [
            at_most(
                f"face_velocity_{port}",
                face_velocity(m, s.v, dmp.free_area.si),
                dmp.max_velocity.si,
                "m/s",
            )
            for port, m, s, dmp in (
                ("oa", m_oa, oa, d.oa),
                ("ra", m_recirc, ra, d.ra),
                ("relief", m_relief, ra, d.relief),
            )
        ]
        checks.append(at_least("min_oa", m_oa * oa.v, self.min_oa_flow, "m3/s"))
        checks.append(at_least("pressurization_bias", m_return, m_recirc, "kg/s"))
        if self.cfg.freeze_threshold is not None:
            checks.append(
                at_least(
                    "mixed_air_freeze", mixed.t_db, self.cfg.freeze_threshold.si, "C"
                )
            )
        return checks
