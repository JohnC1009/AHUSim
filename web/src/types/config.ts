/* Generated from engine/ahuverify/schema.py via unit-config.schema.json. Do not edit; run npm run gen:types. */

export type SchemaVersion = "0.2";
export type Name = string;
export type Value = number;
export type Unit = "ft" | "m";
export type Value1 = number;
export type Unit1 = "Pa" | "in_wc";
export type Value2 = number;
export type Unit2 = "cfm" | "m3/s" | "L/s" | "m3/h";
export type At = string;
export type Value3 = number;
export type Unit3 = "cfm" | "m3/s" | "L/s" | "m3/h";
export type Sign = "supply_minus_return" | "return_minus_supply";
export type Supply = string[];
export type Return = string[];
export type Type = "mixing_box";
export type Value4 = number;
export type Unit4 = "ft2" | "m2";
export type Value5 = number;
export type Unit5 = "fpm" | "m/s";
export type Value6 = number;
export type Unit6 = "F" | "C";
export type Type1 = "space";
export type Value7 = number;
export type Unit7 = "W" | "kW" | "Btu/h" | "MBH";
export type Value8 = number;
export type Unit8 = "kg/s" | "kg/h" | "lb/h";
export type Value9 = number;
export type Unit9 = "%";
export type Type2 = "plate_hx" | "runaround" | "heat_pipe";
export type EpsSens = number;
export type Type3 = "desiccant_wheel";
export type EpsLat = number;
export type Type4 = "steam_humidifier";
export type Type5 = "adiabatic_humidifier";
export type Effectiveness = number;
export type Type6 = "cooling_coil_chw";
export type Mode = "design";
export type Value10 = number;
export type Unit10 = "cfm" | "m3/s" | "L/s" | "m3/h";
export type Type7 = "cooling_coil_chw";
export type Mode1 = "measured";
export type Type8 = "energy_wheel";
export type EpsSens1 = number;
export type EpsLat1 = number;
export type Purge = boolean;
export type Eatr = number;
export type Type9 = "filter";
export type Type10 = "fan";
export type EtaFan = number;
export type EtaMotor = number;
export type MotorInAirstream = boolean;
export type Type11 = "heating_coil_hw";
export type Type12 = "electric_heater";
export type Stages = number | null;
export type Id = string;
export type Type13 = "temperature" | "temperature_averaging";
export type At1 = string;
export type Sensors = Sensor[];
export type Id1 = string;
export type Priority = number;
export type Enter = AllOf | AnyOf | NotOf | Comparison;
/**
 * @minItems 1
 */
export type All = [AllOf | AnyOf | NotOf | Comparison, ...(AllOf | AnyOf | NotOf | Comparison)[]];
/**
 * @minItems 1
 */
export type Any = [AllOf | AnyOf | NotOf | Comparison, ...(AllOf | AnyOf | NotOf | Comparison)[]];
export type Not = AllOf | AnyOf | NotOf | Comparison;
export type Var = "oa_db" | "oa_h" | "oa_dp" | "ra_db" | "ra_h" | "space_t" | "schedule";
export type Op = "<" | "<=" | ">" | ">=" | "==";
export type Value11 = string | Temperature | Enthalpy;
export type Value12 = number;
export type Unit11 = "Btu/lb" | "kJ/kg";
export type Loops = string[];
export type Modes = Mode2[];
export type Sensor1 = string;
/**
 * @minItems 1
 */
export type Stages1 = [Stage, ...Stage[]];
export type Actuator = string;
export type Action = "direct" | "reverse";
export type Role = ("preheat" | "freeze_protection") | null;
export type WeatherFile = string | null;
export type Scenarios = string[];
export type Id2 = string;
export type Schedule = string | null;
export type Operating = OperatingCondition[];

export interface UnitConfig {
  schema_version: SchemaVersion;
  unit: UnitInfo;
  airflows: Airflows;
  lanes: Lanes;
  components: Components;
  sensors: Sensors;
  sequence: Sequence;
  conditions: Conditions;
}
export interface UnitInfo {
  name: Name;
  altitude: Length;
  pressure_override?: Pressure | null;
}
export interface Length {
  value: Value;
  unit: Unit;
}
export interface Pressure {
  value: Value1;
  unit: Unit1;
}
export interface Airflows {
  supply: AirflowAt;
  min_oa: AirflowAt;
  pressurization_bias: PressurizationBias;
}
/**
 * A volumetric airflow and the location whose air state converts it to mass.
 */
export interface AirflowAt {
  value: Value2;
  unit: Unit2;
  at: At;
}
export interface PressurizationBias {
  value: Value3;
  unit: Unit3;
  sign: Sign;
}
export interface Lanes {
  supply: Supply;
  return: Return;
}
export interface Components {
  [k: string]:
    | MixingBox
    | Space
    | SensibleHx
    | DesiccantWheel
    | SteamHumidifier
    | AdiabaticHumidifier
    | CoolingCoilDesign
    | CoolingCoilMeasured
    | EnergyWheel
    | Filter
    | Fan
    | HeatingCoilHw
    | ElectricHeater;
}
export interface MixingBox {
  type: Type;
  dampers: MixingBoxDampers;
  freeze_threshold?: Temperature | null;
}
export interface MixingBoxDampers {
  oa: Damper;
  ra: Damper;
  relief: Damper;
}
export interface Damper {
  free_area: Area;
  max_velocity: Velocity;
}
export interface Area {
  value: Value4;
  unit: Unit4;
}
export interface Velocity {
  value: Value5;
  unit: Unit5;
}
export interface Temperature {
  value: Value6;
  unit: Unit6;
}
/**
 * Optional single space node: return air = supply air + space loads (spec §5.4).
 */
