"""Filter: no change of air state; its pressure drop feeds fan heat (spec §5.4)."""

from ahuverify import schema
from ahuverify.components import ComponentResult, closure_residuals
from ahuverify.state import AirStream


class Filter:
    type = "filter"

    def __init__(self, name: str, cfg: schema.Filter):
        self.name = name
        self.cfg = cfg

    @property
    def dp(self) -> float:
        """Pressure drop used for fan heat, Pa: the dirty (final) value.

        Dirty is the worst case for supply temperature after a fan in cooling;
        see docs/decisions/0002.
        """
        return self.cfg.dp_dirty.si

    def solve(
        self, inlets: dict[str, AirStream], actuators: dict[str, float], p: float
    ) -> ComponentResult:
        inlet = inlets["in"]
        return ComponentResult(
            outlets={"out": inlet}, residuals=closure_residuals([inlet], [inlet])
        )
