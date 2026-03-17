"""Integrationstests für GET /v1/capabilities (Story 1.6, AC 4-5)."""
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings

EXPECTED_TYPES = {
    "correlation_filter",
    "dedup",
    "encode_categorical",
    "impute_missing",
    "outlier_handling",
    "rare_category_bucketing",
    "split",
    "time_feature_encoding",
}


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=str(tmp_path / "bikes.csv"),
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def test_get_capabilities_returns_200(client):
    resp = client.get("/v1/capabilities")
    assert resp.status_code == 200


def test_get_capabilities_content_type_json(client):
    resp = client.get("/v1/capabilities")
    assert "application/json" in resp.headers["content-type"]


def test_get_capabilities_json_structure(client):
    """AC4: Antwort ist konsistentes maschinenlesbares JSON."""
    resp = client.get("/v1/capabilities")
    data = resp.json()
    assert "steps" in data
    assert isinstance(data["steps"], list)


def test_get_capabilities_all_8_steps_present(client):
    """AC2: Alle 8 registrierten Steps sind in der Antwort enthalten."""
    resp = client.get("/v1/capabilities")
    data = resp.json()
    returned_types = {s["type"] for s in data["steps"]}
    assert EXPECTED_TYPES <= returned_types


def test_get_capabilities_each_step_has_type_description_params(client):
    """AC2: Jeder Step hat type, description und params."""
    resp = client.get("/v1/capabilities")
    data = resp.json()
    for step in data["steps"]:
        assert "type" in step
        assert "description" in step
        assert "params" in step


def test_get_capabilities_alphabetical_order(client):
    """AC4: Steps sind alphabetisch nach type sortiert."""
    resp = client.get("/v1/capabilities")
    data = resp.json()
    types = [s["type"] for s in data["steps"]]
    assert types == sorted(types)


def test_get_capabilities_descriptions_nonempty(client):
    resp = client.get("/v1/capabilities")
    data = resp.json()
    for step in data["steps"]:
        assert isinstance(step["description"], str)
        assert len(step["description"]) > 0


def test_get_capabilities_params_are_dicts(client):
    resp = client.get("/v1/capabilities")
    data = resp.json()
    for step in data["steps"]:
        assert isinstance(step["params"], dict)
