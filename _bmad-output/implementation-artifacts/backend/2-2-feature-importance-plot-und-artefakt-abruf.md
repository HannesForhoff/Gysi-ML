# Story 2.2: Feature-Importance-Plot und Artefakt-Abruf

Status: done

## Story

Als ein Datenwissenschaftler,
möchte ich nach dem Decision-Tree-Training einen Feature-Importance-Plot als PNG-Datei abrufen können,
damit ich visuell nachvollziehen kann, welche Features den größten Einfluss auf die Vorhersage haben, und das Ergebnis dem Evaluator präsentieren kann.

## Acceptance Criteria

1. **[Automatische Plot-Generierung]** Nach einem erfolgreich abgeschlossenen `train_decision_tree`-Step wird automatisch ein horizontales Feature-Importance-Balkendiagramm (matplotlib) als PNG erstellt. Die Top-20-Features nach Wichtigkeit werden absteigend sortiert dargestellt.

2. **[Filesystem-Persistenz]** Die PNG-Datei wird im Dateisystem unter `{artifacts_path}/feature_importance_{run_id}.png` gespeichert (kein Base64 in der Response). Das Verzeichnis wird angelegt falls nicht vorhanden.

3. **[SQLite-Artefakt-Eintrag]** Nach der Generierung wird ein Eintrag in der `artifacts`-Tabelle (bereits im Schema vorhanden) angelegt: `artifact_id` (UUID), `run_id`, `type: "feature_importance"`, `file_path`, `created_at`.

4. **[GET /v1/artifacts/{artifact_id}]** `GET /v1/artifacts/{artifact_id}` gibt die PNG-Datei als Byte-Stream mit `Content-Type: image/png` und HTTP 200 zurück.

5. **[404 bei unbekannter Artefakt-ID]** `GET /v1/artifacts/{artifact_id}` mit nicht existierender ID gibt HTTP 404 mit `{"error": "artifact_not_found", "detail": "...", "code": "ARTIFACT_NOT_FOUND"}` zurück.

6. **[Artefakte in Run-Response]** `GET /v1/sessions/{session_id}/runs/{run_id}` gibt im `artifacts`-Array alle Artefakte des Runs zurück: `[{"artifact_id": "...", "type": "feature_importance", "created_at": "..."}]`.

7. **[matplotlib-Abhängigkeit]** `matplotlib>=3.8` ist explizit in `requirements.txt` und `pyproject.toml` eingetragen.

8. **[artifacts_path-Setting]** `Settings` in `config.py` enthält `artifacts_path: str = "../artifacts"`. Der Executor und die App erhalten diesen Wert aus `settings`.

9. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten/geänderten Module.

## Tasks / Subtasks

- [x] **T1 — matplotlib-Abhängigkeit hinzufügen** (AC: 7)
  - [x] `backend/requirements.txt` ergänzen: `matplotlib>=3.8`
  - [x] `backend/pyproject.toml` unter `[project] dependencies` ergänzen: `"matplotlib>=3.8"`

- [x] **T2 — `artifacts_path`-Setting hinzufügen** (AC: 8)
  - [x] `src/gysi_ml/config.py` in `Settings`:
    ```python
    artifacts_path: str = "../artifacts"
    ```
  - [x] `src/gysi_ml/api/app.py` in `create_app()`: nach `app.state.data_path = settings.data_path` hinzufügen:
    ```python
    app.state.artifacts_path = settings.artifacts_path
    ```

- [x] **T3 — `artifact_repository.py` anlegen** (AC: 3, 4, 5, 6)
  - [x] `src/gysi_ml/persistence/artifact_repository.py` anlegen:
    - `create_artifact(artifact_id, run_id, artifact_type, file_path, created_at, db_path=None) -> None`
      - INSERT in `artifacts`-Tabelle (bereits im Schema durch Story 1.1: `artifact_id, run_id, type, file_path, created_at`)
      - Parameterized Query (kein SQL-Injection-Risiko)
    - `get_artifact(artifact_id, db_path=None) -> dict | None`
      - SELECT * FROM artifacts WHERE artifact_id = ?
      - Gibt `None` zurück wenn nicht gefunden
    - `get_artifacts_for_run(run_id, db_path=None) -> list[dict]`
      - SELECT artifact_id, type, created_at FROM artifacts WHERE run_id = ? ORDER BY created_at ASC
  - [x] In `src/gysi_ml/persistence/__init__.py` exportieren (oder direkt importieren wo nötig)

