"""Integrationstests für GET /v1/sessions/{id}/spec/tree (Story 8.2)."""

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
    """Erstellt eine Spec-Version direkt über das Repository."""
    return spec_repository.create_spec_version(
        session_id=session_id,
        spec={"steps": steps or []},
        db_path=settings.db_path,
    )


# ---------------------------------------------------------------------------
# AC4: Neue Session → Basisknoten (v1, leere Spec) wird automatisch angelegt
# ---------------------------------------------------------------------------


def test_spec_tree_new_session_has_base_node(client):
    session_id = _create_session(client)
    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    # Nach Session-Erstellung existiert genau ein Basisknoten (leere Spec)
    assert len(body["versions"]) == 1
    node = body["versions"][0]
    assert node["version"] == "v1"
    assert node["parent_spec_id"] is None
    assert node["change_summary"] is None
    assert node["has_runs"] is False
    # Basisknoten ist gleichzeitig die aktive Spec
    assert body["active_spec_id"] == node["spec_id"]


# ---------------------------------------------------------------------------
# AC3: Einzelne Version → parent_spec_id: null
# ---------------------------------------------------------------------------


def test_spec_tree_single_version(client, settings):
    session_id = _create_session(client)
    _add_spec(settings, session_id)

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == session_id
    assert len(body["versions"]) == 1

    node = body["versions"][0]
    assert node["version"] == "v1"
    assert node["parent_spec_id"] is None
    assert "spec_id" in node
    assert "created_at" in node
    assert node["has_runs"] is False
    assert body["active_spec_id"] == node["spec_id"]


# ---------------------------------------------------------------------------
# AC1 + AC2: Mehrere Versionen → korrekte parent_spec_id-Kette
# ---------------------------------------------------------------------------


def test_spec_tree_multiple_versions(client, settings):
    session_id = _create_session(client)
    _add_spec(settings, session_id, steps=[])
    _add_spec(settings, session_id, steps=[{"type": "a"}])
    _add_spec(settings, session_id, steps=[{"type": "a"}, {"type": "b"}])

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    body = resp.json()
    versions = body["versions"]
    assert len(versions) == 3

    assert versions[0]["version"] == "v1"
    assert versions[0]["parent_spec_id"] is None

    assert versions[1]["version"] == "v2"
    assert versions[1]["parent_spec_id"] == versions[0]["spec_id"]

    assert versions[2]["version"] == "v3"
    assert versions[2]["parent_spec_id"] == versions[1]["spec_id"]

    # active_spec_id zeigt auf neueste Version
    assert body["active_spec_id"] == versions[2]["spec_id"]


# ---------------------------------------------------------------------------
# AC1: has_runs und last_run_status korrekt befüllt
# ---------------------------------------------------------------------------


