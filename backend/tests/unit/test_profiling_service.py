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
    assert "Spalten-Übersicht" in result         # Spalten
    assert "Statistiken" in result               # Numerische Statistiken
    assert "Erste 5 Zeilen" in result            # Head
    assert "Unique-Werte" in result              # Kardinalität
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


def test_command_service_overview_routes_correctly(sample_csv):
    """AC 4 (Story 6.2): CommandService._handle_overview() delegiert immer an profile_raw()."""
    from gysi_ml.services.command_service import CommandService

    svc = CommandService()

    # Immer profile_raw() — unabhängig von vorhandenen Runs
    with patch("gysi_ml.services.profiling_service.get_settings") as mock_settings:
        mock_settings.return_value.data_path = sample_csv
        result = svc._handle_overview("sess-test", None)

    expected_raw = _ps_module._profile_raw_cached(sample_csv)
    assert result == expected_raw


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
