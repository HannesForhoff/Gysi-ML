# Story DV-1.3: CSV-Download-Endpunkt

Status: done

## Story

Als Nutzer,
möchte ich den aktuell angezeigten transformierten Datensatz als CSV-Datei herunterladen können,
damit ich die Ergebnisse meines Preprocessing-Workflows weiterverarbeiten kann.

## Acceptance Criteria

1. **[HTTP 200 + Content-Type]** `GET /v1/sessions/{session_id}/runs/{run_id}/data/download` antwortet mit HTTP 200 und `Content-Type: text/csv`.

2. **[Content-Disposition Header]** Die Response enthält den Header `Content-Disposition: attachment; filename="gysi_data_{run_id[:8]}.csv"` (die ersten 8 Zeichen der run_id).

3. **[Valides CSV]** Der Response-Body ist ein valides CSV mit Header-Zeile und allen Spalten und Zeilen des Snapshots.

4. **[404 bei fehlendem Snapshot]** Existiert für `run_id` kein Parquet-Snapshot, antwortet der Endpunkt mit HTTP 404 und einer verständlichen Fehlermeldung.

5. **[404 bei falscher Session]** Gehört `run_id` zu einer anderen Session, antwortet der Endpunkt mit HTTP 404 (keine Session-ID-Leakage).

6. **[Test-Coverage ≥ 85%]** Alle ACs sind durch Tests in `tests/integration/test_data_api.py` abgedeckt (Erweiterung der bestehenden Datei).

## Tasks / Subtasks

- [x] **T1 — Download-Endpunkt in `data.py` ergänzen** (AC: 1, 2, 3, 4, 5)
  - [x] Datei: `backend/src/gysi_ml/api/routes/data.py` (erweitern)
  - [x] Import ergänzen:
    ```python
    import io
    from fastapi.responses import StreamingResponse
    ```
  - [x] Neuen Endpunkt **nach** `get_run_data` in derselben Datei hinzufügen:

    ```python
    @router.get(
        "/sessions/{session_id}/runs/{run_id}/data/download",
        responses={
            200: {"content": {"text/csv": {}}, "description": "CSV-Download des Run-Snapshots"},
            404: {"model": ErrorResponse},
        },
    )
    def download_run_data_csv(
        session_id: str,
        run_id: str,
        request: Request,
    ) -> StreamingResponse | JSONResponse:
        """Streamt den Run-Snapshot als CSV-Datei.

        Content-Disposition: attachment; filename="gysi_data_{run_id[:8]}.csv"
        Session-Zugehörigkeit wird geprüft.
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

        # Parquet laden und als CSV streamen
        df = pd.read_parquet(parquet_path)
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        buffer.seek(0)

        filename = f"gysi_data_{run_id[:8]}.csv"
        return StreamingResponse(
            iter([buffer.read()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    ```

  - [x] ⚠️ **Reihenfolge der Endpunkte beachten:** FastAPI routet `/data/download` und `/data` beide über `GET /sessions/{sid}/runs/{rid}/data...`. Der spezifischere Pfad `/data/download` muss VOR `/data` definiert sein (oder der Präfix macht ihn eindeutig — da `download` kein Query-Parameter ist, routet FastAPI korrekt). Die aktuelle Route `GET .../data` hat Query-Parameter `offset`/`limit`, die Route `GET .../data/download` hat einen anderen Pfad-Suffix — kein Routing-Konflikt.

- [x] **T2 — Integrationstests ergänzen** (AC: 1–5, 6)
  - [x] Datei: `backend/tests/integration/test_data_api.py` (erweitern — **nicht neu anlegen**)
  - [x] Folgende Tests ergänzen:

    ```python
    # ---------------------------------------------------------------------------
    # DV-1.3: CSV-Download-Endpunkt
    # ---------------------------------------------------------------------------

    def test_csv_download_returns_200_with_csv_content_type(client):
        """AC1: HTTP 200 + Content-Type text/csv."""
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


    def test_csv_download_has_content_disposition_header(client):
        """AC2: Content-Disposition mit korrektem Dateinamen."""
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
        assert resp.status_code == 200
        content_disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert f"gysi_data_{run_id[:8]}.csv" in content_disposition


    def test_csv_download_body_is_valid_csv_with_header(client):
        """AC3: Body enthält valides CSV mit Header-Zeile und Datensatz."""
        session_id = _create_session(client)
        run_id = _run_pipeline(client, session_id)
        resp = client.get(f"/v1/sessions/{session_id}/runs/{run_id}/data/download")
        assert resp.status_code == 200
        lines = resp.text.strip().splitlines()
        # Header-Zeile vorhanden
        assert len(lines) >= 2
        header = lines[0].split(",")
        # Spalten des Fixtures: instant, cnt, temp, dteday
        assert "instant" in header
        assert "cnt" in header


    def test_csv_download_returns_404_if_no_snapshot(client):
        """AC4: 404 wenn kein Snapshot existiert."""
        session_id = _create_session(client)
        resp = client.get(f"/v1/sessions/{session_id}/runs/nonexistent-run-id/data/download")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] in ("RUN_NOT_FOUND", "SNAPSHOT_NOT_FOUND")


    def test_csv_download_returns_404_for_wrong_session(client):
        """AC5: 404 wenn Run zu anderer Session gehört."""
        session_a = _create_session(client)
        session_b = _create_session(client)
        run_id = _run_pipeline(client, session_a)
        resp = client.get(f"/v1/sessions/{session_b}/runs/{run_id}/data/download")
        assert resp.status_code == 404
    ```

