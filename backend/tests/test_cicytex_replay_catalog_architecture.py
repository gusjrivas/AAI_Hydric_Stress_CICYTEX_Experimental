from app.dependencies import get_cicytex_replay_catalog
from app.main import app
from fastapi.testclient import TestClient

from historical_replay.catalog import ReplayCatalog


class FakeReplayCatalogQuery:
    def execute(self) -> ReplayCatalog:
        return ReplayCatalog(
            sensors=("fake-sensor",),
            emission_dates=("2023-07-06",),
            emission_dates_by_horizon={1: ("2023-07-06",)},
            horizons=(1, 2, 3),
            first_legitimate_emission="2023-07-06",
            last_observation="2023-07-25",
        )


def test_catalog_endpoint_delegates_to_the_injected_query():
    app.dependency_overrides[get_cicytex_replay_catalog] = FakeReplayCatalogQuery
    try:
        with TestClient(app) as client:
            response = client.get("/api/v2/cicytex/replay/catalog")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["sensors"] == ["fake-sensor"]
