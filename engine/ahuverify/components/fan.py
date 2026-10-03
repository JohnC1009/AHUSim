"""Fan: heat of compression and motor losses into the air (spec §5.4)."""

from ahuverify import schema
from ahuverify.components import ComponentResult, at_most, closure_residuals
from ahuverify.state import AirState, AirStream


def fan_enthalpy_rise(dp: float, v: float, efficiency: float) -> float:
    """Enthalpy rise of the air across a fan, kJ/kg dry air.

    All fan shaft work ends up as heat in the air: power = Q·ΔP / η, so per
    kg of dry air Δh = ΔP · v / η (ΔP in Pa, v in m³/kg dry air at the fan
    inlet). η is the fan efficiency, times the motor efficiency when the
    motor is in the airstream (its losses also go to the air). W is unchanged;
    T follows from h and W via PsychroLib. Equivalent to the spec §5.4 form
    ΔT = ΔP / (ρ·c_p·η) with moist-air c_p per kg dry air.
    """
    return dp * v / efficiency / 1000.0


class Fan:
    type = "fan"

    def __init__(self, name: str, cfg: schema.Fan, *, filter_dp: float = 0.0):
        self.name = name
        self.cfg = cfg
        self.dp = cfg.total_static.si + filter_dp  # Pa
        eta = cfg.eta_fan * (cfg.eta_motor if cfg.motor_in_airstream else 1.0)
        self.efficiency_to_air = eta

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        inlet = inlets["in"]
        s = inlet.state
        dh = fan_enthalpy_rise(self.dp, s.v, self.efficiency_to_air)
        out = AirStream(AirState.from_h_w(s.h + dh, s.w, p), inlet.m_da)
        heat_to_air = inlet.m_da * dh * 1000.0  # W
        shaft = inlet.m_da * s.v * self.dp / self.cfg.eta_fan  # W
        q_in = inlet.m_da * s.v  # m³/s at the fan inlet
        return ComponentResult(
            outlets={"out": out},
            loads={"q_air": heat_to_air, "power": shaft / self.cfg.eta_motor},
            checks=[at_most("airflow", q_in, self.cfg.design_airflow.si, "m3/s")],
            residuals=closure_residuals([inlet], [out], heat_added=heat_to_air),
        )