- [x] **T4 — BaseStep um `generate_artifact()` erweitern** (AC: 1, 2)
  - [x] `src/gysi_ml/steps/base.py` ergänzen:
    ```python
    def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
        """Generiert ein Artefakt (z.B. Plot) nach der Step-Ausführung.
        Gibt dict mit 'type' und 'file_path' zurück oder None wenn kein Artefakt.
        Preprocessing-Steps geben immer None zurück (Default).
        """
        return None
    ```
  - [x] Keine Änderungen an bestehenden Preprocessing-Steps nötig — Default-Implementierung greift

- [x] **T5 — `DecisionTreeStep` um Plot-Generierung erweitern** (AC: 1, 2)
  - [x] `src/gysi_ml/steps/modeling/decision_tree.py` in `DecisionTreeStep` erweitern:
    - `generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None`

- [x] **T6 — PipelineContext um `artifacts` erweitern** (AC: 6)
  - [x] `src/gysi_ml/executor/pipeline_context.py`:
    - Neues Feld: `artifacts: list[dict] = field(default_factory=list)` nach `metrics`

- [x] **T7 — PipelineExecutor um Artefakt-Persistenz erweitern** (AC: 2, 3, 6)
  - [x] `src/gysi_ml/executor/executor.py` angepasst
  - [x] `src/gysi_ml/api/routes/execute.py` angepasst

- [x] **T8 — Pydantic Schema `ArtifactSummary`** (AC: 6)
  - [x] `src/gysi_ml/api/schemas.py` ergänzt
  - [x] `RunDetailResponse.artifacts` auf `Optional[list[ArtifactSummary]] = None` aktualisiert

- [x] **T9 — Artifacts-Route anlegen** (AC: 4, 5)
  - [x] `src/gysi_ml/api/routes/artifacts.py` angelegt
  - [x] Router in `src/gysi_ml/api/app.py` registriert

- [x] **T10 — Unit Tests** (AC: 1–6, 9)
  - [x] `tests/unit/test_artifact_repository.py` ✓
  - [x] `tests/unit/modeling/test_decision_tree_artifacts.py` ✓

