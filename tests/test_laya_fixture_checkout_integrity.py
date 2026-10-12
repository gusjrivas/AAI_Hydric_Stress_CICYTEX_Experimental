import hashlib
from pathlib import Path

import pytest

FIXTURES = {
    "/tests/fixtures/laya/runtime_dependency/uv.lock": (
        37_599,
        "e968771680b9c6e683163230ebd98b43541325ccb36d6959d1f9ed5565bd5526",
    ),
    "/tests/fixtures/laya/runtime_dependency/laya-runtime.cdx.json": (
        65_198,
        "f2fde1a342990e3b5b4d74d4930bf37f6d2229768b509a27f34edffc009a03b2",
    ),
    "/tests/fixtures/laya/runtime_oci/oci-manifest.json": (
        3_166,
        "7e46eb4f9e10b81e550b2587d1b12d50e0e9d746e346077e860e702ce169d9f0",
    ),
}


def _repository_root() -> Path:
    return Path(__file__).parents[1]


def _active_attribute_rules(payload: str) -> set[str]:
    return {
        line.strip()
        for line in payload.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_laya_evidence_fixtures_have_exact_binary_checkout_rules():
    attributes_path = _repository_root() / ".gitattributes"
    try:
        payload = attributes_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        pytest.fail("repository .gitattributes is required for byte-stable Laya fixtures")

    rules = _active_attribute_rules(payload)
    expected = {f"{path} -text" for path in FIXTURES}
    missing = expected - rules

    assert not missing, "Laya evidence fixtures require exact repository-root -text rules"


@pytest.mark.parametrize(
    ("repository_path", "expected_size", "expected_sha256"),
    tuple((path, size, digest) for path, (size, digest) in FIXTURES.items()),
)
def test_laya_evidence_fixture_checkout_bytes_are_exact(
    repository_path: str,
    expected_size: int,
    expected_sha256: str,
):
    fixture_path = _repository_root() / repository_path.removeprefix("/")
    payload = fixture_path.read_bytes()

    assert len(payload) == expected_size
    assert hashlib.sha256(payload).hexdigest() == expected_sha256
