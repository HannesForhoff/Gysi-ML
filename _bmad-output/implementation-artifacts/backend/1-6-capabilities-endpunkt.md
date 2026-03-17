# Story 1.6: Capabilities-Endpunkt

Status: done

## Story

Als ein API-Konsument (Entwickler oder zukünftiges Frontend),
möchte ich eine strukturierte Übersicht aller verfügbaren Aktionen und Steps abrufen können,
damit ich weiß, welche Pipeline-Steps und API-Operationen das System unterstützt, ohne den Quellcode lesen zu müssen.

## Acceptance Criteria

1. **[GET /v1/capabilities]** `GET /v1/capabilities` liefert HTTP 200 mit einer JSON-Antwort, die alle registrierten Step-Typen enthält.

2. **[Step-Struktur]** Jeder Step enthält `type`, `description` und `params` (Parameterliste mit Typen und Defaults) — direkt aus den Klassen-Attributen abgeleitet (`description` und `param_schema`).

3. **[Auto-Discovery]** Ein neu über `@register_step` registrierter Step erscheint automatisch in der Response — keine manuelle Pflege erforderlich.

4. **[Maschinenlesbar]** Die Capabilities-Response ist konsistentes JSON (kein freier Text) und direkt maschinenlesbar (z.B. für das spätere Frontend oder den LLM-System-Prompt).

5. **[Test-Coverage]** ≥ 85 % für alle in dieser Story neu erstellten Module.

## Tasks / Subtasks

- [x] **T1 — BaseStep Attribute sicherstellen** (AC: 2, 3)
  - [x] `steps/base.py` prüfen/ergänzen:
    - `description: str = ""` als Klassen-Attribut mit Default
    - `param_schema: dict = {}` als Klassen-Attribut mit Default
  - [x] Sicherstellen dass alle bis hier implementierten Steps (`dedup`, `impute_missing`, `outlier_handling`, `encode_categorical`, `correlation_filter`, `rare_category_bucketing`, `time_feature_encoding`, `split`) diese Attribute gesetzt haben

- [x] **T2 — Capabilities-Service** (AC: 1, 2, 3, 4)
  - [x] `src/gysi_ml/core/capabilities.py` anlegen
  - [x] `get_capabilities() -> dict`:
    - Ruft `get_all_steps()` aus der Registry auf
    - Iteriert über alle registrierten Klassen
    - Gibt strukturiertes Dict zurück:
    ```python
    {
      "steps": [
        {
          "type": "dedup",
          "description": "Entfernt exakt duplizierte Zeilen aus dem Datensatz",
          "params": {}
        },
        {
          "type": "impute_missing",
          "description": "Imputiert fehlende Werte numerischer Spalten",
          "params": {
            "strategy": {"type": "string", "enum": ["median", "mean", "most_frequent"], "default": "median"}
          }
        },
        ...
      ]
    }
    ```
  - [x] Steps alphabetisch nach `type` sortiert (deterministisch)

- [x] **T3 — Pydantic Schemas** (AC: 4)
  - [x] `api/schemas.py` ergänzen:
  - [x] `StepCapability`: `type: str`, `description: str`, `params: dict`
  - [x] `CapabilitiesResponse`: `steps: list[StepCapability]`

- [x] **T4 — Capabilities-Endpunkt** (AC: 1–4)
  - [x] `src/gysi_ml/api/routes/capabilities.py` anlegen
  - [x] `GET /v1/capabilities` → `CapabilitiesResponse`
  - [x] Ruft `get_capabilities()` auf — kein Business-Logic-Code direkt im Handler
  - [x] Router in `api/app.py` registrieren

- [x] **T5 — Unit Tests** (AC: 1–4, 5)
  - [x] `tests/unit/test_capabilities.py`:
    - `get_capabilities()` gibt alle registrierten Step-Typen zurück
    - Neuer Dummy-Step erscheint automatisch nach Registrierung
    - Jeder Step hat `type`, `description`, `params`
    - Response ist alphabetisch sortiert

- [x] **T6 — Integration Tests** (AC: 1–4, 5)
  - [x] `tests/integration/test_capabilities_api.py`:
    - `GET /v1/capabilities` liefert HTTP 200
    - Response enthält mindestens: `dedup`, `impute_missing`, `outlier_handling`, `encode_categorical`, `correlation_filter`, `rare_category_bucketing`, `time_feature_encoding`, `split`
    - Response-Format valide JSON, kein freier Text