- [x] **T11 — Integration Tests** (AC: 4, 5, 6, 9)
  - [x] `tests/integration/test_artifacts_api.py` ✓
    from fastapi.responses import FileResponse, JSONResponse
    from gysi_ml.api.schemas import ErrorResponse
    from gysi_ml.persistence import artifact_repository
    import os

    router = APIRouter(prefix="/v1", tags=["artifacts"])

    @router.get("/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: str, request: Request):
        db_path = request.app.state.db_path
        record = artifact_repository.get_artifact(artifact_id, db_path=db_path)
        if record is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="artifact_not_found",
                    detail=f"Artefakt '{artifact_id}' nicht gefunden.",
                    code="ARTIFACT_NOT_FOUND",
                ).model_dump(),
            )
        file_path = record["file_path"]
        if not os.path.isfile(file_path):
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    error="artifact_file_missing",
                    detail="Artefakt-Datei nicht gefunden.",
                    code="ARTIFACT_FILE_MISSING",
                ).model_dump(),
            )
        return FileResponse(file_path, media_type="image/png")
    ```
  - [ ] Router in `src/gysi_ml/api/app.py` registrieren:
    - Import: `from gysi_ml.api.routes.artifacts import router as artifacts_router`
    - `app.include_router(artifacts_router)`

- [ ] **T10 — Unit Tests** (AC: 1–6, 9)
  - [ ] `tests/unit/test_artifact_repository.py`:
    - `test_create_and_get_artifact()`: Anlegen + Abrufen eines Artefakts über In-Memory-SQLite
    - `test_get_artifact_not_found()`: unbekannte ID → None
    - `test_get_artifacts_for_run()`: Run mit 2 Artefakten → Liste mit 2 Einträgen
  - [ ] `tests/unit/modeling/test_decision_tree_artifacts.py`:
    - `test_generate_artifact_creates_png(tmp_path)`: nach `fit()` + `transform()` gibt `generate_artifact(str(tmp_path), "test-run-id")` ein Dict mit `type == "feature_importance"` zurück, und die Datei existiert unter `tmp_path`
    - `test_generate_artifact_returns_none_before_fit()`: ohne vorheriges `fit()` → `None`
    - `test_base_step_default_returns_none()`: Preprocessing-Step (z.B. DedupStep) — `generate_artifact(...)` gibt `None` zurück

- [ ] **T11 — Integration Tests** (AC: 4, 5, 6, 9)
  - [ ] `tests/integration/test_artifacts_api.py`:
    - `test_artifact_retrieve_after_training(tmp_path)`: kompletter Flow: POST exec (split + train_decision_tree) → GET run detail → `artifacts[0].artifact_id` → GET `/v1/artifacts/{artifact_id}` → HTTP 200, `Content-Type: image/png`
    - `test_artifact_404_unknown_id()`: GET `/v1/artifacts/nonexistent` → HTTP 404
    - `test_run_detail_artifacts_array()`: nach Training → `artifacts`-Array in Run-Detail nicht leer
  - [ ] Tests nutzen `tmp_path` fixture für `artifacts_path`, um nicht in `../artifacts/` zu schreiben

## Dev Notes

### Zielstruktur nach dieser Story

```text
backend/src/gysi_ml/
├── config.py                          # ÄNDERN: + artifacts_path
├── steps/
│   ├── base.py                        # ÄNDERN: + generate_artifact()
│   └── modeling/
│       └── decision_tree.py           # ÄNDERN: + generate_artifact()
├── persistence/
│   └── artifact_repository.py         # NEU
├── executor/
│   ├── executor.py                    # ÄNDERN: artifacts_path param, Artefakt-Persistenz
│   └── pipeline_context.py            # ÄNDERN: + artifacts: list
└── api/
    ├── schemas.py                     # ÄNDERN: + ArtifactSummary
    ├── app.py                         # ÄNDERN: artifacts_router + artifacts_path state
    └── routes/
        └── artifacts.py               # NEU
```

### Architektur-Constraints (kritisch!)

- **Non-interactive Matplotlib**: `matplotlib.use("Agg")` **muss vor** dem ersten `import matplotlib.pyplot` stehen, oder `import matplotlib; matplotlib.use("Agg")` in der gleichen Importkette. Server-Prozesse haben kein Display — interactives Backend führt zu Absturz.
- **`plt.close(fig)` nach savefig**: Kein Memory-Leak bei vielen Runs in einer Session.
- **`artifacts`-Tabelle existiert bereits** im SQLite-Schema (Story 1.1: `artifact_id, run_id, type, file_path, created_at`) — kein Schema-Migrate nötig.
- **`PipelineExecutor.__init__` erhält neuen Parameter** `artifacts_path` — überall wo der Executor instantiiert wird (execute.py, Tests) muss dieser übergeben werden. In Tests kann ein `tmp_path`-String verwendet werden.
- **`os.makedirs(artifacts_path, exist_ok=True)` in `generate_artifact()`** — idempotent, kein Fehler falls Verzeichnis schon existiert.

### Regressions-Schutz

- `BaseStep.generate_artifact()` gibt `None` zurück → Preprocessing-Steps unverändert
- Executor prüft `if artifact_info:` vor DB-Schreiboperationen → kein Null-Pointer
- `run_repository.update_run_status` mit `result_json` jetzt mit gefüllten `artifacts` — `RunDetailResponse` liest dies korrekt (`artifacts: Optional[list]` war bereits vorhanden)

### Wichtige Test-Fixture-Anpassung

In Integration-Tests, die `TestClient` nutzen, muss `app.state.artifacts_path` auf `str(tmp_path)` gesetzt werden:

```python
@pytest.fixture
def client(tmp_path):
    settings = Settings(artifacts_path=str(tmp_path), ...)
    app = create_app(settings=settings)
    with TestClient(app) as c:
        yield c
