from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path, PurePosixPath

import pytest
import yaml

from backend.app.config import get_cicytex_legacy_feedback_json
from historical_replay.adapters import sqlite_sessions
from historical_replay.cicytex_feedback import CicytexFeedbackRepositoryError

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "compose.cicytex.yml"

VOLUME_KEY = "cicytex-feedback"
VOLUME_NAME = "aai-cicytex-experiment-feedback"
VOLUME_TARGET = "/workspace/cicytex-feedback"
SESSION_DATABASE = f"{VOLUME_TARGET}/cicytex_replay_sessions.sqlite3"
LEGACY_FEEDBACK = f"{VOLUME_TARGET}/feedback.json"
LEGACY_ENVIRONMENT_KEY = "CICYTEX_REPLAY_FEEDBACK_DIR"
LEGACY_FEEDBACK_KEY = "CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON"
LEGACY_FEEDBACK_DEFAULT = "${CICYTEX_REPLAY_LEGACY_FEEDBACK_JSON:-}"
LEGACY_FEEDBACK_DISCOVERY_KEY = "CICYTEX_REPLAY_LEGACY_FEEDBACK_DISCOVERY"
SESSION_DATABASE_KEY = "CICYTEX_REPLAY_SESSION_DB"


def _load_compose() -> dict:
    document = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    assert type(document) is dict
    return document


def _assert_durable_replay_storage(
    document: dict,
    *,
    legacy_feedback_override: str = "",
) -> None:
    violations: list[str] = []
    if type(document) is not dict:
        raise AssertionError("compose document must be a mapping")

    services = document.get("services")
    backend = services.get("backend") if type(services) is dict else None
    environment = backend.get("environment") if type(backend) is dict else None
    mounts = backend.get("volumes") if type(backend) is dict else None
    declared_volumes = document.get("volumes")

    if type(environment) is not dict:
        violations.append("backend environment must be a mapping")
        environment = {}
    if LEGACY_ENVIRONMENT_KEY in environment:
        violations.append(f"legacy {LEGACY_ENVIRONMENT_KEY} must be absent")
    if environment.get(SESSION_DATABASE_KEY) != SESSION_DATABASE:
        violations.append(f"{SESSION_DATABASE_KEY} must equal {SESSION_DATABASE}")
    if environment.get(LEGACY_FEEDBACK_KEY) != LEGACY_FEEDBACK_DEFAULT:
        violations.append(f"{LEGACY_FEEDBACK_KEY} must use optional empty-default interpolation")
    if environment.get(LEGACY_FEEDBACK_DISCOVERY_KEY) != LEGACY_FEEDBACK:
        violations.append(f"{LEGACY_FEEDBACK_DISCOVERY_KEY} must equal the preserved legacy path")

    expected_mount = f"{VOLUME_KEY}:{VOLUME_TARGET}"
    if type(mounts) is not list or mounts.count(expected_mount) != 1:
        violations.append(f"backend must mount exactly one {expected_mount}")
    else:
        sources_at_target = [
            mount.split(":", 1)[0]
            for mount in mounts
            if type(mount) is str and mount.split(":", 1)[-1] == VOLUME_TARGET
        ]
        if sources_at_target != [VOLUME_KEY]:
            violations.append("session database target must use the preserved named volume")

    volume = declared_volumes.get(VOLUME_KEY) if type(declared_volumes) is dict else None
    if volume != {"name": VOLUME_NAME}:
        violations.append(f"volume {VOLUME_KEY} must preserve name {VOLUME_NAME}")

    configured_database = environment.get(SESSION_DATABASE_KEY)
    if type(configured_database) is str and (
        str(PurePosixPath(configured_database).parent) != VOLUME_TARGET
    ):
        violations.append("session database parent must equal the mounted durable target")
    if legacy_feedback_override and legacy_feedback_override != LEGACY_FEEDBACK:
        violations.append(f"migration {LEGACY_FEEDBACK_KEY} must equal {LEGACY_FEEDBACK}")
    if legacy_feedback_override and (
        str(PurePosixPath(legacy_feedback_override).parent) != VOLUME_TARGET
    ):
        violations.append("legacy feedback parent must equal the mounted durable target")

    assert not violations, "; ".join(violations)


def test_cicytex_compose_binds_replay_sqlite_to_the_preserved_durable_volume():
    _assert_durable_replay_storage(_load_compose())


