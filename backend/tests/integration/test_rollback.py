"""Integrationstests für POST /v1/sessions/{id}/rollback (Story 8.3)."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.persistence import spec_repository


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame(
        {
            "instant": range(1, 21),
            "cnt": range(100, 120),
            "temp": [0.5] * 20,
            "dteday": ["2012-01-01"] * 20,
        }
    )
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def settings(tmp_path, csv_file):
    return Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _add_spec(settings, session_id: str, steps: list | None = None) -> dict:
    return spec_repository.create_spec_version(
        session_id=session_id,
        spec={"steps": steps or []},
        db_path=settings.db_path,
    )


# ---------------------------------------------------------------------------
# AC1: Rollback erzeugt neue Version (keine bestehende wird überschrieben)
# ---------------------------------------------------------------------------
def test_rollback_creates_new_version(client, settings):
    session_id = _create_session(client)

    v1 = _add_spec(settings, session_id, steps=[{"type": "dedup"}])
    v2 = _add_spec(settings, session_id, steps=[{"type": "imputation"}])
    v3 = _add_spec(settings, session_id, steps=[{"type": "encoding"}])

    resp = client.post(
        f"/v1/sessions/{session_id}/rollback",
        json={"target_spec_id": v1["spec_id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "rollback"
    assert body["new_version"] == "v4"

    # Alle Versionen noch vorhanden (AC4)
    all_specs = spec_repository.get_all_specs_for_session(
        session_id=session_id, db_path=settings.db_path
    )
    versions = [s["version"] for s in all_specs]
    assert "v1" in versions
    assert "v2" in versions
    assert "v3" in versions
    assert "v4" in versions
    assert len(versions) == 4


# ---------------------------------------------------------------------------
# AC2: Korrekte parent_spec_id
# ---------------------------------------------------------------------------
def test_rollback_correct_parent_spec_id(client, settings):
    session_id = _create_session(client)

    v1 = _add_spec(settings, session_id)
    v2 = _add_spec(settings, session_id)
    v3 = _add_spec(settings, session_id)

    resp = client.post(
        f"/v1/sessions/{session_id}/rollback",
        json={"target_spec_id": v1["spec_id"]},
    )
    assert resp.status_code == 200
    new_spec_id = resp.json()["new_spec_id"]

    all_specs = spec_repository.get_all_specs_for_session(
        session_id=session_id, db_path=settings.db_path
    )
    new_entry = next(s for s in all_specs if s["spec_id"] == new_spec_id)
    assert new_entry["parent_spec_id"] == v1["spec_id"]


# ---------------------------------------------------------------------------
# AC3: Korrekte change_summary
# ---------------------------------------------------------------------------
def test_rollback_correct_change_summary(client, settings):
    session_id = _create_session(client)

    v1 = _add_spec(settings, session_id)
    _add_spec(settings, session_id)

    resp = client.post(
        f"/v1/sessions/{session_id}/rollback",
        json={"target_spec_id": v1["spec_id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["change_summary"] == "Rollback auf v1"


# ---------------------------------------------------------------------------
# AC5: HTTP 404 bei unbekannter target_spec_id
# ---------------------------------------------------------------------------
def test_rollback_unknown_spec_id_returns_404(client, settings):
    session_id = _create_session(client)
    _add_spec(settings, session_id)

    resp = client.post(
        f"/v1/sessions/{session_id}/rollback",
        json={"target_spec_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SPEC_NOT_FOUND"


# ---------------------------------------------------------------------------
# AC5: Spec einer anderen Session → HTTP 404
# ---------------------------------------------------------------------------
def test_rollback_wrong_session_returns_404(client, settings):
    session_a = _create_session(client)
    session_b = _create_session(client)

    spec_in_a = _add_spec(settings, session_a)

    # target_spec_id gehört zu session_a, aber Aufruf für session_b
    resp = client.post(
        f"/v1/sessions/{session_b}/rollback",
        json={"target_spec_id": spec_in_a["spec_id"]},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SPEC_NOT_FOUND"


# ---------------------------------------------------------------------------
# Unbekannte Session → HTTP 404
# ---------------------------------------------------------------------------
def test_rollback_unknown_session_returns_404(client):
    resp = client.post(
        "/v1/sessions/nonexistent-session/rollback",
        json={"target_spec_id": "some-id"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SESSION_NOT_FOUND"
