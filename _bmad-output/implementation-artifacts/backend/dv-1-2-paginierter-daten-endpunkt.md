# Story DV-1.2: Paginierter Daten-Endpunkt

Status: done

## Story

Als Frontend,
möchte ich Zeilen eines Run-Snapshots seitenweise abrufen können (`offset` + `limit`),
damit die Datenansicht zunächst 1000 Zeilen lädt und beim Scrollen weitere 100 Zeilen nachlädt, ohne den gesamten Datensatz auf einmal zu übertragen.

## Acceptance Criteria

1. **[HTTP 200 mit korrekten Feldern]** `GET /v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=100` antwortet mit HTTP 200 und einem Body, der `columns`, `rows`, `total_rows`, `offset`, `limit`, `is_split` und `column_stats` enthält.

2. **[Korrekte Paginierung]** `rows` enthält genau `limit` Einträge (oder weniger, wenn der Datensatz kleiner ist). Bei `offset=100, limit=100` werden Zeilen 100–199 zurückgegeben.

3. **[column_stats nur bei offset==0]** `column_stats` ist nur im Response enthalten, wenn `offset == 0`. Bei anderen Offsets ist das Feld `null`/nicht vorhanden.

4. **[limit wird auf 1000 geclampt]** Wird `limit=2000` übergeben, antwortet der Endpunkt mit `limit=1000` und maximal 1000 Zeilen — kein Fehler.

5. **[404 bei fehlendem Snapshot]** Existiert für `run_id` kein Parquet-Snapshot (Run noch nicht abgeschlossen oder fehlgeschlagen), antwortet der Endpunkt mit HTTP 404 und einer verständlichen Fehlermeldung.

6. **[404 bei falscher Session]** Gehört `run_id` zu einer anderen Session, antwortet der Endpunkt mit HTTP 404 (keine Session-ID-Leakage).

7. **[Performance < 500 ms]** Für `limit=100` mit einem vollen Bike-Datensatz (17.379 Zeilen) antwortet der Endpunkt in < 500 ms.

8. **[Test-Coverage der Route ≥ 85%]** Alle Acceptance Criteria sind durch Integrationstests in `tests/integration/test_data_api.py` abgedeckt.

## Tasks / Subtasks

- [x] **T1 — Pydantic-Schema `DataPageResponse` hinzufügen** (AC: 1, 3)
  - [x] Datei: `backend/src/gysi_ml/api/schemas.py` (erweitern)
  - [x] Import ergänzen: `from typing import Any` (falls noch nicht vorhanden — prüfen)
  - [x] Schema am Ende der Datei hinzufügen:

    ```python
    class DataPageResponse(BaseModel):
        columns: list[str]
        rows: list[list[Any]]
        total_rows: int
        offset: int
        limit: int
        is_split: bool
        column_stats: Optional[dict] = None  # nur bei offset == 0 befüllt
    ```

