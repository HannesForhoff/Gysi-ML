"""Unit-Tests für artifact_repository (Story 2.2)."""
import pytest

from gysi_ml.persistence.artifact_repository import (
    create_artifact,
    get_artifact,
    get_artifacts_for_run,
)
from gysi_ml.persistence.schema import create_all_tables


@pytest.fixture
def db(tmp_path):
    """Frische SQLite-DB pro Test."""
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


def test_create_and_get_artifact(db):
    create_artifact(
        artifact_id="art-1",
        run_id="run-1",
        artifact_type="feature_importance",
        file_path="/tmp/feature_importance_run-1.png",
        created_at="2026-01-01T00:00:00+00:00",
        db_path=db,
    )
    record = get_artifact("art-1", db_path=db)
    assert record is not None
    assert record["artifact_id"] == "art-1"
    assert record["run_id"] == "run-1"
    assert record["type"] == "feature_importance"
    assert record["file_path"] == "/tmp/feature_importance_run-1.png"
    assert record["created_at"] == "2026-01-01T00:00:00+00:00"


def test_get_artifact_not_found(db):
    result = get_artifact("does-not-exist", db_path=db)
    assert result is None


def test_get_artifacts_for_run(db):
    create_artifact(
        artifact_id="art-a",
        run_id="run-x",
        artifact_type="feature_importance",
        file_path="/tmp/a.png",
        created_at="2026-01-01T00:00:00+00:00",
        db_path=db,
    )
    create_artifact(
        artifact_id="art-b",
        run_id="run-x",
        artifact_type="feature_importance",
        file_path="/tmp/b.png",
        created_at="2026-01-01T00:01:00+00:00",
        db_path=db,
    )
    results = get_artifacts_for_run("run-x", db_path=db)
    assert len(results) == 2
    ids = {r["artifact_id"] for r in results}
    assert ids == {"art-a", "art-b"}


def test_get_artifacts_for_run_empty(db):
    results = get_artifacts_for_run("no-such-run", db_path=db)
    assert results == []