```

Alternativ über `app.state.artifacts_path = str(tmp_path)` nach App-Erstellung setzen.

### Referenzen

- SQLite-Schema (artifacts-Tabelle): [backend/src/gysi_ml/persistence/schema.py](backend/src/gysi_ml/persistence/schema.py)
- Executor (Schleife + result-Dict): [backend/src/gysi_ml/executor/executor.py](backend/src/gysi_ml/executor/executor.py)
- PipelineContext: [backend/src/gysi_ml/executor/pipeline_context.py](backend/src/gysi_ml/executor/pipeline_context.py)
- BaseStep: [backend/src/gysi_ml/steps/base.py](backend/src/gysi_ml/steps/base.py)
- DecisionTreeStep (aus Story 2.1): `backend/src/gysi_ml/steps/modeling/decision_tree.py`
- App-Factory: [backend/src/gysi_ml/api/app.py](backend/src/gysi_ml/api/app.py)
- Config: [backend/src/gysi_ml/config.py](backend/src/gysi_ml/config.py)
- FR30, FR32, FR33, FR34: [epics.md](_bmad-output/planning-artifacts/backend/epics.md)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6

### Completion Notes List

- `matplotlib.use("Agg")` wird innerhalb von `generate_artifact()` gesetzt, unmittelbar vor dem ersten `pyplot`-Import – funktioniert korrekt im Server-Kontext ohne Display.
- `artifact_repository` nutzt `get_connection()` aus `database.py` (gleiches Pattern wie alle anderen Repositories).
- `PipelineExecutor.__init__` hat `artifacts_path` als Keyword-Argument mit Default `"../artifacts"` – bestehende Tests, die `PipelineExecutor(data_path=...)` aufrufen, waren ohne Anpassung kompatibel (256 Tests grün).
- Integration-Tests nutzen `tmp_path / "artifacts"` als `artifacts_path`, kein Schreiben in das echte `../artifacts/`-Verzeichnis.

### File List

- `backend/requirements.txt` — `matplotlib>=3.8` hinzugefügt
- `backend/pyproject.toml` — `matplotlib>=3.8` in `[project] dependencies` hinzugefügt
- `backend/src/gysi_ml/config.py` — `artifacts_path: str = "../artifacts"` hinzugefügt
- `backend/src/gysi_ml/api/app.py` — `artifacts_path` State + `artifacts_router` registriert
- `backend/src/gysi_ml/steps/base.py` — `generate_artifact()` Default-Methode hinzugefügt
- `backend/src/gysi_ml/steps/modeling/decision_tree.py` — `generate_artifact()` implementiert
- `backend/src/gysi_ml/executor/pipeline_context.py` — `artifacts: list[dict]` Feld hinzugefügt
- `backend/src/gysi_ml/executor/executor.py` — `artifacts_path` Parameter, Artefakt-Persistenz-Loop, `context.artifacts` in result
- `backend/src/gysi_ml/api/routes/execute.py` — `_get_artifacts_path()` + `PipelineExecutor(artifacts_path=...)` 
- `backend/src/gysi_ml/api/schemas.py` — `ArtifactSummary` Schema + `RunDetailResponse.artifacts` typisiert
- `backend/src/gysi_ml/persistence/artifact_repository.py` — NEU
- `backend/src/gysi_ml/api/routes/artifacts.py` — NEU
- `backend/tests/unit/test_artifact_repository.py` — NEU (4 Tests)
- `backend/tests/unit/modeling/test_decision_tree_artifacts.py` — NEU (3 Tests)
- `backend/tests/integration/test_artifacts_api.py` — NEU (3 Tests)
