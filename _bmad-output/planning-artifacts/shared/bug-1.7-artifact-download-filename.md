# Bug 1.7 — Artefakt-Download: UUID-basierter Dateiname statt lesbarer Name

**Status:** Analysiert, Fix ausstehend — **3 offene Entscheidungen (siehe Ende des Dokuments)**
**Schweregrad:** Niedrig-Mittel (UX-Problem, keine Funktionalität kaputt)
**Kategorie:** Backend (`artifacts.py`) + optional Frontend (`ResultCard.tsx`)
**Analysiert von:** Amelia (Developer Agent), Party-Mode-Session, 2026-04-04

---

## Beobachtetes Fehlverhalten

| Nutzeraktion | Erwartetes Verhalten | Tatsächliches Verhalten |
|---|---|---|
| User klickt auf Download-Link für ein Split-Artefakt | Datei wird heruntergeladen als z.B. `bike_trainingsdaten.csv` | Datei wird heruntergeladen als `9a9aad2b-1fd3-410a-90f1-25b1d20d9bda_train.csv` |
| User klickt auf Download für Feature-Importance-Plot | `feature_importance.png` | `feature_importance_9a9aad2b-1fd3-410a-90f1-25b1d20d9bda.png` |

**Konkret aus dem Usecase:**

Browser-Download-Prompt zeigt:
```
9a9aad2b-1fd3-410a-90f1-25b1d20d9bda_train
```
(teils ohne Dateiendung im Titel, da OS die Endung manchmal aus dem `filename`-Parameter im
`Content-Disposition`-Header liest, aber nicht immer korrekt anzeigt)

---

## Technische Ursachenanalyse

### Ursachenkette (vollständig)

```
split.py:generate_artifact()
    ↓ schreibt Datei als: {run_id}_train.csv  (run_id = UUID)
    ↓ file_path = "../artifacts/9a9aad2b-..._train.csv"
    ↓ speichert file_path in DB (artifacts-Tabelle)

artifact_repository.get_artifact(artifact_id)
    ↓ liest record["file_path"] aus DB
    ↓ = "../artifacts/9a9aad2b-..._train.csv"

artifacts.py:get_artifact()
    ↓ filename = os.path.basename(file_path)
    ↓ = "9a9aad2b-..._train.csv"   ← hier liegt das Problem
    ↓ return FileResponse(..., filename=filename)
    ↓ → HTTP Header: Content-Disposition: attachment; filename="9a9aad2b-..._train.csv"
    ↓ → Browser zeigt UUID-Namen beim Download
```

---

### Problem-Kern: `artifacts.py` Zeile 50

**Datei:** `backend/src/gysi_ml/api/routes/artifacts.py`

**Ist-Zustand (Zeilen 49–55):**

```python
filename = os.path.basename(file_path)   # ← Disk-Dateiname (UUID-basiert)
mime_type, _ = mimetypes.guess_type(file_path)
media_type = mime_type or "application/octet-stream"
if media_type.startswith("image/"):
    return FileResponse(file_path, media_type=media_type)
return FileResponse(file_path, media_type=media_type, filename=filename)
```

**Problem:**
`os.path.basename(file_path)` liefert den physischen Dateinamen auf Disk — und der wurde in `split.py`
mit der `run_id` (UUID) als Präfix generiert. Der `Content-Disposition: attachment; filename="..."` Header
des HTTP-Response trägt dadurch den UUID-Namen, was der Browser direkt als Download-Dateinamen verwendet.

**Wichtig:**
`record` enthält bereits `record["type"]` (z.B. `"split_train"`, `"split_test"`, `"feature_importance"`).
Diese Information ist im Handler vorhanden und wird nur nicht für den Filename genutzt.

---

### Warum der Disk-Dateiname UUID-basiert ist (kein eigenständiger Bug)

**Datei:** `backend/src/gysi_ml/steps/preprocessing/split.py`

**Ist-Zustand `generate_artifact()` (Zeilen 73–84):**

```python
train_path = os.path.join(artifacts_path, f"{run_id}_train.csv")
test_path  = os.path.join(artifacts_path, f"{run_id}_test.csv")
self._df_train.to_csv(train_path, index=False)
self._df_test.to_csv(test_path, index=False)
return [
    {"type": "split_train", "file_path": train_path},
    {"type": "split_test",  "file_path": test_path},
]
```

Das UUID-Präfix ist **absichtlich** für Eindeutigkeit zwischen verschiedenen Runs — damit Artefakte
verschiedener Runs sich nicht gegenseitig überschreiben. Diese Datei-Benennung auf Disk ist **korrekt**
und soll **nicht geändert** werden. Nur der `Content-Disposition`-Header im HTTP-Response muss
entkoppelt werden.