## Dev Notes

### Was ist die Story?

Ein neuer GET-Endpunkt am Pfad `.../data/download` streamt den Parquet-Snapshot eines Runs als CSV-Datei. Keine neuen Services, keine DB-Änderungen — rein additiv in `data.py`.

### Dateien, die berührt werden

| Datei | Änderungstyp |
|---|---|
| `backend/src/gysi_ml/api/routes/data.py` | Erweiterung: neuer Endpunkt `download_run_data_csv` |
| `backend/tests/integration/test_data_api.py` | Erweiterung: 5 neue Testfunktionen |

### Keine Änderungen an

- `app.py` — `data_router` ist bereits registriert (Story DV-1.2)
- `schemas.py` — kein neues Schema nötig (StreamingResponse hat kein Pydantic-Schema)
- `snapshot_service.py` — kein Eingriff
- Datenbankschema — rein additiv

### FastAPI StreamingResponse mit CSV

```python
import io
from fastapi.responses import StreamingResponse

df = pd.read_parquet(parquet_path)
buffer = io.StringIO()
df.to_csv(buffer, index=False)
buffer.seek(0)

return StreamingResponse(
    iter([buffer.read()]),
    media_type="text/csv",
    headers={"Content-Disposition": f'attachment; filename="gysi_data_{run_id[:8]}.csv"'},
)
```

`iter([buffer.read()])` liefert den gesamten CSV-Inhalt als einen einzigen Chunk — für den Bike-Datensatz (17k Zeilen) vollkommen ausreichend und einfach testbar.

### Routing-Hinweis: Pfad-Eindeutigkeit

FastAPI routet `GET /sessions/{sid}/runs/{rid}/data` und `GET /sessions/{sid}/runs/{rid}/data/download` korrekt ohne Konflikte, da `/data/download` ein längerer, spezifischerer Pfad ist. **Keine Reihenfolge-Tricks nötig**, solange beide Routen mit vollem Pfad definiert sind.

### Session-Zugehörigkeits-Check

Exakt gleiche Logik wie in `get_run_data` (DV-1.2) und `runs.py` (`get_run`-Handler):

```python
row = run_repository.get_run(run_id=run_id, db_path=db_path)
if row is None or row.get("session_id") != session_id:
    return JSONResponse(status_code=404, ...)
```

### Imports-Ergänzung in data.py

Die bestehende `data.py` importiert bereits: `json`, `Path`, `Union`, `pd`, `APIRouter`, `Query`, `Request`, `JSONResponse`.

Neu hinzufügen:
- `import io` (Standard-Bibliothek)
- `from fastapi.responses import StreamingResponse`

### Vorgänger-Story DV-1.2: Kontext übernehmen

- `_get_db_path()` und `_get_artifacts_path()` sind bereits vorhanden — wiederverwenden
- `run_repository.get_run()` Session-Check ist identisch — Code-Pattern 1:1 übernehmen
- `ErrorResponse`-Schema und `SNAPSHOT_NOT_FOUND`/`RUN_NOT_FOUND`-Codes sind etabliert

### Muster-Referenzen

- Paginierter Endpunkt (DV-1.2): [backend/src/gysi_ml/api/routes/data.py](backend/src/gysi_ml/api/routes/data.py)
- Integrationtest-Fixtures: [backend/tests/integration/test_data_api.py](backend/tests/integration/test_data_api.py) — `csv_file`, `client`, `_create_session`, `_run_pipeline` wiederverwenden
- StreamingResponse Docs: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse

### Testbarkeit

Der `TestClient` von fastapi/starlette materialisiert `StreamingResponse`-Antworten vollständig in `resp.content` / `resp.text` — die Tests können `resp.text.splitlines()` nutzen wie bei normalen Response-Bodies.

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Debug Log References

- `response_model=None` in `@router.get`-Dekorator erforderlich, da FastAPI `Union[StreamingResponse, JSONResponse]` nicht als Pydantic-Modell verarbeiten kann.
- `pyarrow` war nicht in der Test-Umgebung installiert — via `pip install pyarrow` nachinstalliert (23.0.1).

### Completion Notes List

- T1: Endpunkt `download_run_data_csv` in `data.py` ergänzt; `import io` + `StreamingResponse` hinzugefügt.
- T2: 5 neue Tests in `test_data_api.py` ergänzt — alle 15 Tests (DV-1.2 + DV-1.3) bestehen.
- Kein Routing-Konflikt mit `/data` (FastAPI routet `/data/download` korrekt als spezifischeren Pfad).

### File List

- `backend/src/gysi_ml/api/routes/data.py`
- `backend/tests/integration/test_data_api.py`
- `backend/pyproject.toml`
- `backend/requirements.txt`