def test_spec_tree_has_runs_and_last_run_status(client, settings):
    import uuid
    from datetime import datetime, timezone

    from gysi_ml.persistence import run_repository

    session_id = _create_session(client)
    spec = _add_spec(settings, session_id)
    spec_id = spec["spec_id"]

    run_id = str(uuid.uuid4())
    run_repository.create_run(
        session_id=session_id,
        run_id=run_id,
        spec_version=spec["version"],
        status="completed",
        started_at=datetime.now(timezone.utc).isoformat(),
        spec_id=spec_id,
        db_path=settings.db_path,
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    node = resp.json()["versions"][0]
    assert node["has_runs"] is True
    assert node["last_run_status"] == "completed"


# ---------------------------------------------------------------------------
# DV-2.4: last_run_id im VersionNode
# ---------------------------------------------------------------------------


def test_spec_tree_last_run_id_with_run(client, settings):
    """Spec mit 1 Run → last_run_id enthält run_id."""
    import uuid
    from datetime import datetime, timezone

    from gysi_ml.persistence import run_repository

    session_id = _create_session(client)
    spec = _add_spec(settings, session_id)
    spec_id = spec["spec_id"]

    run_id = str(uuid.uuid4())
    run_repository.create_run(
        session_id=session_id,
        run_id=run_id,
        spec_version=spec["version"],
        status="done",
        started_at=datetime.now(timezone.utc).isoformat(),
        spec_id=spec_id,
        db_path=settings.db_path,
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    node = resp.json()["versions"][0]
    assert node["last_run_id"] == run_id


def test_spec_tree_last_run_id_without_run(client, settings):
    """Spec ohne Run → last_run_id ist null."""
    session_id = _create_session(client)
    _add_spec(settings, session_id)

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    node = resp.json()["versions"][0]
    assert node["last_run_id"] is None


def test_spec_tree_last_run_id_is_last_run(client, settings):
    """Spec mit 2 Runs → last_run_id ist die run_id des letzten Runs."""
    import uuid
    from datetime import datetime, timezone

    from gysi_ml.persistence import run_repository

    session_id = _create_session(client)
    spec = _add_spec(settings, session_id)
    spec_id = spec["spec_id"]

    run_id_1 = str(uuid.uuid4())
    run_id_2 = str(uuid.uuid4())
    for rid in [run_id_1, run_id_2]:
        run_repository.create_run(
            session_id=session_id,
            run_id=rid,
            spec_version=spec["version"],
            status="done",
            started_at=datetime.now(timezone.utc).isoformat(),
            spec_id=spec_id,
            db_path=settings.db_path,
        )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    node = resp.json()["versions"][0]
    assert node["last_run_id"] == run_id_2


# ---------------------------------------------------------------------------
# AC5: HTTP 404 bei unbekannter Session
# ---------------------------------------------------------------------------


def test_spec_tree_404_unknown_session(client):
    resp = client.get("/v1/sessions/does-not-exist/spec/tree")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "SESSION_NOT_FOUND"
    assert "does-not-exist" in body["detail"]


# ---------------------------------------------------------------------------
# VT-1.1 AC8: phase-Feld — Modeling- vs. Preprocessing-Detection
# ---------------------------------------------------------------------------


def test_spec_tree_phase_preprocessing(client, settings):
    """Spec ohne Modeling-Steps → phase == 'preprocessing'."""
    session_id = _create_session(client)
    _add_spec(settings, session_id, steps=[{"type": "dedup", "enabled": True}])

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    # versions[-1] = neueste Version (die tatsächlich präprozessierte Spec)
    node = resp.json()["versions"][-1]
    assert node["phase"] == "preprocessing"


def test_spec_tree_phase_modeling_decision_tree(client, settings):
    """Spec mit train_decision_tree (enabled) → phase == 'modeling'."""
    session_id = _create_session(client)
    _add_spec(
        settings,
        session_id,
        steps=[
            {"type": "split", "enabled": True},
            {"type": "train_decision_tree", "enabled": True},
        ],
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    # versions[-1] = neueste Version (die Modeling-Steps enthält)
    node = resp.json()["versions"][-1]
    assert node["phase"] == "modeling"


def test_spec_tree_phase_modeling_disabled_step(client, settings):
    """Deaktivierter Modeling-Step zählt nicht → phase == 'preprocessing'."""
    session_id = _create_session(client)
    _add_spec(
        settings,
        session_id,
        steps=[{"type": "train_decision_tree", "enabled": False}],
    )

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    # versions[-1] = neueste Version (deaktivierter Modeling-Step → preprocessing)
    node = resp.json()["versions"][-1]
    assert node["phase"] == "preprocessing"


def test_spec_tree_phase_empty_spec(client, settings):
    """Leere Steps-Liste (Basisknoten) → phase == 'preprocessing'."""
    session_id = _create_session(client)
    # steps=[] entspricht dem Basisknoten (bereits durch create_session angelegt);
    # create_spec_version liefert ihn idempotent zurück, kein neuer Eintrag.
    _add_spec(settings, session_id, steps=[])

    resp = client.get(f"/v1/sessions/{session_id}/spec/tree")
    assert resp.status_code == 200
    # Nur der Basisknoten existiert
    assert len(resp.json()["versions"]) == 1
    node = resp.json()["versions"][-1]
    assert node["phase"] == "preprocessing"
