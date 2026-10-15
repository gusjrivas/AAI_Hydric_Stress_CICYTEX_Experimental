import type { components, operations } from "./api/generated/schema";
import type {
  Sector,
  SectorListResult,
  SensorListResult,
  SensorSummary,
} from "./features/producer/catalogApi";
import type {
  ReadingRow,
  ReadingsResult,
  VariableCoverage,
} from "./features/producer/readingsApi";

type Equal<Left, Right> =
  (<Type>() => Type extends Left ? 1 : 2) extends
  (<Type>() => Type extends Right ? 1 : 2) ? true : false;
type Expect<Type extends true> = Type;
type Response<Operation> = Operation extends {
  responses: { 200: { content: { "application/json": infer Body } } };
} ? Body : never;

type ListSectors = operations["list_sectors_api_v2_sectors_get"];
type ListSensors = operations["list_sensors_api_v2_sensors_get"];
type GetReadings = operations["get_readings_api_v2_sensors__sensor_id__readings_get"];

type _Sector = Expect<Equal<Sector, components["schemas"]["SectorResponse"]>>;
type _Sensor = Expect<Equal<SensorSummary, components["schemas"]["SensorResponse"]>>;
type _SectorList = Expect<Equal<SectorListResult, Response<ListSectors>>>;
type _SensorList = Expect<Equal<SensorListResult, Response<ListSensors>>>;
type _ReadingRow = Expect<Equal<ReadingRow, components["schemas"]["ReadingRow"]>>;
type _Coverage = Expect<Equal<VariableCoverage, components["schemas"]["VariableCoverage"]>>;
type _Readings = Expect<Equal<ReadingsResult, Response<GetReadings>>>;

export type GeneratedProducerSliceAContract = [
  _Sector,
  _Sensor,
  _SectorList,
  _SensorList,
  _ReadingRow,
  _Coverage,
  _Readings,
];
