"""Unit-Tests für SnapshotService (Story DV-1.1)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from gysi_ml.services.snapshot_service import SnapshotService, _compute_column_stats


@pytest.fixture()
def simple_df() -> pd.DataFrame:
    return pd.DataFrame({
        "age": [10, 20, 30, 40, 50],
        "score": [1.1, 2.2, 3.3, 4.4, 5.5],
        "label": ["a", "b", "a", "c", "b"],
    })


def test_save_snapshot_creates_parquet(tmp_path, simple_df):
    service = SnapshotService()
    service.save_snapshot(
        run_id="test-run-1",
        df=simple_df,
        is_split=False,
        artifacts_path=str(tmp_path),
    )
    parquet_file = tmp_path / "test-run-1_snapshot.parquet"
    assert parquet_file.exists()
    loaded = pd.read_parquet(parquet_file)
    assert list(loaded.columns) == list(simple_df.columns)
    assert len(loaded) == len(simple_df)


def test_save_snapshot_creates_column_stats_json(tmp_path, simple_df):
    service = SnapshotService()
    service.save_snapshot(
        run_id="test-run-2",
        df=simple_df,
        is_split=False,
        artifacts_path=str(tmp_path),
    )
    stats_file = tmp_path / "test-run-2_column_stats.json"
    assert stats_file.exists()
    data = json.loads(stats_file.read_text(encoding="utf-8"))
    assert "is_split" in data
    assert data["is_split"] is False


def test_column_stats_numeric_fields(simple_df):
    stats = _compute_column_stats(simple_df, is_split=False)
    age_stats = stats["columns"]["age"]
    assert age_stats["min"] is not None
    assert age_stats["max"] is not None
    assert age_stats["histogram"] is not None
    assert len(age_stats["histogram"]["bins"]) == 11
    assert len(age_stats["histogram"]["counts"]) == 10


def test_column_stats_missing_values():
    df = pd.DataFrame({"val": [1.0, 2.0, None, 4.0, None]})
    stats = _compute_column_stats(df, is_split=False)
    col = stats["columns"]["val"]
    assert col["missing_count"] == 2
    assert col["missing_pct"] == pytest.approx(40.0, rel=1e-4)


def test_column_stats_is_split_true(tmp_path):
    df = pd.DataFrame({"x": [1, 2, 3]})
    service = SnapshotService()
    service.save_snapshot(
        run_id="split-run",
        df=df,
        is_split=True,
        artifacts_path=str(tmp_path),
    )
    data = json.loads((tmp_path / "split-run_column_stats.json").read_text(encoding="utf-8"))
    assert data["is_split"] is True


def test_column_stats_non_numeric_column(simple_df):
    stats = _compute_column_stats(simple_df, is_split=False)
    label_stats = stats["columns"]["label"]
    assert label_stats["min"] is None
    assert label_stats["max"] is None
    assert label_stats["histogram"] is None


def test_save_snapshot_creates_artifacts_dir(tmp_path):
    nested_path = tmp_path / "deep" / "nested" / "artifacts"
    assert not nested_path.exists()
    df = pd.DataFrame({"n": [1, 2, 3]})
    service = SnapshotService()
    service.save_snapshot(
        run_id="dir-test",
        df=df,
        is_split=False,
        artifacts_path=str(nested_path),
    )
    assert nested_path.exists()
    assert (nested_path / "dir-test_snapshot.parquet").exists()