---

### Vorhandene Infrastruktur im Frontend (kein Blocking-Problem)

**Datei:** `frontend/src/api/realTransport.ts`

Mapping von `type` → lesbares Label existiert bereits (Zeilen 303–311):

```typescript
function artifactTypeToLabel(type: string): string {
  const labels: Record<string, string> = {
    split_train: 'Trainingsdaten (CSV)',
    split_test: 'Testdaten (CSV)',
    feature_importance: 'Feature Importance',
  }
  return labels[type] ?? (type || 'Artifact')
}
```

Das Frontend zeigt `label` korrekt im UI — der Bug betrifft ausschließlich den Download-Dateinamen
(HTTP `Content-Disposition`).

---

## Betroffene Dateien

| Datei | Relevanz | Änderung nötig? |
|---|---|---|
| `backend/src/gysi_ml/api/routes/artifacts.py` | Hauptursache: Zeile 50 `filename = os.path.basename(file_path)` | **Ja — Pflicht** |
| `backend/src/gysi_ml/steps/preprocessing/split.py` | Erzeugt UUID-basierten Disk-Dateinamen | Nein — korrekt so |
| `backend/src/gysi_ml/steps/modeling/decision_tree.py` | Erzeugt `feature_importance_{run_id}.png` | Nein — Disk-Name korrekt |
| `backend/src/gysi_ml/steps/modeling/ebm.py` | Ähnliches Muster wie decision_tree.py | Nein — Disk-Name korrekt |
| `frontend/src/components/ResultCard.tsx` | `<a href=...>` ohne `download`-Attribut | Optional (Entscheidung 3) |
| `backend/tests/api/test_artifacts.py` | Kein Test für `Content-Disposition` Header | Neuer Test empfohlen |

---

## Lösungsansatz (nicht implementiert — wartet auf Entscheidungen)

**Backend-Fix in `artifacts.py`:**

Statt `os.path.basename(file_path)` ein Mapping von `record["type"]` auf semantischen Dateinamen
verwenden:

```python
# Vorschlag-Mapping (Entscheidung 1: exakte Namen festlegen)
_TYPE_TO_DOWNLOAD_FILENAME: dict[str, str] = {
    "split_train": "bike_trainingsdaten.csv",
    "split_test":  "bike_testdaten.csv",
    "feature_importance": "feature_importance.png",
}

filename = _TYPE_TO_DOWNLOAD_FILENAME.get(
    record.get("type", ""),
    os.path.basename(file_path)   # Fallback: alter Verhalten für unbekannte Typen
)
```

Zeile 49 in `artifacts.py` wird dabei ersetzt:
```python
# ALT:
filename = os.path.basename(file_path)

# NEU:
filename = _TYPE_TO_DOWNLOAD_FILENAME.get(record.get("type", ""), os.path.basename(file_path))
```

Der Rest des Handlers (`FileResponse`, Path-Traversal-Schutz, MIME-Type) bleibt **unverändert**.

---

## Auswirkung auf Bilder (Images)

**Achtung:** In Zeile 53–54 gibt es einen Sonderpfad für Bilder:

```python
if media_type.startswith("image/"):
    return FileResponse(file_path, media_type=media_type)   # ← KEIN filename-Parameter!
```

Für Bilder wird aktuell **gar kein** `filename` gesetzt — der Browser verwendet dann den letzten
URL-Pfadsegment-Teil als Name (`{artifact_id}`, also wieder eine UUID).

**Entscheidung 2** (siehe unten) betrifft diesen Fall: ob auch Bilder einen semantischen Dateinamen
bekommen sollen.

---

## Offene Entscheidungen — müssen beim Fix beantwortet werden

### Entscheidung 1 — Exakte Dateinamen der Download-Dateien

> **Frage:** Welche konkreten Dateinamen sollen die Downloads bekommen?

**Optionen:**

| Artefakt-Typ | Option A (Dataset-Präfix) | Option B (Generisch) | Option C (Run-Kontext) |
|---|---|---|---|
| `split_train` | `bike_trainingsdaten.csv` | `trainingsdaten.csv` | `trainingsdaten_{datum}.csv` |
| `split_test` | `bike_testdaten.csv` | `testdaten.csv` | `testdaten_{datum}.csv` |
| `feature_importance` (DT) | `decision_tree_feature_importance.png` | `feature_importance.png` | `feature_importance_{datum}.png` |
| `feature_importance` (EBM) | `ebm_feature_importance.png` | `feature_importance.png` | gleich wie DT → Kollision? |

