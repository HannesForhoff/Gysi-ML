# Bug 1.10 — Artefakt-Download: Fehlende Typ-Mappings für `correlation_filter_result` und `time_features_result`

**Gefunden**: 2026-04-15
**Status**: Dokumentiert, Entscheidung getroffen, Fix ausstehend
**Priorität**: 🔴 Hoch-Mittel (direkt sichtbar, sofort behebbar)
**Kategorie**: Backend — `api/routes/artifacts.py` + Tests

---

## Beobachtetes Fehlverhalten

| Artefakt-Typ | Erwarteter Download-Name | Tatsächlicher Download-Name |
| --- | --- | --- |
| `correlation_filter_result` | `correlation_filter_ergebnis.csv` | `3dc58424-7f6d-4b29-9272-369d8ff02a3a_correlation_filter (1)` |
| `time_features_result` | `time_features_ergebnis.csv` | `00e48fad-d5ee-4090-ae12-932fd8f9537f_time_features` |

**Kontext:** Dieser Fehler ist die Fortsetzung von Bug 1.7, der das generelle Problem behoben hat.
Bug 1.7 ergänzte das `_TYPE_TO_DOWNLOAD_FILENAME`-Mapping für `split_train`, `split_test`,
`feature_importance` und `ebm_global_explanation`. Die in Bug 1.6 (TimeFeatures) und
Bug 1.4 (CorrelationFilter) neu eingeführten Artefakt-Typen wurden dabei nicht berücksichtigt.

---

## Technische Ursachenanalyse

### Ursache — Unvollständiges Typ-Mapping

**Datei:** `backend/src/gysi_ml/api/routes/artifacts.py`

**Ist-Zustand:**

```python
_TYPE_TO_DOWNLOAD_FILENAME: dict[str, str] = {
    "split_train": "trainingsdaten.csv",
    "split_test": "testdaten.csv",
    "feature_importance": "decision_tree_feature_importance.png",
    "ebm_global_explanation": "ebm_feature_importance.png",
    # ← correlation_filter_result fehlt
    # ← time_features_result fehlt
}
```

Der Fallback in der `get_artifact()`-Route greift:

```python
filename = _TYPE_TO_DOWNLOAD_FILENAME.get(
    record.get("type", ""), os.path.basename(file_path)
)
# → os.path.basename("../artifacts/3dc58424-..._correlation_filter.csv")
# → "3dc58424-..._correlation_filter.csv"
```

### Woher kommen die Typen?

- `"correlation_filter_result"` wird in `correlation_filter.py` → `generate_artifact()` gesetzt:
  `{"type": "correlation_filter_result", "file_path": path}`
- `"time_features_result"` wird in `time_features.py` → `generate_artifact()` gesetzt:
  `{"type": "time_features_result", "file_path": path}`

### Was steht in der `correlation_filter_result`-CSV?

Die CSV enthält den gefilterten Trainings-DataFrame nach dem Entfernen hochkorrelierter Features.
Aktuell kein Problem mit dem Inhalt — nur der Download-Name ist falsch.

---

## Fix-Plan

### Schritt 1 — Mapping in `artifacts.py` ergänzen

```python
_TYPE_TO_DOWNLOAD_FILENAME: dict[str, str] = {
    "split_train": "trainingsdaten.csv",
    "split_test": "testdaten.csv",
    "feature_importance": "decision_tree_feature_importance.png",
    "ebm_global_explanation": "ebm_feature_importance.png",
    "correlation_filter_result": "correlation_filter_ergebnis.csv",   # ← neu
    "time_features_result": "time_features_ergebnis.csv",            # ← neu
}
```

### Schritt 2 — Tests in `test_artifacts_api.py` ergänzen

Analog zu den bestehenden Tests für `split_train`/`split_test`/`feature_importance`:

```python
def test_correlation_filter_content_disposition_readable_filename(client):
    """correlation_filter_result muss 'correlation_filter_ergebnis.csv' im Header tragen."""
    ...
    content_disposition = art_resp.headers.get("content-disposition", "")
    assert "correlation_filter_ergebnis.csv" in content_disposition

def test_time_features_content_disposition_readable_filename(client):
    """time_features_result muss 'time_features_ergebnis.csv' im Header tragen."""
    ...
    content_disposition = art_resp.headers.get("content-disposition", "")
    assert "time_features_ergebnis.csv" in content_disposition
```

### Prozess-Verbesserung (kein Code-Fix)

Beim Hinzufügen eines neuen Steps mit `generate_artifact()` muss das Typ-Mapping
in `_TYPE_TO_DOWNLOAD_FILENAME` immer zeitgleich gepflegt werden.
Dies sollte als Checkliste-Punkt in der Story-Vorlage für neue Steps aufgenommen werden.

---

## Betroffene Dateien

| Datei | Änderung |
| --- | --- |
| `backend/src/gysi_ml/api/routes/artifacts.py` | 2 Einträge in `_TYPE_TO_DOWNLOAD_FILENAME` |
| `backend/tests/integration/test_artifacts_api.py` | 2 neue Integrationstests |

---

## Getroffene Entscheidungen

- Mapping-Namen: `correlation_filter_ergebnis.csv` und `time_features_ergebnis.csv`
  (deutsch, konsistent mit `trainingsdaten.csv` / `testdaten.csv`)
- Keine Änderung an Disk-Dateinamen (UUID bleibt für Eindeutigkeit)

---

## Offene Entscheidungen

Keine — Fix ist vollständig spezifiziert.

---

## Dringlichkeit

🟠 Hoch-Mittel — Direkt sichtbar im UI, sofort nach Ausführung der betroffenen Steps.
Extrem kleiner Fix (2 Zeilen + 2 Tests). Kein Grund diese zu verzögern.