- [x] **T7 — Epic 1 Abschluss-Check** (kein AC, Qualität)
  - [x] `pytest tests/ --cov=src/gysi_ml --cov-report=term-missing` — Coverage ≥ 85 % (96 % erreicht)
  - [x] Alle bisherigen Tests grün (249/249 bestanden, keine Regressionen)

## Dev Notes

### Zielstruktur nach dieser Story

```
backend/src/gysi_ml/
├── core/
│   └── capabilities.py              # NEU: get_capabilities()
└── api/
    ├── schemas.py                   # + StepCapability, CapabilitiesResponse
    └── routes/
        └── capabilities.py          # NEU: GET /v1/capabilities
```

### Vollständige Liste registrierter Steps nach Epic 1

Nach Abschluss aller Stories von Epic 1 sind folgende Steps in der Registry:

| type | Klasse | Story |
|---|---|---|
| `dedup` | `DeduplicationStep` | 1.3 |
| `impute_missing` | `ImputationStep` | 1.3 |
| `outlier_handling` | `OutlierHandlingStep` | 1.3 |
| `encode_categorical` | `CategoricalEncodingStep` | 1.4 |
| `correlation_filter` | `CorrelationFilterStep` | 1.4 |
| `rare_category_bucketing` | `RareCategoryBucketingStep` | 1.4 |
| `time_feature_encoding` | `TimeFeatureEncodingStep` | 1.4 |
| `split` | `SplitStep` | 1.5 |

In Epic 2 kommen hinzu: `train_decision_tree`, `train_ebm`
In Epic 4 kommt hinzu: `catboost_feature_selection`

### Warum `param_schema` kein JSON-Schema für die Capabilities-Response ist

`param_schema` ist das per-Step definierte Schema der `params`-Keys. Die Capabilities-Response gibt dieses Schema direkt weiter — so sieht das Frontend/LLM, welche Parameter ein Step akzeptiert und welche Defaults gelten.

Beispiel für `split`:
```json
{
  "type": "split",
  "description": "Teilt den Datensatz reproduzierbar in Train/Test auf",
  "params": {
    "test_size": {"type": "number", "default": 0.2},
    "random_state": {"type": "integer", "default": 42}
  }
}
```

### Verwendung in Story 3 (LLM-System-Prompt)

Die Capabilities-Response wird in Story 3.2 als Teil des LLM-System-Prompts verwendet, damit das Modell weiß, welche Steps es erzeugen darf. Die maschinenlesbare Struktur ist dafür essenziell.

### Auto-Discovery erfordert Import-Reihenfolge

Damit alle Steps bei `GET /v1/capabilities` sichtbar sind, müssen alle `@register_step`-Decorators **vor** dem ersten Aufruf von `get_all_steps()` ausgeführt sein. Sichergestellt durch:

```python
# api/app.py — app factory
import gysi_ml.steps  # triggt alle preprocessing/__init__.py Imports
```

Wenn neue Steps in neuen Modulen hinzukommen (Epic 2, 4), müssen ihre `__init__.py`-Importe ebenfalls hier hinzugefügt werden — oder die Steps werden in den jeweiligen Story-`__init__.py`-Dateien importiert.

### Sortierung für Determinismus

Steps werden alphabetisch nach `type` sortiert damit die Reihenfolge in der API-Response nicht von der Registrierungsreihenfolge (= Import-Reihenfolge) abhängt.

### Epic 1 vollständig — was als nächstes kommt

Nach Story 1.6 ist Epic 1 abgeschlossen. Die vollständige Preprocessing-Pipeline kann über `/execute` mit Specs ausgeführt werden. Epic 2 fügt Modeling-Steps hinzu, Epic 3 die LLM-Konversationsschicht.

### Referenzen

- [Source: _bmad-output/planning-artifacts/backend/epics.md#Story 1.6]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#FR11]
- [Source: _bmad-output/planning-artifacts/backend/epics.md#NFR-M1, NFR-M2]
- [Source: _bmad-output/planning-artifacts/backend/prd.md#FR11]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

### Completion Notes List

### File List
