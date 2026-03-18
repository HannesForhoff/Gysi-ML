"""Unit-Tests fuer PipelineExecutor mit Dummy-Steps und In-Memory-SQLite."""
import pandas as pd
import pytest

from gysi_ml.executor.executor import PipelineExecutor
from gysi_ml.persistence.schema import create_all_tables
from gysi_ml.steps.base import BaseStep
from gysi_ml.steps.registry import _registry, register_step


@pytest.fixture(autouse=True)
def clean_registry():
    original = dict(_registry)
    yield
    _registry.clear()
    _registry.update(original)


@pytest.fixture
def db(tmp_path):
    db_file = str(tmp_path / "test.db")
    create_all_tables(db_file)
    return db_file


@pytest.fixture
def csv_file(tmp_path):
    """Erstellt eine minimale bikes.csv fuer Tests."""
    df = pd.DataFrame({
        "instant": [1, 2, 3, 4, 5],
        "dteday": ["2011-01-01"] * 5,
        "cnt": [985, 801, 1349, 1562, 1600],
    })
    path = tmp_path / "bikes.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def executor(csv_file):
    return PipelineExecutor(data_path=csv_file)


def _register_dummy():
    @register_step("dummy")
    class DummyStep(BaseStep):
        description = "Test step"
        param_schema = {}

        def fit(self, df_train):
            pass

        def transform(self, df_train, df_test):
            return df_train, df_test

    return DummyStep


# ---------------------------------------------------------------------------
# Gültige Spec
# ---------------------------------------------------------------------------


def test_execute_empty_steps(executor, db):
    result = executor.execute(spec={"steps": []}, session_id="s1", db_path=db)
    assert result["status"] == "completed"
    assert "run_id" in result
    assert result["result"]["step_results"] == []


def test_execute_with_dummy_step(executor, db):
    _register_dummy()
    spec = {"steps": [{"type": "dummy", "params": {}, "enabled": True}]}
    result = executor.execute(spec=spec, session_id="s1", db_path=db)
    assert result["status"] == "completed"
    assert len(result["result"]["step_results"]) == 1
    assert result["result"]["step_results"][0]["step_type"] == "dummy"


def test_execute_skips_disabled_step(executor, db):
    _register_dummy()
    spec = {"steps": [{"type": "dummy", "enabled": False}]}
    result = executor.execute(spec=spec, session_id="s1", db_path=db)
    assert result["status"] == "completed"
    assert result["result"]["step_results"] == []


# ---------------------------------------------------------------------------
# Unbekannter Step-Typ
# ---------------------------------------------------------------------------


def test_execute_unknown_step_type_returns_error(executor, db):
    spec = {"steps": [{"type": "nonexistent_step"}]}
    result = executor.execute(spec=spec, session_id="s1", db_path=db)
    assert result["error"] == "unknown_step_type"
    assert result["code"] == "UNKNOWN_STEP_TYPE"


def test_execute_unknown_step_persists_failed_run(executor, db):
    from gysi_ml.persistence.database import get_connection

    spec = {"steps": [{"type": "not_registered"}]}
    executor.execute(spec=spec, session_id="s1", db_path=db)

    conn = get_connection(db)
    cursor = conn.execute("SELECT status FROM runs LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    assert row["status"] == "failed"


# ---------------------------------------------------------------------------
# Ungültige Spec
# ---------------------------------------------------------------------------


def test_execute_invalid_spec_returns_error(executor, db):
    result = executor.execute(spec={"no_steps_key": []}, session_id="s1", db_path=db)
    assert result["error"] == "invalid_spec"
    assert result["code"] == "INVALID_SPEC"


def test_execute_invalid_spec_does_not_create_run(executor, db):
    from gysi_ml.persistence.database import get_connection

    executor.execute(spec={}, session_id="s1", db_path=db)
    conn = get_connection(db)
    cursor = conn.execute("SELECT COUNT(*) as c FROM runs")
    count = cursor.fetchone()["c"]
    conn.close()
    assert count == 0


# ---------------------------------------------------------------------------
# Persistenz nach Erfolg
# ---------------------------------------------------------------------------


def test_execute_persists_completed_run(executor, db):
    from gysi_ml.persistence.database import get_connection

    result = executor.execute(spec={"steps": []}, session_id="s1", db_path=db)
    run_id = result["run_id"]

    conn = get_connection(db)
    cursor = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()

    assert row["status"] == "completed"
    assert row["started_at"] is not None
    assert row["finished_at"] is not None
    assert row["spec_version"] == "v1"


def test_execute_persists_spec_version(executor, db):
    from gysi_ml.persistence.database import get_connection

    executor.execute(spec={"steps": []}, session_id="s1", db_path=db)

    conn = get_connection(db)
    cursor = conn.execute("SELECT * FROM spec_versions WHERE session_id = ?", ("s1",))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["version"] == "v1"


# ---------------------------------------------------------------------------
# Step-Exception → failed run
# ---------------------------------------------------------------------------


def test_execute_step_exception_marks_run_failed(executor, db):
    from gysi_ml.persistence.database import get_connection

    @register_step("failing_step")
    class FailingStep(BaseStep):
        def fit(self, df_train):
            raise RuntimeError("Absichtlicher Fehler")

        def transform(self, df_train, df_test):
            return df_train, df_test

    spec = {"steps": [{"type": "failing_step"}]}
    result = executor.execute(spec=spec, session_id="s1", db_path=db)
    assert result["error"] == "step_execution_failed"

    conn = get_connection(db)
    cursor = conn.execute("SELECT status, error_message FROM runs LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    assert row["status"] == "failed"
    assert "Absichtlicher Fehler" in row["error_message"]


# ---------------------------------------------------------------------------
# execute_with_spec_id (Story 4.1)
# ---------------------------------------------------------------------------


def test_execute_with_spec_id_invalid_order_returns_error(executor, db):
    """execute_with_spec_id mit ungültiger Step-Reihenfolge → error."""
    spec = {"steps": [
        {"type": "train_decision_tree", "params": {}},
        {"type": "split", "params": {"test_size": 0.2}},
    ]}
    result = executor.execute_with_spec_id(
        spec=spec, spec_id="spec-1", session_id="s1", db_path=db,
    )
    assert result["error"] == "invalid_spec_order"
    assert result["code"] == "INVALID_SPEC_ORDER"
