"""ProfilingService — Rohdatensatz-Profilierung (Story 7.1)."""
import functools
import os

import pandas as pd

from gysi_ml.config import get_settings


class ProfilingService:
    def profile_raw(self) -> str:
        """Profiliert den Rohdatensatz. Ergebnis ist gecacht."""
        return _profile_raw_cached(self._get_data_path())

    def profile_current(self, session_id: str, db_path: str | None = None) -> str:
        """Profiliert den aktuell verarbeiteten Datensatz nach dem letzten abgeschlossenen Run.

        Berücksichtigt nur Runs, die zur aktuellen Spec-Version gehören.
        Nach einem Rollback (neue Spec, noch kein Run) wird auf profile_raw() zurückgefallen.

        Priorität:
        1. Post-Split Train-CSV  ({run_id}_train.csv)    — spiegelt alle Transformationen wider
        2. Pre-Split Snapshot    ({run_id}_snapshot.parquet) — für Pipelines ohne Split
        3. Fallback              → profile_raw()

        Kein lru_cache — sessionspezifisch.
        """
        from gysi_ml.persistence import run_repository, spec_repository

        current_spec = spec_repository.get_latest_spec(session_id=session_id, db_path=db_path)
        if current_spec is None:
            return self.profile_raw()

        current_spec_id = current_spec["spec_id"]

        runs = run_repository.get_runs_for_session(session_id=session_id, db_path=db_path)
        completed_runs = [
            r for r in runs
            if r["status"] == "completed" and r.get("spec_id") == current_spec_id
        ]

        if not completed_runs:
            # Rollback-Fall: neue Spec hat noch keinen Run.
            # change_summary enthält "Rollback auf vX" → Artefakte der Original-Version verwenden.
            change_summary = current_spec.get("change_summary") or ""
            if change_summary.startswith("Rollback auf "):
                target_version = change_summary.removeprefix("Rollback auf ")
                target_spec_id = spec_repository.get_spec_id_by_version(
                    session_id=session_id, version=target_version, db_path=db_path
                )
                if target_spec_id:
                    completed_runs = [
                        r for r in runs
                        if r["status"] == "completed" and r.get("spec_id") == target_spec_id
                    ]

        if not completed_runs:
            return self.profile_raw()

        latest = completed_runs[-1]
        run_id = latest["run_id"]
        version = latest.get("spec_version", "?")
        artifacts_path = get_settings().artifacts_path

        train_path = os.path.join(artifacts_path, f"{run_id}_train.csv")
        if os.path.exists(train_path):
            df = pd.read_csv(train_path)
            header = f"## Verarbeiteter Datensatz — {version} (Train-Split)\n"
            return header + "\n" + _format_profile(df)

        snapshot_path = os.path.join(artifacts_path, f"{run_id}_snapshot.parquet")
        if os.path.exists(snapshot_path):
            df = pd.read_parquet(snapshot_path)
            header = f"## Verarbeiteter Datensatz — {version}\n"
            return header + "\n" + _format_profile(df)

        return self.profile_raw()

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


def _df_to_md_table(df: pd.DataFrame) -> str:
    """Konvertiert einen DataFrame in eine Markdown-Tabelle."""
    headers = list(df.columns)
    index_name = df.index.name or ""
    # Header-Zeile mit Index
    header_row = "| " + index_name + " | " + " | ".join(headers) + " |"
    sep_row = "| " + " | ".join(["---"] * (len(headers) + 1)) + " |"
    rows = []
    for idx, row in df.iterrows():
        cells = [str(idx)] + [str(v) for v in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header_row, sep_row] + rows)


def _format_profile(df: pd.DataFrame) -> str:
    lines = []

    # 1. Grundinfos
    lines.append("## Datensatz-Überblick")
    lines.append("")
    lines.append(f"**Zeilen:** {len(df):,} &nbsp;|&nbsp; **Spalten:** {len(df.columns)}")
    lines.append("")

    # 2. Spalten-Übersicht als Tabelle
    lines.append("### Spalten")
    lines.append("")
    missing_counts = df.isnull().sum()
    col_rows = []
    for col in df.columns:
        non_null = df[col].notna().sum()
        n_missing = missing_counts[col]
        pct_missing = f"{n_missing / len(df) * 100:.1f}%" if n_missing > 0 else "—"
        n_unique = df[col].nunique()
        col_rows.append(f"| `{col}` | {df[col].dtype} | {non_null:,} | {n_missing:,} ({pct_missing}) | {n_unique:,} |")

    lines.append("| Spalte | Typ | Non-Null | Fehlend | Unique |")
    lines.append("| --- | --- | --- | --- | --- |")
    lines.extend(col_rows)
    lines.append("")

    # 3. Fehlende Werte — nur wenn vorhanden
    missing = missing_counts[missing_counts > 0].sort_values(ascending=False)
    if missing.empty:
        lines.append("**Fehlende Werte:** keine ✅")
    else:
        lines.append(f"**Fehlende Werte:** {len(missing)} Spalte(n) betroffen")
    lines.append("")

    # 4. Statistiken (numerische Spalten) als Tabelle
    num_cols = df.select_dtypes(include="number")
    if not num_cols.empty:
        lines.append("### Statistiken (numerische Spalten)")
        lines.append("")
        desc = num_cols.describe().T[["min", "max", "mean", "50%", "std"]]
        desc.columns = ["Min", "Max", "Mean", "Median", "Std"]
        desc = desc.round(2)
        desc.index.name = "Spalte"
        lines.append(_df_to_md_table(desc))
        lines.append("")

    # 5. Erste 5 Zeilen als Tabelle
    lines.append("### Erste 5 Zeilen")
    lines.append("")
    preview = df.head(5).reset_index(drop=True)
    preview.index.name = "#"
    lines.append(_df_to_md_table(preview))

    return "\n".join(lines)
