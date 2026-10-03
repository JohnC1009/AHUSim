"""Two independent copies of PsychroLib: `si` and `ip`.

PsychroLib stores its unit system in a module-level global. Toggling it would
be unsafe once the API serves concurrent requests, so the vendored file is
loaded twice under different module names, each fixed to one unit system.
Engine physics uses `si` only; `ip` is for I-P display values (spec §4).
"""

import importlib.util
from pathlib import Path
from types import ModuleType

_SOURCE = Path(__file__).parent / "_vendor" / "psychrolib.py"


def _load_copy(name: str, unit_system_attr: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"ahuverify._psychrolib_{name}", _SOURCE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SetUnitSystem(getattr(module, unit_system_attr))
    return module


si = _load_copy("si", "SI")
ip = _load_copy("ip", "IP")