- [x] **T2 — Neuen Router `data.py` anlegen** (AC: 1–7)
  - [x] Datei: `backend/src/gysi_ml/api/routes/data.py` (neu)
  - [x] Folgenden Code implementieren:

    ```python
    """API-Endpunkt: Paginierter Datensatz-Zugriff auf Run-Snapshot (Story DV-1.2)."""
    from __future__ import annotations

    import json
    from pathlib import Path
    from typing import Union

    import pandas as pd
    from fastapi import APIRouter, Query, Request
    from fastapi.responses import JSONResponse

    from gysi_ml.api.schemas import DataPageResponse, ErrorResponse
    from gysi_ml.config import get_settings
    from gysi_ml.persistence import run_repository

    router = APIRouter(prefix="/v1")

    _MAX_LIMIT = 1000


    def _get_db_path(request: Request) -> str | None:
        return getattr(request.app.state, "db_path", None)


    def _get_artifacts_path(request: Request) -> str:
        return getattr(request.app.state, "artifacts_path", get_settings().artifacts_path)


    @router.get(
        "/sessions/{session_id}/runs/{run_id}/data",
        response_model=DataPageResponse,
        responses={404: {"model": ErrorResponse}},
    )
    def get_run_data(
        session_id: str,
        run_id: str,
        request: Request,
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1),
    ) -> Union[DataPageResponse, JSONResponse]:
        """Gibt eine paginierte Seite des Run-Snapshots zurück.

        column_stats wird nur bei offset==0 mitgeliefert.
        limit wird serverseitig auf 1000 geclampt.
        """
        db_path = _get_db_path(request)
        artifacts_path = _get_artifacts_path(request)

        # Session-Zugehörigkeit des Runs prüfen
        row = run_repository.get_run(run_id=run_id, db_path=db_path)
        if row is None or row.get("session_id") != session_id:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="run_not_found",
                    detail=f"Run mit ID '{run_id}' nicht gefunden oder gehört nicht zu Session '{session_id}'.",
                    code="RUN_NOT_FOUND",
                ).model_dump(),
            )

        # Snapshot-Datei prüfen
        parquet_path = Path(artifacts_path) / f"{run_id}_snapshot.parquet"
        if not parquet_path.exists():
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="snapshot_not_found",
                    detail=f"Kein Snapshot für Run '{run_id}' vorhanden. Run wurde möglicherweise noch nicht erfolgreich abgeschlossen.",
                    code="SNAPSHOT_NOT_FOUND",
                ).model_dump(),
            )

        # limit clampen
        effective_limit = min(limit, _MAX_LIMIT)

        # Parquet laden und paginieren
        df = pd.read_parquet(parquet_path)
        total_rows = len(df)
        page = df.iloc[offset : offset + effective_limit]

        columns = list(df.columns)
        rows = [list(row) for row in page.itertuples(index=False, name=None)]

        # Column-Stats nur beim ersten Request (offset == 0)
        column_stats: dict | None = None
        if offset == 0:
            stats_path = Path(artifacts_path) / f"{run_id}_column_stats.json"
            if stats_path.exists():
                stats_data = json.loads(stats_path.read_text(encoding="utf-8"))
                column_stats = stats_data.get("columns")

        # is_split aus column_stats-JSON lesen (falls vorhanden), sonst aus Run-Result
        is_split = False
        stats_path = Path(artifacts_path) / f"{run_id}_column_stats.json"
        if stats_path.exists():
            stats_data = json.loads(stats_path.read_text(encoding="utf-8"))
            is_split = bool(stats_data.get("is_split", False))

        return DataPageResponse(
            columns=columns,
            rows=rows,
            total_rows=total_rows,
            offset=offset,
            limit=effective_limit,
            is_split=is_split,
            column_stats=column_stats,
        )
    ```

  - [x] ⚠️ **Hinweis zur stats_path-Doppellesung:** Wenn `offset == 0`, wird `stats_path` zweimal gelesen. Zur Optimierung kann man das in einem `if`-Block zusammenfassen — aber Korrektheit hat Vorrang: Wenn der `stats_path` nicht existiert, ist `column_stats = None` und `is_split = False` (korrekte Defaults).

- [x] **T3 — Router in `app.py` registrieren** (AC: 1)
  - [x] Datei: `backend/src/gysi_ml/api/app.py`
  - [x] Import ergänzen: `from gysi_ml.api.routes.data import router as data_router`
  - [x] Router registrieren — **nach** `runs_router` und **vor** `specs_router`:
    ```python
    app.include_router(runs_router)
    app.include_router(data_router)   # ← NEU (DV-1.2)
    app.include_router(specs_router)
    ```

