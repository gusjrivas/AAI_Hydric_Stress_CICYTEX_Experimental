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
import type {
  EnsembleComponentVote,
  EnsembleDetail,
  EventThreshold,
  Forecast,
  ForecastBatch,
  ForecastListResult,
  ForecastReview,
  ForecastSlot,
  LatestReview,
  ModelReference,
  ReviewRequest,
} from "./features/producer/forecastsApi";

type Equal<Left, Right> =
  (<Type>() => Type extends Left ? 1 : 2) extends
  (<Type>() => Type extends Right ? 1 : 2) ? true : false;
type Expect<Type extends true> = Type;
type Expand<Type> = { [Key in keyof Type]: Type[Key] };
type Response<Operation> = Operation extends {
  responses: { 200: { content: { "application/json": infer Body } } };
} ? Body : never;
type ResponseAt<Operation, Status extends number> = Operation extends {
  responses: Record<Status, { content: { "application/json": infer Body } }>;
} ? Body : never;

type ListSectors = operations["list_sectors_api_v2_sectors_get"];
type ListSensors = operations["list_sensors_api_v2_sensors_get"];
type GetReadings = operations["get_readings_api_v2_sensors__sensor_id__readings_get"];
type ListForecasts = operations["list_forecasts_api_v2_sensors__sensor_id__forecasts_get"];
type GetForecast = operations["get_forecast_api_v2_sensors__sensor_id__forecasts__forecast_id__get"];
type CreateReview = operations["create_review_api_v2_sensors__sensor_id__forecasts__forecast_id__reviews_post"];
type CreateForecasts = operations["create_forecasts_api_v2_sensors__sensor_id__forecasts_post"];
type GetHistoricalForecasts =
  operations["get_historical_forecasts_api_v2_sensors__sensor_id__historical__as_of_date__forecasts_get"];

type _Sector = Expect<Equal<Sector, components["schemas"]["SectorResponse"]>>;
type _Sensor = Expect<Equal<SensorSummary, components["schemas"]["SensorResponse"]>>;
type _SectorList = Expect<Equal<SectorListResult, Response<ListSectors>>>;
type _SensorList = Expect<Equal<SensorListResult, Response<ListSensors>>>;
type _ReadingRow = Expect<Equal<ReadingRow, components["schemas"]["ReadingRow"]>>;
type _Coverage = Expect<Equal<VariableCoverage, components["schemas"]["VariableCoverage"]>>;
type _Readings = Expect<Equal<ReadingsResult, Response<GetReadings>>>;
type GeneratedModelReference = components["schemas"]["ModelReference"];
type ExpectedModelReference = Pick<
  GeneratedModelReference,
  | "model_version"
  | "horizon_days"
  | "contract_version"
  | "trained_through"
  | "calibration_version"
  | "assessment_reference"
>;
type GeneratedEnsemble = components["schemas"]["EnsembleDetail"];
type ExpectedEnsembleVote = Expand<
  Omit<components["schemas"]["EnsembleComponentVote"], "model_reference"> & {
    model_reference: ExpectedModelReference;
  }
>;
type ExpectedEnsemble = Expand<Omit<GeneratedEnsemble, "components"> & {
  components: ExpectedEnsembleVote[];
}>;
type GeneratedForecast = ResponseAt<GetForecast, 200>;
type ExpectedForecast = Expand<Omit<GeneratedForecast, "ensemble" | "model_reference"> & {
  ensemble?: ExpectedEnsemble | null;
  model_reference: ExpectedModelReference;
}>;
type GeneratedReviewCreate = components["schemas"]["ReviewCreate"];
type ExpectedReviewRequest = {
  requestId: GeneratedReviewCreate["request_id"];
  expectedRevision: GeneratedReviewCreate["expected_revision"];
  action: GeneratedReviewCreate["action"];
  comment: Exclude<GeneratedReviewCreate["comment"], undefined>;
};
type GeneratedBatch = ResponseAt<CreateForecasts, 200 | 201>;
type ExpectedBatch = Expand<Pick<
  GeneratedBatch,
  | "batch_id"
  | "revision"
  | "as_of_date"
  | "data_age_days"
  | "server_today"
  | "provenance"
  | "calendar_timezone"
> & { slots: ForecastSlot[] }>;

type _EventThreshold = Expect<Equal<EventThreshold, components["schemas"]["EventThreshold"]>>;
type _ModelReference = Expect<Equal<ModelReference, ExpectedModelReference>>;
type _LatestReview = Expect<Equal<LatestReview, components["schemas"]["LatestReview"]>>;
type _ForecastReview = Expect<Equal<ForecastReview, ResponseAt<CreateReview, 201>>>;
type _EnsembleVote = Expect<Equal<EnsembleComponentVote, ExpectedEnsembleVote>>;
type _Ensemble = Expect<Equal<EnsembleDetail, ExpectedEnsemble>>;
type _Forecast = Expect<Equal<Forecast, ExpectedForecast>>;
type ExpectedForecastList = Expand<
  Omit<ResponseAt<ListForecasts, 200>, "items"> & { items: Forecast[] }
>;
type _ForecastList = Expect<Equal<ForecastListResult, ExpectedForecastList>>;
type _ReviewRequest = Expect<Equal<ReviewRequest, ExpectedReviewRequest>>;
type _ForecastBatch = Expect<Equal<ForecastBatch, ExpectedBatch>>;
type _HistoricalForecastBatch = Expect<
  ResponseAt<GetHistoricalForecasts, 200> extends ForecastBatch ? true : false
>;

export type GeneratedProducerSliceAContract = [
  _Sector,
  _Sensor,
  _SectorList,
  _SensorList,
  _ReadingRow,
  _Coverage,
  _Readings,
  _EventThreshold,
  _ModelReference,
  _LatestReview,
  _ForecastReview,
  _EnsembleVote,
  _Ensemble,
  _Forecast,
  _ForecastList,
  _ReviewRequest,
  _ForecastBatch,
  _HistoricalForecastBatch,
];
