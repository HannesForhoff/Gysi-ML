"""Integrationstests für Spec-Modifikation (Story 4.2)."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gysi_ml.api.app import create_app
from gysi_ml.config import Settings
from gysi_ml.persistence import spec_repository


@pytest.fixture
def csv_file(tmp_path):
    df = pd.DataFrame({
        "instant": range(1, 21),
        "cnt": range(100, 120),
        "temp": [0.5] * 20,
        "dteday": ["2012-01-01"] * 20,
    })
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def client(tmp_path, csv_file):
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
    )
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_spec(client):
    """Session + Execute → gibt (client, session_id, db_path) zurück."""
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]
    exec_resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": []}},
    )
    assert exec_resp.status_code == 200
    return client, session_id


def _create_session(client) -> str:
    resp = client.post("/v1/sessions", json={"name": "Test"})
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _execute(client, session_id: str, steps: list | None = None) -> dict:
    if steps is None:
        steps = []
    resp = client.post(
        f"/v1/sessions/{session_id}/execute",
        json={"spec": {"steps": steps}},
    )
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# AC 5: Versionsnummern-Logik
# ---------------------------------------------------------------------------


def test_executor_creates_v1_on_first_execute(client):
    """Erster Execute in einer Session → spec_version == 'v1'."""
    session_id = _create_session(client)
    _execute(client, session_id)

    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 200
    assert resp.json()["version"] == "v1"


def test_executor_creates_v2_on_second_execute(client):
    """Zweiter Execute in derselben Session → spec_version == 'v2'."""
    session_id = _create_session(client)
    _execute(client, session_id)
    _execute(client, session_id, [{"type": "dedup"}])

    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 200
    assert resp.json()["version"] == "v2"


# ---------------------------------------------------------------------------
# AC 4: GET /spec zeigt enabled-Feld
# ---------------------------------------------------------------------------


def test_get_spec_shows_enabled_false(client, tmp_path, csv_file):
    """Nach create_spec_version mit 'enabled: false' zeigt GET /spec den disabled Step."""
    settings = Settings(
        db_path=str(tmp_path / "test.db"),
        data_path=csv_file,
    )
    session_id = _create_session(client)
    _execute(client, session_id)

    # Direkt via spec_repository eine Spec mit enabled=false anlegen
    spec_with_disabled = {
        "steps": [
            {"type": "dedup", "enabled": True},
            {"type": "outlier_handling", "enabled": False, "params": {"method": "iqr"}},
        ]
    }
    spec_repository.create_spec_version(
        session_id=session_id,
        spec=spec_with_disabled,
        db_path=settings.db_path,
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec")
    assert resp.status_code == 200
    body = resp.json()
    steps = body["spec"]["steps"]
    disabled_steps = [s for s in steps if s.get("enabled") is False]
    assert len(disabled_steps) == 1
    assert disabled_steps[0]["type"] == "outlier_handling"


# ---------------------------------------------------------------------------
# AC 1+5: Audit-Trail — v1 abrufbar nach Erstellung v2
# ---------------------------------------------------------------------------


def test_get_spec_v1_still_accessible_after_v2(client):
    """v1 bleibt abrufbar nachdem v2 existiert."""
    session_id = _create_session(client)
    _execute(client, session_id, [{"type": "dedup"}])
    _execute(client, session_id, [{"type": "dedup"}, {"type": "split", "params": {"test_size": 0.2}}])

    resp_v1 = client.get(f"/v1/sessions/{session_id}/spec/v1")
    assert resp_v1.status_code == 200
    assert resp_v1.json()["spec"]["steps"] == [{"type": "dedup"}]

    resp_v2 = client.get(f"/v1/sessions/{session_id}/spec/v2")
    assert resp_v2.status_code == 200
    assert len(resp_v2.json()["spec"]["steps"]) == 2
