"""Unit-Tests für ProfilingService (Story 7.1)."""
import textwrap
from unittest.mock import patch

import pandas as pd
import pytest

# Cache vor jedem Test leeren (lru_cache auf Modulebene bleibt sonst erhalten)
import gysi_ml.services.profiling_service as _ps_module


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Stellt sicher, dass der lru_cache vor jedem Test geleert wird."""
    _ps_module._profile_raw_cached.cache_clear()
    _ps_module._get_raw_row_count_cached.cache_clear()
    yield
    _ps_module._profile_raw_cached.cache_clear()
    _ps_module._get_raw_row_count_cached.cache_clear()


@pytest.fixture
def sample_csv(tmp_path) -> str:
    """Erstellt ein kleines Test-CSV und gibt den Pfad zurück."""
    csv_content = textwrap.dedent("""\
        season,temp,hum,cnt
        1,0.24,0.81,985
        2,0.40,0.55,1234
        3,0.60,0.40,2000
        1,,0.70,500
    """)
    csv_file = tmp_path / "test_bikes.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


# ---------------------------------------------------------------------------
# AC 1: Vollständiges Profiling-Ergebnis
# ---------------------------------------------------------------------------

def test_profile_raw_contains_all_sections(sample_csv):
    """profile_raw() gibt einen String mit allen Pflicht-Abschnitten zurück."""
    result = _ps_module._profile_raw_cached(sample_csv)

    assert isinstance(result, str)
    assert "Datensatz-Überblick" in result       # Grundinfos
    assert "### Spalten" in result               # Spalten-Tabelle
    assert "Statistiken" in result               # Numerische Statistiken
    assert "Erste 5 Zeilen" in result            # Head
    assert "Unique" in result                    # Kardinalität-Spaltenheader
    # Fehlende Werte: temp hat 1 fehlenden Wert
    assert "Fehlende Werte" in result
    assert "temp" in result


def test_profile_raw_returns_row_and_column_count(sample_csv):
    """Grundinfos enthalten korrekte Zeilen-/Spaltenzahl."""
    result = _ps_module._profile_raw_cached(sample_csv)

    assert "**Zeilen:** 4" in result   # exakt 4 Zeilen
    assert "**Spalten:** 4" in result  # exakt 4 Spalten (season, temp, hum, cnt)


def test_profile_raw_contains_numeric_statistics(sample_csv):
    """Statistiken-Abschnitt enthält Min, Max, Mean, Median, Std."""
    result = _ps_module._profile_raw_cached(sample_csv)

    assert "Min" in result
    assert "Max" in result
    assert "Mean" in result
    assert "Median" in result
    assert "Std" in result


# ---------------------------------------------------------------------------
# AC 2: lru_cache — kein doppeltes Laden
# ---------------------------------------------------------------------------

def test_profile_raw_cache_reads_csv_only_once(sample_csv):
    """Zweimaliger Aufruf mit gleichem data_path liest CSV nur einmal."""
    with patch("gysi_ml.services.profiling_service.pd.read_csv", wraps=pd.read_csv) as mock_read:
        from gysi_ml.services.profiling_service import ProfilingService

        # Ersten Aufruf machen
        result1 = _ps_module._profile_raw_cached(sample_csv)
        # Zweiten Aufruf mit gleichem Pfad — sollte gecacht sein
        result2 = _ps_module._profile_raw_cached(sample_csv)

    assert mock_read.call_count == 1, "pd.read_csv soll nur einmal aufgerufen werden (lru_cache)"
    assert result1 == result2


def test_profile_raw_cache_different_paths_read_separately(sample_csv, tmp_path):
    """Zwei verschiedene Pfade erzeugen zwei separate Cache-Einträge."""
    csv2_content = "a,b\n1,2\n3,4\n"
    csv2 = tmp_path / "other.csv"
    csv2.write_text(csv2_content)

    with patch("gysi_ml.services.profiling_service.pd.read_csv", wraps=pd.read_csv) as mock_read:
        _ps_module._profile_raw_cached(sample_csv)
        _ps_module._profile_raw_cached(str(csv2))

    assert mock_read.call_count == 2, "Verschiedene Pfade erzeugen separate Cache-Lese-Aufrufe"


# ---------------------------------------------------------------------------
# AC 3: Cold Start toleriert
# ---------------------------------------------------------------------------

def test_profile_raw_no_exception_on_cold_start(sample_csv):
    """Erster Aufruf (cold start) wirft keinen Fehler."""
    from gysi_ml.services.profiling_service import ProfilingService

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings:
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()
        result = svc.profile_raw()

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# AC 5: Keine Spec-Änderung
# ---------------------------------------------------------------------------

def test_profile_raw_returns_string_no_side_effects(sample_csv):
    """profile_raw() gibt String zurück und verändert keine Spec (kein Exception)."""
    from gysi_ml.services.profiling_service import ProfilingService

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings:
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()

        result = svc.profile_raw()

    assert isinstance(result, str)
    # Kein Pipeline-Spec-Objekt zurückgegeben
    assert not isinstance(result, dict)
    assert not isinstance(result, list)


# ---------------------------------------------------------------------------
# Story 7.3: profile_after_steps — AC 1, 2, 3, 4, 5
# ---------------------------------------------------------------------------

def test_profile_after_steps_no_runs_fallback(sample_csv):
    """AC 2: Keine completed Runs → gibt gleichen Output wie profile_raw()."""
    from gysi_ml.services.profiling_service import ProfilingService
    import gysi_ml.persistence.run_repository as _run_repo

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_run_repo, "get_runs_for_session", return_value=[]):
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()
        result = svc.profile_after_steps(session_id="sess-no-runs")

    expected = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected


def test_profile_after_steps_with_runs(sample_csv):
    """AC 1: Completed Run mit dedup-Ergebnis → enthält Vorher/Nachher-Vergleich."""
    from gysi_ml.services.profiling_service import ProfilingService
    import gysi_ml.persistence.run_repository as _run_repo

    run_result = {
        "step_results": [{"step_type": "dedup", "metadata": {"removed_duplicates": 1}}],
        "metrics": {},
        "artifacts": [],
    }
    mock_run_full = {"run_id": "run-xyz", "status": "completed", "result": run_result}

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_run_repo, "get_runs_for_session",
                      return_value=[{"run_id": "run-xyz", "status": "completed"}]), \
         patch.object(_run_repo, "get_run", return_value=mock_run_full):
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()
        result = svc.profile_after_steps(session_id="sess-with-runs")

    assert "Vorher/Nachher" in result
    assert "Rohdatensatz" in result
    assert "Nach Preprocessing" in result
    # sample_csv hat 4 Zeilen, 1 entfernt → 3 verbleibend
    assert "Rohdatensatz: 4 Zeilen" in result
    assert "Nach Preprocessing: 3 Zeilen" in result


def test_profile_after_steps_run_data_none(sample_csv):
    """L2: Fallback wenn get_run() None zurückgibt → diff=0, kein Fehler."""
    from gysi_ml.services.profiling_service import ProfilingService
    import gysi_ml.persistence.run_repository as _run_repo

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_run_repo, "get_runs_for_session",
                      return_value=[{"run_id": "run-xyz", "status": "completed"}]), \
         patch.object(_run_repo, "get_run", return_value=None):
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()
        result = svc.profile_after_steps(session_id="sess-run-none")

    assert "Vorher/Nachher" in result
    assert "Differenz: 0 Zeilen entfernt" in result


def test_command_service_overview_calls_profile_current(sample_csv):
    """AC 4 (Story 6.2 updated): CommandService._handle_overview() delegiert an profile_current()."""
    from gysi_ml.services.command_service import CommandService
    from gysi_ml.services.profiling_service import ProfilingService

    svc = CommandService()

    with patch.object(ProfilingService, "profile_current", return_value="## Verarbeiteter Datensatz\nFoo") as mock_current:
        result = svc._handle_overview("sess-test", None)

    mock_current.assert_called_once_with(session_id="sess-test", db_path=None)
    assert "Datensatz" in result


# ---------------------------------------------------------------------------
# profile_current — Fallback, Train-CSV, Snapshot
# ---------------------------------------------------------------------------

def test_profile_current_no_runs_falls_back_to_raw(sample_csv):
    """Keine abgeschlossenen Runs für aktuelle Spec → Fallback auf profile_raw()."""
    from gysi_ml.services.profiling_service import ProfilingService
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo

    mock_spec = {"spec_id": "spec-111", "version": "v1"}

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec), \
         patch.object(_run_repo, "get_runs_for_session", return_value=[]):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = "/nonexistent"
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    expected = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected


def test_profile_current_after_rollback_shows_target_artifacts(tmp_path, sample_csv):
    """Rollback v2→v1 erzeugt v3: profile_current soll die Artefakte des v1-Runs zeigen."""
    import textwrap
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo
    from gysi_ml.services.profiling_service import ProfilingService

    v1_spec_id = "spec-v1"
    v3_spec_id = "spec-v3-rollback"  # neue spec_id nach Rollback

    # v1-Artefakt (Train-CSV) existiert auf Disk
    v1_run_id = "run-v1"
    train_csv = tmp_path / f"{v1_run_id}_train.csv"
    train_csv.write_text(textwrap.dedent("""\
        season,temp,cnt
        1,0.24,100
        2,0.40,200
        3,0.60,300
    """))

    # Aktuelle Spec ist v3, hat change_summary "Rollback auf v1"
    mock_spec_v3 = {"spec_id": v3_spec_id, "version": "v3", "change_summary": "Rollback auf v1"}
    mock_runs = [
        {"run_id": v1_run_id, "status": "completed", "spec_version": "v1", "spec_id": v1_spec_id},
        {"run_id": "run-v2", "status": "completed", "spec_version": "v2", "spec_id": "spec-v2"},
        # kein Run für v3_spec_id
    ]

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec_v3), \
         patch.object(_spec_repo, "get_spec_id_by_version", return_value=v1_spec_id), \
         patch.object(_run_repo, "get_runs_for_session", return_value=mock_runs):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = str(tmp_path)
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    assert "Train-Split" in result
    assert "**Zeilen:** 3" in result   # v1-Train-CSV hat 3 Zeilen
    # Versionslabel der v1-Run-Artefakte (v1) wird zusammen mit dem Rollback angezeigt
    assert "v1" in result


def test_profile_current_after_rollback_falls_back_to_raw_when_target_has_no_run(sample_csv):
    """Rollback auf Version ohne Run → Fallback auf profile_raw()."""
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo
    from gysi_ml.services.profiling_service import ProfilingService

    mock_spec = {"spec_id": "spec-v3", "version": "v3", "change_summary": "Rollback auf v1"}
    # v1 hat keinen Run
    mock_runs = [{"run_id": "run-v2", "status": "completed", "spec_version": "v2", "spec_id": "spec-v2"}]

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec), \
         patch.object(_spec_repo, "get_spec_id_by_version", return_value="spec-v1"), \
         patch.object(_run_repo, "get_runs_for_session", return_value=mock_runs):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = "/nonexistent"
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    expected = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected


def test_profile_current_no_spec_falls_back_to_raw(sample_csv):
    """Keine Spec in der Session → Fallback auf profile_raw()."""
    from gysi_ml.services.profiling_service import ProfilingService
    import gysi_ml.persistence.spec_repository as _spec_repo

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=None):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = "/nonexistent"
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    expected = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected


def test_profile_current_uses_train_csv_when_available(tmp_path, sample_csv):
    """Wenn _train.csv existiert → dessen Daten werden gezeigt."""
    import textwrap
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo
    from gysi_ml.services.profiling_service import ProfilingService

    run_id = "run-abc"
    spec_id = "spec-abc"
    train_csv = tmp_path / f"{run_id}_train.csv"
    train_csv.write_text(textwrap.dedent("""\
        season,temp,cnt
        1,0.24,100
        2,0.40,200
    """))

    mock_spec = {"spec_id": spec_id, "version": "v2"}
    mock_runs = [{"run_id": run_id, "status": "completed", "spec_version": "v2", "spec_id": spec_id}]

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec), \
         patch.object(_run_repo, "get_runs_for_session", return_value=mock_runs):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = str(tmp_path)
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    assert "v2" in result
    assert "Train-Split" in result
    assert "**Zeilen:** 2" in result  # train CSV hat 2 Zeilen


def test_profile_current_uses_snapshot_when_no_train_csv(tmp_path, sample_csv):
    """Wenn kein _train.csv, aber _snapshot.parquet existiert → Snapshot wird verwendet."""
    import pandas as pd
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo
    from gysi_ml.services.profiling_service import ProfilingService

    run_id = "run-def"
    spec_id = "spec-def"
    df_snap = pd.DataFrame({"season": [1, 2, 3], "temp": [0.1, 0.2, 0.3]})
    snap_path = tmp_path / f"{run_id}_snapshot.parquet"
    df_snap.to_parquet(snap_path, index=False)

    mock_spec = {"spec_id": spec_id, "version": "v1"}
    mock_runs = [{"run_id": run_id, "status": "completed", "spec_version": "v1", "spec_id": spec_id}]

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec), \
         patch.object(_run_repo, "get_runs_for_session", return_value=mock_runs):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = str(tmp_path)
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    assert "v1" in result
    assert "Train-Split" not in result
    assert "**Zeilen:** 3" in result  # Snapshot hat 3 Zeilen


def test_profile_current_falls_back_when_no_artifacts(tmp_path, sample_csv):
    """Completed Run für aktuelle Spec, aber keine Artefakt-Dateien → Fallback auf profile_raw()."""
    import gysi_ml.persistence.run_repository as _run_repo
    import gysi_ml.persistence.spec_repository as _spec_repo
    from gysi_ml.services.profiling_service import ProfilingService

    spec_id = "spec-ghi"
    mock_spec = {"spec_id": spec_id, "version": "v1"}
    mock_runs = [{"run_id": "run-ghi", "status": "completed", "spec_version": "v1", "spec_id": spec_id}]

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings, \
         patch.object(_spec_repo, "get_latest_spec", return_value=mock_spec), \
         patch.object(_run_repo, "get_runs_for_session", return_value=mock_runs):
        mock_settings.return_value.data_path = sample_csv
        mock_settings.return_value.artifacts_path = str(tmp_path)  # leer
        svc = ProfilingService()
        result = svc.profile_current(session_id="s1", db_path=None)

    expected = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected


# ---------------------------------------------------------------------------
# Story 7.2 — to_compact_str()
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_compact_cache():
    """Leert auch den compact-Cache vor jedem Test."""
    _ps_module._compact_profile_cached.cache_clear()
    yield
    _ps_module._compact_profile_cached.cache_clear()


def test_compact_str_contains_row_col_info(sample_csv):
    """to_compact_str() enthält Zeilen × Spalten-Info."""
    result = _ps_module._compact_profile_cached(sample_csv)
    assert "Zeilen" in result
    assert "Spalten" in result
    assert "4" in result  # 4 Zeilen im sample_csv


def test_compact_str_contains_numeric_cols(sample_csv):
    """to_compact_str() listet numerische Spalten auf."""
    result = _ps_module._compact_profile_cached(sample_csv)
    assert "Numerische Spalten" in result
    assert "temp" in result or "season" in result


def test_compact_str_contains_missing_info(sample_csv):
    """to_compact_str() zeigt fehlende Werte (temp hat 1 NaN in sample_csv)."""
    result = _ps_module._compact_profile_cached(sample_csv)
    assert "Fehlende Werte" in result
    assert "temp" in result


def test_compact_str_contains_correlation_with_cnt(sample_csv):
    """to_compact_str() enthält Korrelations-Info wenn 'cnt' vorhanden."""
    result = _ps_module._compact_profile_cached(sample_csv)
    assert "cnt" in result
    assert "Korrelation" in result


def test_compact_str_via_service_method(sample_csv):
    """ProfilingService.to_compact_str() delegiert korrekt an _compact_profile_cached."""
    from gysi_ml.services.profiling_service import ProfilingService

    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings:
        mock_settings.return_value.data_path = sample_csv
        svc = ProfilingService()
        result = svc.to_compact_str()

    assert isinstance(result, str)
    assert len(result) > 0
    assert "Zeilen" in result
