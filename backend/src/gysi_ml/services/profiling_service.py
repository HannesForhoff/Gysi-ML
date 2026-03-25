"""ProfilingService — Rohdatensatz-Profilierung (Story 7.1)."""
import functools

import pandas as pd

from gysi_ml.config import get_settings


class ProfilingService:
    def profile_raw(self) -> str:
        """Profiliert den Rohdatensatz. Ergebnis ist gecacht."""
        return _profile_raw_cached(self._get_data_path())

    def profile_after_steps(self, session_id: str, db_path: str | None = None) -> str:
        """Profiliert den Datensatz nach ausgeführten Preprocessing-Steps.

        Ermittelt Zeilen-Differenz aus dem letzten abgeschlossenen Run.
        Kein lru_cache — sessionspezifisch.
        """
        from gysi_ml.persistence import run_repository

        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        completed_runs = [r for r in runs if r["status"] == "completed"]

        if not completed_runs:
            return self.profile_raw()

        rows_before = _get_raw_row_count_cached(self._get_data_path())

        latest_run_id = completed_runs[-1]["run_id"]
        run_data = run_repository.get_run(latest_run_id, db_path=db_path)

        rows_after = rows_before  # Fallback
        if run_data and run_data.get("result"):
            result = run_data["result"]
            # Bevorzugter Schlüssel (kann in älteren Runs fehlen)
            rows_after = result.get("rows_after_preprocessing", rows_before)
            # Aus dedup-Metadaten ableiten wenn Schlüssel fehlt
            if rows_after == rows_before:
                removed = sum(
                    sr.get("metadata", {}).get("removed_duplicates", 0)
                    for sr in result.get("step_results", [])
                )
                rows_after = rows_before - removed

        diff = rows_before - rows_after
        comparison = (
            "**Vorher/Nachher:**\n"
            f"- Rohdatensatz: {rows_before:,} Zeilen\n"
            f"- Nach Preprocessing: {rows_after:,} Zeilen\n"
            f"- Differenz: {diff:,} Zeilen entfernt"
        )
        raw_profile = _profile_raw_cached(self._get_data_path())
        return f"{comparison}\n\n---\n\n{raw_profile}"

    def to_compact_str(self) -> str:
        """Kompakte Darstellung für LLM-Prompt-Injection."""
        return _compact_profile_cached(self._get_data_path())

    def _get_data_path(self) -> str:
        return get_settings().data_path


@functools.lru_cache(maxsize=1)
def _get_raw_row_count_cached(data_path: str) -> int:
    """Gecachte Zeilen-Anzahl des Rohdatensatzes. Konsistent mit _profile_raw_cached."""
    return len(pd.read_csv(data_path))


@functools.lru_cache(maxsize=1)
def _profile_raw_cached(data_path: str) -> str:
    """lru_cache auf Modulebene — einmal geladen, gilt für alle ProfilingService-Instanzen.

    maxsize=1: Gysi verwendet einen einzigen Bike-Datensatz pro Deployment. Bei mehreren
    verschiedenen data_path-Werten würde der Cache jeweils den vorherigen Eintrag verdrängen.
    Für Multi-Datensatz-Szenarien auf maxsize=None erhöhen.
    """
    df = pd.read_csv(data_path)
    return _format_profile(df)


@functools.lru_cache(maxsize=1)
def _compact_profile_cached(data_path: str) -> str:
    """Kompakte Profil-Zusammenfassung für LLM-Prompt-Injection. Gecacht wie _profile_raw_cached."""
    df = pd.read_csv(data_path)
    rows, cols = df.shape
    missing = df.isnull().sum()
    missing_cols = missing[missing > 0]
    num_cols = df.select_dtypes(include="number").columns.tolist()

    lines = [
        f"Datensatz: {rows} Zeilen × {cols} Spalten",
        f"Numerische Spalten ({len(num_cols)}): {', '.join(num_cols[:8])}{'...' if len(num_cols) > 8 else ''}",
    ]
    if not missing_cols.empty:
        top3 = missing_cols.head(3)
        missing_str = ", ".join(f"{c} ({n})" for c, n in top3.items())
        lines.append(f"Fehlende Werte: {missing_str}")
    else:
        lines.append("Fehlende Werte: keine")

    if "cnt" in df.columns:
        corr = df[num_cols].corr()["cnt"].drop("cnt", errors="ignore").abs().sort_values(ascending=False)
        top_corr = corr.head(5)
        corr_str = ", ".join(f"{c} ({v:.2f})" for c, v in top_corr.items())
        lines.append(f"Stärkste Korrelationen mit 'cnt': {corr_str}")

    return "\n".join(lines)


def _format_profile(df: pd.DataFrame) -> str:
    lines = []

    # 1. Grundinfos
    lines.append(f"## Datensatz-Überblick\n")
    lines.append(f"**Zeilen:** {len(df):,}  |  **Spalten:** {len(df.columns)}\n")

    # 2. Spalten-Übersicht
    lines.append("### Spalten-Übersicht")
    col_info = []
    for col in df.columns:
        non_null = df[col].notna().sum()
        col_info.append(f"- `{col}`: {df[col].dtype}, {non_null}/{len(df)} Non-Null")
    lines.append("\n".join(col_info))

    # 3. Fehlende Werte
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if not missing.empty:
        lines.append("\n### Fehlende Werte")
        for col, count in missing.items():
            pct = count / len(df) * 100
            lines.append(f"- `{col}`: {count} ({pct:.1f}%)")
    else:
        lines.append("\n### Fehlende Werte\nKeine fehlenden Werte ✅")

    # 4. Statistiken (numerische Spalten)
    num_cols = df.select_dtypes(include="number")
    if not num_cols.empty:
        lines.append("\n### Statistiken (numerische Spalten)")
        desc = num_cols.describe().T[["min", "max", "mean", "50%", "std"]]
        desc.columns = ["Min", "Max", "Mean", "Median", "Std"]
        lines.append(desc.to_string())

    # 5. Erste 5 Zeilen
    lines.append("\n### Erste 5 Zeilen")
    lines.append(df.head(5).to_string())

    # 6. Kardinalität
    lines.append("\n### Unique-Werte (Kardinalität)")
    for col in df.columns:
        n_unique = df[col].nunique()
        lines.append(f"- `{col}`: {n_unique} unique Werte")

    return "\n".join(lines)