- [x] **T4 — Integrationstests anlegen** (AC: 1–6, 8)
  - [x] Datei: `backend/tests/integration/test_data_api.py` (neu)
  - [x] Folgendes implementieren:

    ```python
    """Integrationstests für GET /v1/sessions/{session_id}/runs/{run_id}/data (Story DV-1.2)."""
    from __future__ import annotations

    import pandas as pd
    import pytest
    from fastapi.testclient import TestClient

    from gysi_ml.api.app import create_app
    from gysi_ml.config import Settings


    @pytest.fixture
    def csv_file(tmp_path):
        df = pd.DataFrame({
            "instant": range(1, 201),   # 200 Zeilen für Paginierungstest
            "cnt": range(100, 300),
            "temp": [0.5] * 200,
            "dteday": ["2012-01-01"] * 200,
        })
        path = tmp_path / "bikes.csv"
        df.to_csv(path, index=False)
        return str(path)


    @pytest.fixture
    def client(tmp_path, csv_file):
        settings = Settings(
            db_path=str(tmp_path / "test.db"),
            data_path=csv_file,
            artifacts_path=str(tmp_path / "artifacts"),
        )
        app = create_app(settings=settings)
        with TestClient(app) as c:
            yield c


    def _create_session(client) -> str:
        resp = client.post("/v1/sessions", json={"name": "DataTest"})
        assert resp.status_code == 201
        return resp.json()["session_id"]


    def _run_pipeline(client, session_id: str) -> str:
        resp = client.post(
            f"/v1/sessions/{session_id}/execute",
            json={"spec": {"steps": []}},
        )
        assert resp.status_code == 200
        return resp.json()["run_id"]


    # ---------------------------------------------------------------------------
    # AC1: HTTP 200 + korrekte Response-Felder
    # ---------------------------------------------------------------------------

    def test_get_data_returns_200_with_required_fields(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert "columns" in body
        assert "rows" in body
        assert "total_rows" in body
        assert "offset" in body
        assert "limit" in body
        assert "is_split" in body


    # ---------------------------------------------------------------------------
    # AC2: Korrekte Paginierung
    # ---------------------------------------------------------------------------

    def test_get_data_pagination_offset_0(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rows"]) == 10
        assert body["offset"] == 0
        assert body["limit"] == 10


    def test_get_data_pagination_offset_10(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        r0 = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10").json()
        r1 = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=10&limit=10").json()
        # Zeilen dürfen sich nicht überschneiden
        assert r0["rows"][0] != r1["rows"][0]
        assert r1["offset"] == 10


    # ---------------------------------------------------------------------------
    # AC3: column_stats nur bei offset==0
    # ---------------------------------------------------------------------------

    def test_column_stats_present_at_offset_0(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=10")
        body = resp.json()
        assert body["column_stats"] is not None


    def test_column_stats_absent_at_offset_nonzero(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=10&limit=10")
        body = resp.json()
        assert body["column_stats"] is None


    # ---------------------------------------------------------------------------
    # AC4: limit wird auf 1000 geclampt
    # ---------------------------------------------------------------------------

    def test_limit_is_clamped_to_1000(client):
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data?offset=0&limit=9999")
        assert resp.status_code == 200
        body = resp.json()
        assert body["limit"] == 1000


    # ---------------------------------------------------------------------------
    # AC5: 404 bei fehlendem Snapshot
    # ---------------------------------------------------------------------------

    def test_returns_404_if_no_snapshot(client, tmp_path):
        """Run existiert in DB, aber kein Parquet-Snapshot (simuliert durch direktes DB-Insert)."""
        # Wir nutzen einen run_id, der nie ausgeführt wurde
        session_id = _create_session(client)
        resp = client.get(f"/v1/sessions/{session_id}/runs/nonexistent-run-id/data")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] in ("RUN_NOT_FOUND", "SNAPSHOT_NOT_FOUND")


    # ---------------------------------------------------------------------------
    # AC6: 404 bei falscher Session
    # ---------------------------------------------------------------------------

    def test_returns_404_for_wrong_session(client):
        session_a = _create_session(client)
        session_b = _create_session(client)
        run_id = _run_pipeline(client, session_a)
        # Run gehört zu session_a, aber wir fragen session_b
        resp = client.get(f"/v1/sessions/{session_b}/runs/{run_id}/data?offset=0&limit=10")
        assert resp.status_code == 404
    ```

## Dev Notes

### Architektur-Kontext

- Dieser Endpunkt liest **ausschließlich** bestehende Artefakte — er verändert keine Datenbank-Einträge und ruft keine Services auf, die schreiben.
- Die Session-Zugehörigkeit des Runs wird über `run_repository.get_run()` geprüft — exakt gleiche Logik wie in `runs.py` (`get_run`-Handler).
- `artifacts_path` wird über `request.app.state.artifacts_path` bezogen (gleiche Konvention wie `execute.py`).

### Dateien, die berührt werden

| Datei | Änderungstyp |
|---|---|
| `backend/src/gysi_ml/api/schemas.py` | Erweiterung: `DataPageResponse` hinzufügen |
| `backend/src/gysi_ml/api/routes/data.py` | Neu anlegen |
| `backend/src/gysi_ml/api/app.py` | Router-Registrierung |
| `backend/tests/integration/test_data_api.py` | Neu anlegen |

### Keine Änderungen an

- `executor.py` — keine Eingriffe in die Execution-Logik
- `snapshot_service.py` — kein neuer Code nötig
- Datenbankschema — rein additiv, nur neue API-Ebene
- Bestehende Router-Dateien außer `app.py`

### Wichtige Technische Details

**Parquet lesen & paginieren:**

```python
df = pd.read_parquet(parquet_path)
total_rows = len(df)
page = df.iloc[offset : offset + effective_limit]
rows = [list(row) for row in page.itertuples(index=False, name=None)]
```

`itertuples(index=False, name=None)` liefert schnelle Tupel ohne den Zeilen-Index — korrekt für JSON-Serialisierung als List of Lists.

**column_stats-Struktur** (aus DV-1.1 `_compute_column_stats`):

