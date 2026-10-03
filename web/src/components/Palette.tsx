import { allowedTypes, insertShared, insertSingle } from "../lib/lanes.ts";
import { COMPONENT_LABELS, CROSS_LANE, SYMBOL } from "../lib/model.ts";
import { useWorkspace } from "../store.ts";

const ORDER = [
  "filter", "heating_coil_hw", "electric_heater", "cooling_coil_chw", "steam_humidifier", "adiabatic_humidifier",
  "fan", "mixing_box", "energy_wheel", "plate_hx", "runaround", "heat_pipe", "desiccant_wheel",
];

export function Palette() {
  const { config, slot, edit, select } = useWorkspace();
  if (!config) return null;
  const ok = allowedTypes(config, slot.supply, slot.ret);
  const where =
    slot.supply !== null && slot.ret !== null
      ? "a slot in each lane (parts that span both lanes)"
      : slot.supply !== null
        ? "a supply-lane slot"
        : slot.ret !== null
          ? "a return-lane slot"
          : null;
  const add = (type: string) => {
    const [cfg, id] =
      CROSS_LANE.has(type) || type === "mixing_box"
        ? insertShared(config, type, slot.supply!, slot.ret!)
        : insertSingle(config, type, slot.supply !== null ? { lane: "supply", index: slot.supply } : { lane: "return", index: slot.ret! });
    edit(cfg);
    useWorkspace.setState({ slot: { supply: null, ret: null } });
    select(id);
  };
  return (
    <div className="stack tight palette">
      <h3>Components</h3>
      <p className="hint">{where ? `Adding to ${where}.` : "Pick a + slot in the schematic (one in each lane for wheels and the mixing box)."}</p>
      <ul className="list">
        {ORDER.map((t) => {
          const enabled = ok.has(t);
          return (
            <li
              key={t}
              role="button"
              aria-disabled={!enabled}
              className={enabled ? "clickable" : undefined}
              onClick={() => enabled && add(t)}
            >
              <svg className="sym-icon" aria-hidden="true"><use href={`#sym-${SYMBOL[t]}`} /></svg>
              {COMPONENT_LABELS[t]}
              {CROSS_LANE.has(t) || t === "mixing_box" ? <span className="badge">both lanes</span> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