def _valid_document() -> dict:
    return {
        "services": {
            "backend": {
                "environment": {
                    SESSION_DATABASE_KEY: SESSION_DATABASE,
                    LEGACY_FEEDBACK_KEY: LEGACY_FEEDBACK_DEFAULT,
                    LEGACY_FEEDBACK_DISCOVERY_KEY: LEGACY_FEEDBACK,
                },
                "volumes": [f"{VOLUME_KEY}:{VOLUME_TARGET}"],
            }
        },
        "volumes": {VOLUME_KEY: {"name": VOLUME_NAME}},
    }


def _add_stale_environment(document: dict) -> None:
    document["services"]["backend"]["environment"][LEGACY_ENVIRONMENT_KEY] = VOLUME_TARGET


def _remove_database_environment(document: dict) -> None:
    del document["services"]["backend"]["environment"][SESSION_DATABASE_KEY]


def _change_database_filename(document: dict) -> None:
    document["services"]["backend"]["environment"][
        SESSION_DATABASE_KEY
    ] = f"{VOLUME_TARGET}/other.sqlite3"


def _move_database_outside_mount(document: dict) -> None:
    document["services"]["backend"]["environment"][
        SESSION_DATABASE_KEY
    ] = "/workspace/data/cicytex_replay_sessions.sqlite3"


def _remove_legacy_feedback_environment(document: dict) -> None:
    del document["services"]["backend"]["environment"][LEGACY_FEEDBACK_KEY]


def _change_legacy_feedback_filename(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_KEY
    ] = f"{VOLUME_TARGET}/other.json"


def _move_legacy_feedback_outside_mount(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_KEY
    ] = "/workspace/data/feedback.json"


def _hardcode_exact_legacy_feedback(document: dict) -> None:
    document["services"]["backend"]["environment"][LEGACY_FEEDBACK_KEY] = LEGACY_FEEDBACK


def _use_nonempty_legacy_feedback_default(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_KEY
    ] = f"${{{LEGACY_FEEDBACK_KEY}:-{LEGACY_FEEDBACK}}}"


def _interpolate_wrong_legacy_feedback_variable(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_KEY
    ] = "${CICYTEX_WRONG_LEGACY_FEEDBACK_JSON:-}"


def _remove_legacy_feedback_discovery(document: dict) -> None:
    del document["services"]["backend"]["environment"][LEGACY_FEEDBACK_DISCOVERY_KEY]


def _change_legacy_feedback_discovery(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_DISCOVERY_KEY
    ] = f"{VOLUME_TARGET}/other.json"


def _move_legacy_feedback_discovery_outside_mount(document: dict) -> None:
    document["services"]["backend"]["environment"][
        LEGACY_FEEDBACK_DISCOVERY_KEY
    ] = "/workspace/data/feedback.json"


def _remove_mount(document: dict) -> None:
    document["services"]["backend"]["volumes"] = []


def _rename_mount_source(document: dict) -> None:
    document["services"]["backend"]["volumes"] = [f"renamed-feedback:{VOLUME_TARGET}"]


def _rename_mount_target(document: dict) -> None:
    document["services"]["backend"]["volumes"] = [f"{VOLUME_KEY}:/workspace/renamed-feedback"]
    document["services"]["backend"]["environment"][
        SESSION_DATABASE_KEY
    ] = "/workspace/renamed-feedback/cicytex_replay_sessions.sqlite3"


def _rename_declared_volume(document: dict) -> None:
    document["volumes"] = {"renamed-feedback": {"name": VOLUME_NAME}}
    document["services"]["backend"]["volumes"] = [f"renamed-feedback:{VOLUME_TARGET}"]


def _rename_external_volume(document: dict) -> None:
    document["volumes"][VOLUME_KEY]["name"] = "renamed-experiment-feedback"


@pytest.mark.parametrize(
    "mutate",
    (
        _add_stale_environment,
        _remove_database_environment,
        _change_database_filename,
        _move_database_outside_mount,
        _remove_legacy_feedback_environment,
        _change_legacy_feedback_filename,
        _move_legacy_feedback_outside_mount,
        _hardcode_exact_legacy_feedback,
        _use_nonempty_legacy_feedback_default,
        _interpolate_wrong_legacy_feedback_variable,
        _remove_legacy_feedback_discovery,
        _change_legacy_feedback_discovery,
        _move_legacy_feedback_discovery_outside_mount,
        _remove_mount,
        _rename_mount_source,
        _rename_mount_target,
        _rename_declared_volume,
        _rename_external_volume,
    ),
    ids=lambda mutate: mutate.__name__.removeprefix("_"),
)
def test_durable_replay_storage_contract_rejects_unsafe_mutations(
    mutate: Callable[[dict], None],
):
    document = deepcopy(_valid_document())
    mutate(document)

    with pytest.raises(AssertionError):
        _assert_durable_replay_storage(document)


