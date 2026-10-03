"""Print the M1-9 comparison for every selection file, as a Markdown table.

Usage (from engine/):  python examples/compare_coil_selections.py
Add one JSON file per manufacturer selection to tests/fixtures/coil_selections/
(copy example_rated_point.json). Paste the output into docs/decisions/coil-model.md.
"""

from pathlib import Path

from ahuverify.coil_validation import LIMIT_LAT_F, LIMIT_Q_PCT, Selection, compare

FOLDER = Path(__file__).parents[1] / "tests" / "fixtures" / "coil_selections"

print(f"Limits: LAT ±{LIMIT_LAT_F} °F, capacity ±{LIMIT_Q_PCT} %\n")
print(
    "| file | point | model LAT db/wb (°F) | Δ db (°F) | Δ wb (°F) | model Q (MBH) | Δ Q (%) | OK |"
)
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for path in sorted(FOLDER.glob("*.json")):
    for r in compare(Selection.model_validate_json(path.read_text())):
        ok = "yes" if r.within_limits else "**no**"
        print(
            f"| {path.stem} | {r.id} | {r.lat_db_f:.1f} / {r.lat_wb_f:.1f} | {r.d_lat_db_f:+.2f} | "
            f"{r.d_lat_wb_f:+.2f} | {r.q_mbh:.1f} | {r.d_q_pct:+.1f} | {ok} |"
        )
