"""Psychrometric chart grid in display units (spec §8.3: computed by the API).

Lines: saturation, RH 10–90 %, dry bulb, humidity ratio, enthalpy, wet bulb.
I-P lines come from PsychroLib in I-P mode, SI lines from SI mode.
"""

from ahuverify.psychro import ip, si

_RANGES = {
    # x: dry bulb, y: humidity ratio (display units), grid steps
    "ip": {
        "x": (30.0, 110.0, 10.0, "Dry bulb (°F)"),
        "y": (0.0, 160.0, 20.0, "W (gr/lb)"),
        "w_per_display": 1 / 7000.0,
        "h_step": 5.0,
        "h_range": (10, 55),
        "wb_step": 10.0,
        "wb_range": (40, 90),
        "p_scale": 1 / 6894.757293168,
    },  # Pa -> psi
    "si": {
        "x": (-1.0, 43.0, 5.0, "Dry bulb (°C)"),
        "y": (0.0, 23.0, 2.0, "W (g/kg)"),
        "w_per_display": 1 / 1000.0,
        "h_step": 10.0,
        "h_range": (10, 130),
        "wb_step": 5.0,
        "wb_range": (5, 30),
        "p_scale": 1.0,
    },
}


def _frange(a: float, b: float, step: float) -> list[float]:
    n = round((b - a) / step)
    return [a + k * step for k in range(n + 1)]


def chart_grid(p_pa: float, system: str) -> dict:
    """Chart lines as [x, y] points in display units for site pressure p (Pa)."""
    r = _RANGES[system]
    lib = ip if system == "ip" else si
    p = p_pa * r["p_scale"]
    (x0, x1, dx, xlabel), (y0, y1, dy, ylabel) = r["x"], r["y"]
    k = r["w_per_display"]
    h_unit = 1.0 if system == "ip" else 1000.0  # PsychroLib SI enthalpy is J/kg
    fine = _frange(x0, x1, (x1 - x0) / 160)

    def w_sat(t):
        return lib.GetSatHumRatio(t, p) / k

    def clip(points):
        return [
            [round(x, 3), round(y, 3)]
            for x, y in points
            if x0 <= x <= x1 and y0 <= y <= y1
        ]

    lines = [
        {
            "kind": "saturation",
            "label": "100 %",
            "points": clip([(t, w_sat(t)) for t in fine]),
        }
    ]
    for rh in range(10, 100, 10):
        pts = [(t, lib.GetHumRatioFromRelHum(t, rh / 100, p) / k) for t in fine]
        lines.append({"kind": "rh", "label": f"{rh} %", "points": clip(pts)})
    for t in _frange(x0, x1, dx):
        lines.append(
            {
                "kind": "db",
                "label": f"{t:g}",
                "points": clip([(t, y0), (t, min(w_sat(t), y1))]),
            }
        )
    for w in _frange(y0 + dy, y1, dy):
        t_dp = lib.GetTDewPointFromHumRatio(x1, w * k, p)
        lines.append(
            {
                "kind": "w",
                "label": f"{w:g}",
                "points": clip([(max(t_dp, x0), w), (x1, w)]),
            }
        )
    for h in _frange(*r["h_range"], r["h_step"]):
        pts = []
        for y in _frange(y0, y1, (y1 - y0) / 80):
            t = lib.GetTDryBulbFromEnthalpyAndHumRatio(h * h_unit, y * k)
            if y <= w_sat(t) + 1e-9:
                pts.append((t, y))
        lines.append({"kind": "h", "label": f"{h:g}", "points": clip(pts)})
    for twb in _frange(*r["wb_range"], r["wb_step"]):
        pts = []
        for t in fine:
            if t < twb:
                continue
            w = lib.GetHumRatioFromTWetBulb(t, twb, p) / k
            if w >= 0:
                pts.append((t, w))
        lines.append({"kind": "wb", "label": f"{twb:g}", "points": clip(pts)})
    lines = [ln for ln in lines if len(ln["points"]) >= 2]
    return {
        "units": system,
        "x": {"min": x0, "max": x1, "step": dx, "label": xlabel},
        "y": {"min": y0, "max": y1, "step": dy, "label": ylabel},
        "lines": lines,
    }


def chart_point(t_db_c: float, w: float, system: str) -> list[float]:
    """A state as [x, y] on the chart in display units."""
    if system == "ip":
        return [t_db_c * 1.8 + 32.0, w * 7000.0]
    return [t_db_c, w * 1000.0]