```json
{
  "is_split": false,
  "columns": {
    "col_name": {
      "missing_count": 0,
      "missing_pct": 0.0,
      "distinct_count": 10,
      "distinct_pct": 100.0,
      "min": 1.0,
      "max": 10.0,
      "histogram": { "bins": [...11 Werte...], "counts": [...10 Werte...] }
    }
  }
}
```

Die Response gibt `stats_data["columns"]` als `column_stats` zurück — nicht die volle Datei inkl. `is_split`.

**limit-Clamping:** `Query(100, ge=1)` ohne `le=1000` — das Clamping erfolgt manuell mit `min(limit, _MAX_LIMIT)`. So wird kein 422-Fehler geworfen, sondern still geclampt (laut AC4).

**NaN-Handling:** `itertuples` kann `NaN`-Werte enthalten (float). FastAPI/JSON serialisiert `float('nan')` als `NaN` (kein gültiges JSON). Falls nötig: `page = page.where(page.notna(), other=None)` vor dem itertuples-Aufruf. Das ist ein bekanntes Problem — im ersten Schritt nur implementieren wenn Tests scheitern.

### Muster-Referenzen

- Session-Zugehörigkeits-Check: [backend/src/gysi_ml/api/routes/runs.py](backend/src/gysi_ml/api/routes/runs.py) — Zeilen `get_run`-Handler
- `artifacts_path`-Zugriff: [backend/src/gysi_ml/api/routes/execute.py](backend/src/gysi_ml/api/routes/execute.py) — `_get_artifacts_path()`
- Router-Registrierung: [backend/src/gysi_ml/api/app.py](backend/src/gysi_ml/api/app.py)
- Integrationtest-Muster: [backend/tests/integration/test_runs_api.py](backend/tests/integration/test_runs_api.py)
- SnapshotService (schreibt die Dateien): [backend/src/gysi_ml/services/snapshot_service.py](backend/src/gysi_ml/services/snapshot_service.py)

### Project Structure Notes

- Neuer Router folgt der Konvention: `backend/src/gysi_ml/api/routes/<name>.py` mit `router = APIRouter(prefix="/v1")`
- Neue Schemas folgen der Konvention in `schemas.py`: Pydantic `BaseModel`, keine extra Validierung nötig
- Test-Datei folgt der Konvention: `backend/tests/integration/test_<feature>_api.py`

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot — Amelia Developer Agent)

### Debug Log References

- Keine besonderen Debugging-Schritte nötig — alle Tests liefen beim ersten Durchlauf durch.
- stats_path-Doppellesung aus Story-Hinweis optimiert: `is_split` und `column_stats` werden in einem einzigen `if stats_path.exists()`-Block gelesen (effizienter als Story-Template).

### Completion Notes List

- ✅ T1: `DataPageResponse` Schema in `schemas.py` ergänzt (7 Felder inkl. optionalem `column_stats`)
- ✅ T2: `data.py` Router angelegt — Parquet-Pagination, limit-Clamping auf 1000, column_stats nur bei offset==0, Session-Zugehörigkeits-Check, 404 für fehlende Runs/Snapshots; NaN→None-Handling ergänzt (Code-Review M1)
- ✅ T3: Router in `app.py` nach `runs_router` und vor `specs_router` registriert
- ✅ T4: 10 Integrationstests angelegt — alle ACs 1–7 abgedeckt; 10/10 Tests bestanden
- Code-Review-Fixes: NaN-Handling (M1), SNAPSHOT_NOT_FOUND-Test (M2), AC1 column_stats-Assertion (L1), Performance-Test AC7 (H1)
- Regressionssuite: alle relevanten Tests grün

### File List

- `backend/src/gysi_ml/api/schemas.py` — `DataPageResponse` hinzugefügt
- `backend/src/gysi_ml/api/routes/data.py` — neu angelegt; NaN-Fix nach Code-Review
- `backend/src/gysi_ml/api/app.py` — `data_router` importiert und registriert
- `backend/tests/integration/test_data_api.py` — neu angelegt (10 Tests nach Code-Review)

## Change Log

- 2026-04-14: Story DV-1.2 implementiert — `GET /v1/sessions/{session_id}/runs/{run_id}/data` mit Pagination, limit-Clamping, column_stats-Logik, 404-Handling. 8 Integrationstests, alle grün. (Amelia / Claude Sonnet 4.6)
- 2026-04-14: Code-Review-Fixes — NaN-Handling, SNAPSHOT_NOT_FOUND-Test, AC1 column_stats-Assertion, Performance-Test (AC7). 10/10 Tests grün. Status → done. (Amelia / Claude Sonnet 4.6)