export interface Space {
  type: Type1;
  sensible_load: Power;
  latent_load?: Power | null;
  moisture_load?: MassFlow | null;
  t_min?: Temperature | null;
  t_max?: Temperature | null;
  rh_max?: RelHum | null;
}
export interface Power {
  value: Value7;
  unit: Unit7;
}
export interface MassFlow {
  value: Value8;
  unit: Unit8;
}
export interface RelHum {
  value: Value9;
  unit: Unit9;
}
/**
 * Plate exchanger, runaround loop or heat pipe: sensible-only heat recovery.
 */
export interface SensibleHx {
  type: Type2;
  eps_sens: EpsSens;
  face_area?: Area | null;
  max_face_velocity?: Velocity | null;
}
export interface DesiccantWheel {
  type: Type3;
  eps_lat: EpsLat;
  regen_heat: Power;
}
export interface SteamHumidifier {
  type: Type4;
  max_rate: MassFlow;
  absorption_distance: Length;
}
export interface AdiabaticHumidifier {
  type: Type5;
  effectiveness: Effectiveness;
  max_rate: MassFlow;
}
/**
 * Chilled-water coil modelled from one rating point (ADP / bypass factor).
 */
export interface CoolingCoilDesign {
  type: Type6;
  mode: Mode;
  face_area: Area;
  rating: CoolingCoilRating;
  max_face_velocity?: Velocity | null;
}
export interface CoolingCoilRating {
  eat_db: Temperature;
  eat_wb: Temperature;
  lat_db: Temperature;
  lat_wb: Temperature;
  airflow: Airflow;
  chws: Temperature;
  chwr: Temperature;
}
export interface Airflow {
  value: Value10;
  unit: Unit10;
}
/**
 * Chilled-water coil with a forced (measured) leaving state.
 */
export interface CoolingCoilMeasured {
  type: Type7;
  mode: Mode1;
  face_area: Area;
  leaving: LeavingAir;
  max_face_velocity?: Velocity | null;
}
export interface LeavingAir {
  db: Temperature;
  rh: RelHum;
}
export interface EnergyWheel {
  type: Type8;
  eps_sens: EpsSens1;
  eps_lat: EpsLat1;
  purge: Purge;
  eatr: Eatr;
}
export interface Filter {
  type: Type9;
  dp_clean: Pressure;
  dp_dirty: Pressure;
}
/**
 * Supply, return or exhaust fan. Airflow is fixed per mode in v1.
 */
export interface Fan {
  type: Type10;
  design_airflow: Airflow;
  total_static: Pressure;
  eta_fan: EtaFan;
  eta_motor: EtaMotor;
  motor_in_airstream: MotorInAirstream;
}
/**
 * Hot-water coil (preheat or reheat).
 */
export interface HeatingCoilHw {
  type: Type11;
  face_area: Area;
  rating: HeatingCoilRating;
  max_face_velocity?: Velocity | null;
}
export interface HeatingCoilRating {
  eat: Temperature;
  lat: Temperature;
  airflow: Airflow;
  ewt: Temperature;
  lwt: Temperature;
}
export interface ElectricHeater {
  type: Type12;
  power: Power;
  stages?: Stages;
}
export interface Sensor {
  id: Id;
  type: Type13;
  at: At1;
}
export interface Sequence {
  modes: Modes;
  loops: Loops1;
}
export interface Mode2 {
  id: Id1;
  priority: Priority;
  enter: Enter;
  fixed?: Fixed;
  loops?: Loops;
}
export interface AllOf {
  all: All;
}
export interface AnyOf {
  any: Any;
}
export interface NotOf {
  not: Not;
}
export interface Comparison {
  var: Var;
  op: Op;
  value: Value11;
}
export interface Enthalpy {
  value: Value12;
  unit: Unit11;
}
export interface Fixed {
  [k: string]: number;
}
export interface Loops1 {
  [k: string]: Loop;
}
export interface Loop {
  sensor: Sensor1;
  setpoint: Temperature;
  stages: Stages1;
  role?: Role;
}
export interface Stage {
  actuator: Actuator;
  action: Action;
}
export interface Conditions {
  weather_file?: WeatherFile;
  scenarios?: Scenarios;
  operating?: Operating;
}
/**
 * One named operating point for a scenario run (spec §5.9).
 */
export interface OperatingCondition {
  id: Id2;
  oa_db: Temperature;
  oa_wb?: Temperature | null;
  oa_rh?: RelHum | null;
  ra_db: Temperature;
  ra_rh: RelHum;
  schedule?: Schedule;
  space_t?: Temperature | null;
}