def test_durable_replay_storage_contract_accepts_only_the_coherent_profile():
    _assert_durable_replay_storage(_valid_document())


def test_fresh_volume_accepts_an_empty_optional_legacy_feedback_override():
    _assert_durable_replay_storage(_valid_document(), legacy_feedback_override="")


@pytest.mark.parametrize("configured", (None, ""))
def test_optional_legacy_feedback_config_resolves_absent_or_empty_to_none(
    configured: str | None,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(LEGACY_FEEDBACK_DISCOVERY_KEY, raising=False)
    if configured is None:
        monkeypatch.delenv(LEGACY_FEEDBACK_KEY, raising=False)
    else:
        monkeypatch.setenv(LEGACY_FEEDBACK_KEY, configured)

    assert get_cicytex_legacy_feedback_json() is None


@pytest.mark.parametrize("configured", (None, ""))
def test_deployment_discovers_existing_legacy_feedback_when_override_is_empty(
    tmp_path: Path,
    configured: str | None,
    monkeypatch: pytest.MonkeyPatch,
):
    legacy = tmp_path / "feedback.json"
    legacy.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(LEGACY_FEEDBACK_DISCOVERY_KEY, str(legacy))
    if configured is None:
        monkeypatch.delenv(LEGACY_FEEDBACK_KEY, raising=False)
    else:
        monkeypatch.setenv(LEGACY_FEEDBACK_KEY, configured)

    assert get_cicytex_legacy_feedback_json() == legacy


def test_deployment_discovery_absent_keeps_fresh_volume_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    discovery = tmp_path / "feedback.json"
    monkeypatch.setenv(LEGACY_FEEDBACK_DISCOVERY_KEY, str(discovery))
    monkeypatch.delenv(LEGACY_FEEDBACK_KEY, raising=False)

    assert get_cicytex_legacy_feedback_json() is None


def test_deployment_rejects_explicit_legacy_path_that_disagrees_with_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    discovery = tmp_path / "feedback.json"
    override = tmp_path / "other.json"
    discovery.write_text("{}", encoding="utf-8")
    override.write_text("{}", encoding="utf-8")
    monkeypatch.setenv(LEGACY_FEEDBACK_DISCOVERY_KEY, str(discovery))
    monkeypatch.setenv(LEGACY_FEEDBACK_KEY, str(override))

    with pytest.raises(ValueError):
        get_cicytex_legacy_feedback_json()


def test_feedback_only_discovery_fails_closed_instead_of_creating_empty_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    legacy = tmp_path / "feedback.json"
    database = tmp_path / "fresh.sqlite3"
    legacy.write_text(
        '{"CP1_S1|2023-07-06|1":{"estado_validacion":"confirmada",'
        '"etiqueta_corregida":1,"observacion":"preserved-review",'
        '"registered_at":"2026-10-12T10:00:00+00:00",'
        '"simulated_at":"2023-07-07",'
        '"scope":"demostracion; no recalibra ni reentrena"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv(LEGACY_FEEDBACK_DISCOVERY_KEY, str(legacy))
    monkeypatch.delenv(LEGACY_FEEDBACK_KEY, raising=False)

    with pytest.raises(CicytexFeedbackRepositoryError):
        sqlite_sessions.SQLiteCicytexFeedbackRepository(
            database,
            legacy_feedback_path=get_cicytex_legacy_feedback_json(),
        )

    assert not database.exists()


def test_fresh_database_does_not_attempt_legacy_feedback_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def forbidden_parse(path: Path):
        raise AssertionError(f"fresh database attempted legacy parse: {path.name}")

    monkeypatch.setattr(sqlite_sessions, "_parse_cicytex_legacy", forbidden_parse)
    database = tmp_path / "fresh.sqlite3"

    sqlite_sessions.SQLiteCicytexFeedbackRepository(
        database,
        legacy_feedback_path=None,
    )

    assert database.is_file()


def test_existing_deployment_accepts_only_the_exact_legacy_migration_path():
    _assert_durable_replay_storage(
        _valid_document(),
        legacy_feedback_override=LEGACY_FEEDBACK,
    )


@pytest.mark.parametrize(
    "legacy_feedback_override",
    (
        f"{VOLUME_TARGET}/other.json",
        "/workspace/data/feedback.json",
    ),
)
def test_existing_deployment_rejects_an_incoherent_legacy_migration_path(
    legacy_feedback_override: str,
):
    with pytest.raises(AssertionError):
        _assert_durable_replay_storage(
            _valid_document(),
            legacy_feedback_override=legacy_feedback_override,
        )
