"""Moist-air state and airstream (spec §5.1). SI units, properties from PsychroLib.

Units: t_db, t_dp, t_wb °C; w kg/kg dry air; p Pa; h kJ/kg dry air;
v m³/kg dry air; rh 0–1.
"""

from dataclasses import dataclass, field

from ahuverify._numeric import bisect
from ahuverify.psychro import si

# Relative tolerance on "at or below saturation" (PsychroLib round-off).
_SAT_TOL = 1e-9


@dataclass(frozen=True)
class AirState:
    """A moist-air state. Derived properties are computed once, on creation."""

    t_db: float
    w: float
    p: float
    h: float = field(init=False)
    v: float = field(init=False)
    rh: float = field(init=False)
    t_dp: float = field(init=False)
    t_wb: float = field(init=False)

    def __post_init__(self):
        if self.w < 0:
            raise ValueError(f"Humidity ratio {self.w} kg/kg is negative.")
        w_sat = si.GetSatHumRatio(self.t_db, self.p)
        if self.w > w_sat * (1 + _SAT_TOL):
            raise ValueError(
                f"State {self.t_db:.2f} °C with W = {self.w * 1000:.3f} g/kg is supersaturated "
                f"(saturation is {w_sat * 1000:.3f} g/kg); use condense_to_saturation()."
            )
        w = min(self.w, w_sat)
        set_ = object.__setattr__
        set_(self, "w", w)
        set_(self, "h", si.GetMoistAirEnthalpy(self.t_db, w) / 1000.0)  # J/kg -> kJ/kg
        set_(self, "v", si.GetMoistAirVolume(self.t_db, w, self.p))
        set_(self, "rh", min(si.GetRelHumFromHumRatio(self.t_db, w, self.p), 1.0))
        set_(
            self,
            "t_dp",
            min(si.GetTDewPointFromHumRatio(self.t_db, w, self.p), self.t_db),
        )
        set_(
            self,
            "t_wb",
            min(si.GetTWetBulbFromHumRatio(self.t_db, w, self.p), self.t_db),
        )

    @classmethod
    def from_db_w(cls, t_db: float, w: float, p: float) -> "AirState":
        return cls(t_db, w, p)

    @classmethod
    def from_db_rh(cls, t_db: float, rh: float, p: float) -> "AirState":
        if not 0.0 <= rh <= 1.0:
            raise ValueError(f"Relative humidity {rh} must be between 0 and 1.")
        return cls(t_db, si.GetHumRatioFromRelHum(t_db, rh, p), p)

    @classmethod
    def from_db_wb(cls, t_db: float, t_wb: float, p: float) -> "AirState":
        return cls(t_db, si.GetHumRatioFromTWetBulb(t_db, t_wb, p), p)

    @classmethod
    def from_db_dp(cls, t_db: float, t_dp: float, p: float) -> "AirState":
        return cls(t_db, si.GetHumRatioFromTDewPoint(t_dp, p), p)

    @classmethod
    def from_h_w(cls, h: float, w: float, p: float) -> "AirState":
        """State from enthalpy (kJ/kg) and humidity ratio (ASHRAE F 2017 Ch. 1 Eq. 30)."""
        return cls(si.GetTDryBulbFromEnthalpyAndHumRatio(h * 1000.0, w), w, p)


@dataclass(frozen=True)
class AirStream:
    """An air state plus its dry-air mass flow m_da (kg/s)."""

    state: AirState
    m_da: float


def saturation_enthalpy(t_db: float, p: float) -> float:
    """Enthalpy of saturated air at t_db, kJ/kg (PsychroLib, ASHRAE F 2017 Ch. 1)."""
    return si.GetSatAirEnthalpy(t_db, p) / 1000.0


def condense_to_saturation(h: float, w: float, p: float) -> tuple[AirState, float]:
    """Air with enthalpy h and humidity ratio w, capped at saturation.

    If (h, w) lies beyond the saturation curve, the excess water condenses
    (fog, or frost below 0 °C). The air ends saturated at the same enthalpy:
    find T where h_sat(T) = h, then condensate = w − W_sat(T). The released
    latent heat warms the air, so T ends above the supersaturated point. The condensate
    is taken to leave with zero enthalpy, so the air keeps all of the energy
    (adiabatic saturation; the liquid's own enthalpy, ~4.2 kJ/kg per K per kg
    of water, is neglected — under 0.1 % of the stream energy).

    Returns (state, condensate in kg/kg dry air). Condensate is 0.0 when the
    air was not supersaturated.
    """
    t = si.GetTDryBulbFromEnthalpyAndHumRatio(h * 1000.0, w)
    w_sat = si.GetSatHumRatio(t, p)
    if w <= w_sat * (1 + _SAT_TOL):
        return AirState(t, w, p), 0.0
    # h_sat(t) < h here, and h_sat rises steeply with T, so the root is in (t, t + 60).
    t_sat = bisect(lambda x: saturation_enthalpy(x, p) - h, t, t + 60.0, tol=1e-6)
    w_new = si.GetSatHumRatio(t_sat, p)
    return AirState(t_sat, w_new, p), w - w_new
