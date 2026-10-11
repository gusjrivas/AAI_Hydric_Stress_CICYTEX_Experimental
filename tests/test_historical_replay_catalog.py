from historical_replay.catalog import GetReplayCatalog, ReplayCatalog


class FakeReplayCatalogSource:
    def __init__(self, catalog: ReplayCatalog) -> None:
        self.catalog = catalog
        self.calls = 0

    def load_catalog(self) -> ReplayCatalog:
        self.calls += 1
        return self.catalog


def test_get_replay_catalog_delegates_to_the_configured_source():
    expected = ReplayCatalog(
        sensors=("CP1_S1", "CP2_S1"),
        emission_dates=("2023-07-06", "2023-07-07"),
        emission_dates_by_horizon={
            1: ("2023-07-06",),
            2: ("2023-07-07",),
        },
        horizons=(1, 2, 3),
        first_legitimate_emission="2023-07-06",
        last_observation="2023-07-25",
    )
    source = FakeReplayCatalogSource(expected)

    result = GetReplayCatalog(source).execute()

    assert result == expected
    assert source.calls == 1


def test_replay_catalog_serializes_with_the_existing_http_shape():
    catalog = ReplayCatalog(
        sensors=("CP1_S1",),
        emission_dates=("2023-07-06",),
        emission_dates_by_horizon={1: ("2023-07-06",)},
        horizons=(1, 2, 3),
        first_legitimate_emission="2023-07-06",
        last_observation="2023-07-25",
    )

    assert catalog.to_dict() == {
        "sensors": ["CP1_S1"],
        "emission_dates": ["2023-07-06"],
        "emission_dates_by_horizon": {"1": ["2023-07-06"]},
        "horizons": [1, 2, 3],
        "first_legitimate_emission": "2023-07-06",
        "last_observation": "2023-07-25",
    }
