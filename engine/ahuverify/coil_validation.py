"""M1-9: compare the design-mode cooling-coil model with manufacturer selections.

A selection file holds the coil's rating (what the model is calibrated from)
and off-design points from the manufacturer's software. For each point the
model is run at valve = 1 and its leaving state and capacity are compared.
Proposed acceptance (docs/decisions/coil-model.md): LAT db and wb within
±1.0 °F, total capacity within ±5 %.
"""

from dataclasses import dataclass

from ahuverify import schema, units
from ahuverify.components.cooling_coil import CoolingCoilDesignMode
from ahuverify.psychro import si
from ahuverify.state import AirState, AirStream

LIMIT_LAT_F = 1.0
LIMIT_Q_PCT = 5.0


class SelectionPoint(schema._Model):
    id: str
    eat_db: schema.Temperature
    eat_wb: schema.Temperature
    airflow: schema.Airflow  # at entering conditions
    chws: schema.Temperature
    lat_db: schema.Temperature
    lat_wb: schema.Temperature
    q_total: schema.Power


class Selection(schema._Model):
    source: str
    altitude: schema.Length
    coil: schema.CoolingCoilDesign
    points: list[SelectionPoint]


@dataclass(frozen=True)
class Comparison:
    id: str
    lat_db_f: float  # model
    lat_wb_f: float
    q_mbh: float
    d_lat_db_f: float  # model − selection
    d_lat_wb_f: float
    d_q_pct: float

    @property
    def within_limits(self) -> bool:
        return (
            abs(self.d_lat_db_f) <= LIMIT_LAT_F
            and abs(self.d_lat_wb_f) <= LIMIT_LAT_F
            and abs(self.d_q_pct) <= LIMIT_Q_PCT
        )


def compare(selection: Selection) -> list[Comparison]:
    p = si.GetStandardAtmPressure(selection.altitude.si)
    coil = CoolingCoilDesignMode("cc", selection.coil, p=p)
    rows = []
    for pt in selection.points:
        entering = AirState.from_db_wb(pt.eat_db.si, pt.eat_wb.si, p)
        inlet = AirStream(entering, pt.airflow.si / entering.v)
        t, w = coil.valve_open_leaving(inlet, chws=pt.chws.si)
        leaving = AirState.from_db_w(t, w, p)
        q = inlet.m_da * (entering.h - leaving.h) * 1000.0  # W
        lat_db_f = units.from_si(leaving.t_db, "F")
        lat_wb_f = units.from_si(leaving.t_wb, "F")
        q_mbh = units.from_si(q, "MBH")
        rows.append(
            Comparison(
                id=pt.id,
                lat_db_f=lat_db_f,
                lat_wb_f=lat_wb_f,
                q_mbh=q_mbh,
                d_lat_db_f=lat_db_f - units.from_si(pt.lat_db.si, "F"),
                d_lat_wb_f=lat_wb_f - units.from_si(pt.lat_wb.si, "F"),
                d_q_pct=100.0 * (q_mbh / units.from_si(pt.q_total.si, "MBH") - 1.0),
            )
        )
    return rows