**Hinweis zu Option C / Datum:** `record["created_at"]` ist in der DB vorhanden — das Datum wäre
technisch ableitbar, erfordert aber String-Parsing im Handler.

**Hinweis zu EBM vs. DT:** Beide Modelle erzeugen `type: "feature_importance"` — mit einem
generischen Namen würden beide die gleiche Datei `feature_importance.png` heißen. Falls der User
beide herunterlädt, würde der Browser eine überschreiben. Entweder unterschiedliche `type`-Werte
oder ein spezifischerer Name.

**Empfehlung Amelia:** Option B (generisch) für CSVs, Option mit Modell-Präfix für Bilder —
aber das ist Hannes' Entscheidung.

---

### Entscheidung 2 — Bilder: Filename setzen oder nicht?

> **Frage:** Soll der Bild-Pfad (aktuell ohne `filename`-Parameter) ebenfalls einen semantischen
> Namen bekommen, oder ist `<img>`-Anzeige (kein Download) der einzige Use Case?

**Ist-Zustand:**
```python
if media_type.startswith("image/"):
    return FileResponse(file_path, media_type=media_type)   # kein filename
```

**Kontext:** Der Browser zeigt Bilder inline an (kein Download-Dialog). Wenn der User
"Bild speichern" macht, erhält er den UUID-Namen. Downloads über `<a download>` im Frontend
würden bei Cross-Origin durch CORS beschränkt (daher greift Entscheidung 3).

**Optionen:**
- A: Bild-Pfad ebenfalls mit semantischem `filename` versehen (beide Branches vereinheitlichen)
- B: Bild-Branch unverändert lassen — Bilder werden ohnehin inline angezeigt, kein Download-Use-Case

---

### Entscheidung 3 — Frontend: `download`-Attribut am `<a>`-Tag ergänzen?

> **Frage:** Soll in `ResultCard.tsx` das `download`-Attribut am Anker-Tag gesetzt werden?

**Ist-Zustand** (`frontend/src/components/ResultCard.tsx`, Zeilen ~126–133):
```tsx
<a
  href={safeUrl}
  target="_blank"
  rel="noreferrer"
  className="resultArtifactLink"
>
```

**Option A:** `download`-Attribut hinzufügen:
```tsx
<a
  href={safeUrl}
  target="_blank"
  rel="noreferrer"
  download={artifact.label}   // oder ein berechneter Dateiname
  className="resultArtifactLink"
>
```

**Wichtige Einschränkung:** Das `download`-Attribut funktioniert bei `<a>`-Tags nur zuverlässig
für **Same-Origin**-URLs. Da Backend und Frontend auf der gleichen Origin laufen (`localhost`),
würde es in der Dev-Umgebung funktionieren. In Produktion hängt es von der Deployment-Konfiguration ab.

**Empfehlung Amelia:** Backend-Fix (Entscheidung 1) reicht aus — `Content-Disposition: attachment`
vom Backend gibt dem Browser bereits den richtigen Dateinamen. Frontend-`download`-Attribut
ist optional und redundant.

---

## Teststrategie (nach dem Fix)

Ein neuer Test sollte in `backend/tests/api/test_artifacts.py` (oder neu anlegen, falls nicht vorhanden)
prüfen:

```python
# Prüfen dass Content-Disposition einen lesbaren Filename trägt
response = client.get(f"/v1/artifacts/{artifact_id}")
assert response.status_code == 200
content_disposition = response.headers.get("content-disposition", "")
assert "9a9aad2b" not in content_disposition   # kein UUID im Dateinamen
assert "trainingsdaten.csv" in content_disposition   # oder der gewählte Name aus Entscheidung 1
```

---

## Zusammenfassung für den Dev-Agent

| | |
|---|---|
| **Root Cause** | `filename = os.path.basename(file_path)` in `artifacts.py:50` liefert den Disk-UUID-Namen |
| **Fix-Ort** | `backend/src/gysi_ml/api/routes/artifacts.py` — Zeile 50 |
| **Fix-Typ** | Mapping `record["type"] → lesbarer Dateiname`. Einzeiler + Dict-Konstante |
| **Nicht anfassen** | `split.py`, `decision_tree.py`, `ebm.py` — Disk-Benennung ist korrekt |
| **Nicht anfassen** | Path-Traversal-Schutz, MIME-Type-Logik, 404/403-Handler — alle korrekt |
| **Risiko** | Sehr gering. Nur `Content-Disposition`-Header ändert sich |
| **Voraussetzung** | Entscheidung 1 (Dateinamen) muss vor dem Fix von Hannes beantwortet werden |
| **Optional** | Entscheidung 2 (Bild-Branch) + Entscheidung 3 (Frontend `download`-Attribut) |
