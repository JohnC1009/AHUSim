"""M1-10: the example notebook executes cleanly from a fresh kernel."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient

EXAMPLES = Path(__file__).parents[1] / "examples"


def test_default_unit_notebook_runs():
    nb = nbformat.read(EXAMPLES / "default_unit.ipynb", as_version=4)
    NotebookClient(
        nb,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(EXAMPLES)}},
    ).execute()
    text = "".join(
        o.get("text", "")
        for c in nb.cells
        if c.cell_type == "code"
        for o in c.get("outputs", [])
    )
    assert "SAT" in text and "Converged" in text
    assert "min_oa" not in text  # 3,000 cfm at the OA damper is met in both cases
