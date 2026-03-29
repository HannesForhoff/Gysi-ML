# Bug-Report & Analysedokument — Usability-Session 2026-03-25

**Erstellt:** 2026-03-25
**Kontext:** Erster Live-Test der Gysi-ML-Oberfläche durch Hannes.
**Zweck dieses Dokuments:** Vollständige Grundlage für andere Agenten und Chat-Sessions,
um den aktuellen Fehlerzustand, die Ursachen und die geplanten Fixes zu verstehen — ohne
die ursprüngliche Konversation erneut durchlesen zu müssen.

---

## Überblick der betroffenen Bereiche

| # | Titel | Bereich | Dringlichkeit |
| --- | --- | --- | --- |
| B-01 | Split-Pflicht für Preprocessing-Steps | Backend, Prompt | 🔴 Kritisch |
| B-02 | Keine Willkommens-Nachricht beim Start | Frontend | 🟡 Mittel |
| B-03 | Action-Log auf rechter Seite fehlt | Frontend, Backend | 🟠 Hoch |
| B-04 | Kein visuelles Feedback während Berechnung | Frontend | 🟡 Mittel |
| B-05 | Antworten nach Aktionen zu kurz und ohne Lerneffekt | Backend, LLM-Prompt | 🟠 Hoch |
| B-06 | Spec-Summary wird nach Execute nicht aktualisiert | Backend, Frontend | 🟠 Hoch |
| B-07 | Keine Artefakte beim Split / kein Schutz der Originaldatei | Backend | 🟠 Hoch |
| B-08 | Git-ähnlicher Verlauf (Spec-Versionen) nicht sichtbar | Frontend | 🟡 Mittel |
| B-09 | LLM schlägt von sich aus nichts vor | LLM-Prompt | 🟡 Mittel |
| B-10 | Frontend-Smoke-Tests kaputt (pre-existing) | Frontend, Tests | 🟠 Hoch |

---

## B-01 — Split-Pflicht für Preprocessing-Steps

### Problembeschreibung

Wenn der Nutzer einen Preprocessing-Schritt ausführen möchte (z. B. "Impute windspeed mit
Median"), bevor ein Train-Test-Split durchgeführt wurde, verweigert das System die Ausführung
mit der Fehlermeldung:

```
Step 'impute_missing' benötigt einen vorherigen 'split'-Step,
aber kein Split-Step wurde vor diesem Step gefunden.
```

Das System zwingt den Nutzer also, zuerst einen Split durchzuführen — auch bei reinen
Explorations- und Preprocessing-Schritten, die für den Lernprozess sinnvoll am Gesamtdatensatz
gezeigt werden sollten.

### Aktueller Stand (Code)

In `backend/src/gysi_ml/executor/spec_validator.py` ist eine Menge `REQUIRES_SPLIT` definiert,
die folgende Steps enthält:

```python
REQUIRES_SPLIT: frozenset[str] = frozenset({
    "impute_missing",
    "outlier_handling",
    "encode_categorical",
    "correlation_filter",
    "rare_category_bucketing",
    # Modeling Steps (Epic 2)
    "train_decision_tree",
    "train_ebm",
    "catboost_feature_selection",
})
```

Diese Validierung wird in `executor.py` und `message_service.py` aufgerufen. Zusätzlich steht
im System-Prompt an das LLM (`llm/prompts.py`):

```
Der `split`-Step muss vor allen Preprocessing-Steps (außer `dedup`) und Modeling-Steps stehen.
```

Das LLM wird also aktiv angewiesen, immer einen Split zu fordern.

### Ursache (Zweifach)

**Ursache 1 — Fachlich falsche Validierungsregel:**
Preprocessing-Steps wie `impute_missing`, `outlier_handling` und `encode_categorical` haben
kein zwingendes Data-Leakage-Problem, wenn sie auf dem Gesamtdatensatz ausgeführt werden.
Der Split ist nur für Modeling-Steps (Training/Evaluation) zwingend erforderlich. Die
Aufnahme aller Preprocessing-Steps in `REQUIRES_SPLIT` ist pädagogisch falsch und blockiert
sinnvolle explorative Workflows.

**Ursache 2 — Zustandsloses Spec-Design vs. schrittweiser UX:**
Das LLM erzeugt bei jedem `execute`-Action eine neue, isolierte Spec (z. B. nur
`[{type: "impute_missing"}]`). Der Validator prüft diese isolierte Spec — kein Split
darin → Fehler. Die bisherige Session-Spec (die einen abgeschlossenen Split enthalten
könnte) wird nicht automatisch als Kontext für die neue Spec herangezogen.

### Mögliche Fixes

**Fix A (Minimal, Kern-Fix):**
Alle Preprocessing-Steps aus `REQUIRES_SPLIT` entfernen. Nur Modeling-Steps behalten:

```python
REQUIRES_SPLIT: frozenset[str] = frozenset({
    "train_decision_tree",
    "train_ebm",
    "catboost_feature_selection",
})
```

Gleichzeitig den System-Prompt anpassen: Die Aussage "der `split`-Step muss vor allen
Preprocessing-Steps stehen" entfernen oder auf Modeling-Steps beschränken.

**Fix B (Ergänzend, bessere UX):**
Das LLM bei `execute` dazu bringen, die akkumulierte Session-Spec zu verwenden (alle
bisherigen Steps + der neue Step), statt nur den neuen Step zu senden. Der System-Prompt
enthält bereits die aktuelle Spec als Kontext — die Anweisung muss nur präzisiert werden.

### Dringlichkeit: 🔴 Kritisch

Dieser Fehler macht die grundlegende Preprocessing-Exploration vollständig unbrauchbar.
Kein Nutzer kann den Assistenten sinnvoll bedienen, solange dieser Fehler besteht.

---

## B-02 — Keine Willkommens-Nachricht beim Start

### Problembeschreibung

Wenn der Nutzer die Oberfläche öffnet, ist das Chat-Fenster leer. Es gibt keine Begrüßung,
keine Erklärung was das System kann, keine Aufforderung zum Start.

### Aktueller Stand (Code)

In `frontend/src/state/chatReducer.ts` wird der initiale State mit `messages: []` erzeugt:

```typescript
return {
  ui: { type: 'idle' },
  messages: [],  // ← leer, kein Willkommensmessage
  ...
}
```

In `frontend/src/App.tsx` gibt es keinen `useEffect` oder sonstigen Mechanismus, der beim
Appstart eine initiale Nachricht hinzufügt.

### Ursache

Schlicht nicht implementiert. Kein Willkommens-Message im initialen State, kein Backend-Call
beim Start der Session, der eine Greeting-Nachricht liefern würde.

### Mögliche Fixes

**Fix A (Frontend-only, einfach):**
In `createInitialChatState()` eine statische Willkommens-Nachricht in `messages[]` einfügen:

```typescript
messages: [
  {
    id: 'welcome',
    role: 'assistant',
    content: 'Hallo! Ich bin Gysi, dein ML-Assistent für den Bike-Sharing-Datensatz. ...',
    ts: new Date().toISOString(),
  }
]
```

**Fix B (Backend-gesteuert):**
Beim Erstellen einer neuen Session auf dem Backend eine initiale Willkommens-Nachricht
zurückgeben, die das Frontend dann als erste Chat-Nachricht anzeigt. Vorteil: Inhalt
zentral steuerbar, kann z. B. Datensatz-Info enthalten.

### Dringlichkeit: 🟡 Mittel

Keine Funktionalität kaputt, aber starke negative Wirkung auf den ersten Eindruck.

---

## B-03 — Action-Log auf rechter Seite fehlt

### Problembeschreibung

Laut Anforderungen sollte auf der rechten Seite der Oberfläche ein Log aller ausgeführten
Aktionen angezeigt werden — also ein chronologischer Verlauf der Pipeline-Schritte mit
Status, Zeitstempel und Ergebnis (z. B. "Duplikate entfernt: 0 gefunden", "Imputation:
3 Werte in Spalte windspeed ersetzt"). Dieses Panel existiert nicht.

### Aktueller Stand (Code)

Das `StatusPanel` (`frontend/src/components/StatusPanel.tsx`) zeigt:

- Backend-Verbindungsstatus
- Spec Summary (aktuelle Pipeline-Konfiguration)
- Letzter Run (Status + Metriken)
- Artefakte

Ein **Step-by-Step-Ausführungslog** ist nicht vorhanden. Weder ein eigener UI-Bereich noch
die notwendigen Daten dafür werden angezeigt.

**Backend-Seite:** Die `step_results` werden in `PipelineContext` gesammelt und auch im
Run-Result gespeichert (in der SQLite-DB via `run_repository`). Sie werden jedoch in der
Response des `execute`-Endpoints an das Frontend **nicht mitgesendet**.

In `message_service.py` (execute-Pfad) wird nur zurückgegeben:

```python
return {"type": "result", "run_id": result["run_id"], "explanation": explanation}
```

`step_results` fehlen komplett in der Response.

### Ursache

- Backend: `step_results` werden zwar berechnet, aber nicht in die API-Response
  eingebunden.
- Frontend: Kein UI-Element für einen Aktions-Log. Das StatusPanel zeigt nur
  Zustandsschnappschüsse, keinen Verlauf.

### Mögliche Fixes

**Fix A (Backend):**
Die `execute`-Response um `step_results` erweitern:

```python
return {
    "type": "result",
    "run_id": result["run_id"],
    "explanation": explanation,
    "step_results": result.get("step_results", []),  # ← hinzufügen
    "spec_summary": ...,  # ← siehe B-06
}
```

**Fix B (Frontend — neuer Log-Bereich im StatusPanel):**
Einen neuen Abschnitt "Ausgeführte Steps" im StatusPanel rendern, der die `step_results`
des letzten Runs auflistet. Langfristig: Verlauf über mehrere Runs hinweg akkumulieren.

### Dringlichkeit: 🟠 Hoch

Nutzer können nicht nachvollziehen was das System gemacht hat. Kernfeature für
Lernzweck des Assistenten.

---

## B-04 — Kein visuelles Feedback während Berechnung

### Problembeschreibung

Wenn der Nutzer eine Aktion auslöst (mit `execute`), passiert zwischen dem Absenden der
Nachricht und dem Erscheinen des Ergebnisses visuell nichts. Keine Ladeanzeige, kein
"Berechne...", kein Hinweis dass im Hintergrund etwas läuft.

### Aktueller Stand (Code)

Der `execute`-Pfad läuft **synchron**: Das Backend führt die Pipeline aus und gibt dann
die fertige Response zurück. Das Frontend sendet eine Nachricht, der UI-State wechselt auf
`sending_message`, aber es gibt keine explizite visuelle Entsprechung dafür im Chat.

Der `run_polling`-Mechanismus existiert im Code (in `useRunPolling`), wird aber nur für
den **Confirm-Pfad** (Proposal bestätigen → asynchroner Run) aktiviert — nicht für direkte
`execute`-Actions via Nachricht.

In `frontend/src/App.tsx` wird `isSending = state.ui.type === 'sending_message'` berechnet,
aber nur für das Deaktivieren des Composer-Inputs verwendet, **nicht** für eine sichtbare
Ladeanzeige im Chat.

### Ursache

- Direkte `execute`-Actions sind synchron → kein natürlicher Polling-Zyklus.
- `isSending`-State wird nicht visuell kommuniziert (kein Spinner, keine Statusnachricht).

### Mögliche Fixes

**Fix A (Einfach — Frontend only):**
Bei `ui.type === 'sending_message'` eine sichtbare Ladeanzeige im Chat rendern (z. B.
animierter Punkt oder "Gysi rechnet..."-Bubble).

**Fix B (Mittelfristig — asynchrones Execute):**
Den `execute`-Pfad ebenfalls asynchron gestalten (sofortiger Return mit `run_id`, dann
Polling wie beim Confirm-Pfad). Aufwändiger, aber konsistenter und skalierbar für
langläufige Schritte.

### Dringlichkeit: 🟡 Mittel

Kein funktionaler Fehler, aber deutlich schlechtere UX bei länger laufenden Operationen.

---

## B-05 — Antworten nach Aktionen zu kurz und ohne Lerneffekt

### Problembeschreibung

Nach der Ausführung eines Steps zeigt Gysi nur eine sehr knappe Meldung (z. B. "Run
abgeschlossen" oder "Ich habe alle Duplikate entfernt.") ohne konkrete Zahlen, Spaltennamen
oder Lernhinweise. Der Nutzer erfährt nicht:

- Wie viele Werte wurden verändert?
- In welchen Spalten wurde etwas geändert?
- Was bedeutet das für den Datensatz?
- Warum ist dieser Schritt sinnvoll?

**Zitat aus dem Test:**
> "Bist du schon fertig? Was genau wurde jetzt gemacht?"

### Aktueller Stand (Code)

**Backend:** `step.get_metadata()` liefert für jeden Step Metadaten. Beispiel `dedup`:

```python
{"rows_before": 17379, "rows_after": 17379, "duplicates_removed": 0}
```

Diese werden in `context.step_results` gesammelt, aber:
1. Nicht in die API-Response eingeschlossen (→ B-03)
2. Nicht für die LLM-Antwort verwendet

**Frontend:** `formatAssistantResponse()` in `App.tsx` rendert für `result`-Type:

```typescript
return `${response.message}\n\nStatus: ${response.status}${metrics}${artifacts}`
```

`response.message` ist aber nur der `explanation`-Text des LLMs — ohne Step-Metadaten.

**LLM-Prompt:** Es gibt keine Anweisung, die Ergebnisse eines Steps (Zahlen, Spalten) in
die Erklärung einzubauen. Das LLM kennt zur Zeit der Antwort-Generierung gar keine
Step-Ergebnisse, weil diese erst nach dem LLM-Aufruf entstehen (Pipeline wird nach dem
LLM-Call ausgeführt).

### Ursache

Architektur-bedingt: LLM formuliert die Erklärung **vor** der Ausführung. Die konkreten
Ergebniszahlen (wie viele Duplikate, welche Spalten) entstehen erst **während** der
Ausführung.

Es gibt keine zweite LLM-Runde nach der Ausführung, die die Metadaten in eine
lernorientierte Nachricht verarbeitet.

### Mögliche Fixes

**Fix A (Einfach — Frontend-seitig):**
Die `step_results`-Metadaten direkt im Frontend auslesen und als strukturierte
Info-Box nach der Nachricht anzeigen — kein zweiter LLM-Call nötig. Z. B.:

```
✅ dedup ausgeführt: 17.379 Zeilen geprüft, 0 Duplikate entfernt.
✅ impute_missing (windspeed, median): 3 Werte ersetzt.
```

**Fix B (Qualitativ besser — Post-Execution LLM-Runde):**
Nach der Ausführung einen zweiten LLM-Call machen und die `step_results` als Kontext
mitschicken. Das LLM formuliert dann eine pädagogisch wertvolle Zusammenfassung.
Aufwändiger, aber näher am Lernziel des Projekts.

### Dringlichkeit: 🟠 Hoch

Das ist der Kern-Lernwert des Tools. Ohne diese Rückmeldung ist Gysi für Bildungszwecke
kaum nützlich.

---

## B-06 — Spec-Summary wird nach Execute nicht aktualisiert

### Problembeschreibung

Nach dem Ausführen einer Aktion (execute) bleibt die Spec-Summary im rechten Panel
unverändert. Der Nutzer sieht nicht, welche Steps nun in der Pipeline enthalten sind.
Auch nach einem Train-Test-Split erscheint der Split-Step nicht in der Übersicht.

### Aktueller Stand (Code)

**Backend (`message_service.py`, execute-Pfad):**
Die Response enthält kein `spec_summary`-Feld:

```python
return {"type": "result", "run_id": result["run_id"], "explanation": explanation}
```

**Frontend (`chatReducer.ts`):**
Die Spec-Summary wird in `SEND_REQUEST_SUCCEEDED` nur aktualisiert wenn
`response.spec_summary` vorhanden ist:

```typescript
const specSummary =
  response.type === 'proposal' || response.type === 'result'
    ? response.spec_summary ?? state.specSummary  // ← null wenn keine summary mitkommt
    : ...
```

**Initial-Load:** Die Spec-Summary wird nur einmal beim Start geladen (via `fetchSpecSummary`
in `App.tsx`), danach nie wieder automatisch neu abgerufen.

### Ursache

Die `execute`-Route gibt keine aktualisierte Spec-Summary zurück. Das Frontend hat keinen
Fallback-Mechanismus (z. B. manueller Re-Fetch nach execute), um die neue Spec zu laden.

### Mögliche Fixes

**Fix A (Backend):**
Nach dem Execute die aktuelle Spec-Summary aus dem Repository laden und in die Response
einschließen:

```python
spec_summary = spec_repository.get_spec_summary(session_id=session_id, db_path=db_path)
return {
    "type": "result",
    "run_id": result["run_id"],
    "explanation": explanation,
    "spec_summary": spec_summary,  # ← hinzufügen
}
```

**Fix B (Frontend als Fallback):**
Nach jedem erfolgreichen Response den Spec-Summary-Endpoint erneut pollen. Weniger elegant,
aber unabhängig vom Backend.

### Dringlichkeit: 🟠 Hoch

Nutzer können nicht mit der Pipeline-Übersicht navigieren und verlieren den Überblick über
den aktuellen Zustand.

---

## B-07 — Keine Artefakte beim Split / kein Schutz der Originaldatei

### Problembeschreibung

Nach einem Train-Test-Split werden keine Artefakte erzeugt (keine CSV-Dateien für
Trainings- und Testdatensatz). Der Split existiert nur im Arbeitsspeicher während der
Pipeline-Ausführung und geht danach verloren.

Das bedeutet auch: Es gibt keine gesicherte Kopie der Daten, auf der gearbeitet wird —
die Originaldatei `data/raw/bikes.csv` ist theoretisch ungeschützt, auch wenn sie aktuell
nicht direkt überschrieben wird.

**Zitat aus dem Test:**
> "Sollte da nicht eigentlich dann eine Kopie vom Datensatz gemacht werden, auf der dann
> das ganze stattfindet damit die Original Datei nicht zerstört/verändert wird?"

### Aktueller Stand (Code)

`SplitStep.generate_artifact()` existiert nicht (erbt die Basis-Implementierung aus
`BaseStep`, die `None` zurückgibt). Der Executor in `executor.py` speichert nur dann
Artefakte, wenn `generate_artifact()` etwas zurückgibt:

```python
artifact_info = step.generate_artifact(artifacts_path=..., run_id=run_id)
if artifact_info:
    # → wird für SplitStep nie ausgeführt
```

### Ursache

`generate_artifact()` wurde für `SplitStep` nicht implementiert. Die Step-Klasse kennt
nach `transform()` die gesplitteten DataFrames, aber schreibt sie nicht ins Dateisystem.

### Mögliche Fixes

**Fix A (Split-Artefakte als CSVs):**
In `SplitStep.generate_artifact()` die Train- und Test-DataFrames als CSV in den
`artifacts/`-Ordner schreiben:

```python
def generate_artifact(self, artifacts_path: str, run_id: str) -> dict | None:
    train_path = f"{artifacts_path}/{run_id}_train.csv"
    test_path = f"{artifacts_path}/{run_id}_test.csv"
    self._df_train.to_csv(train_path, index=False)
    self._df_test.to_csv(test_path, index=False)
    return {"type": "split", "file_path": train_path}  # oder zwei separate Artefakte
```

Dafür muss `SplitStep` die DataFrames nach `transform()` zwischenspeichern.

**Fix B (Unveränderlichkeit der Originaldatei sicherstellen):**
Den `data_loader` so anpassen, dass immer eine Kopie des DataFrames in die Pipeline
geht (bereits der Fall via `df.copy()` oder ähnliches — prüfen ob das aktuell so ist).

### Dringlichkeit: 🟠 Hoch

Ohne persistierte Split-Artefakte ist kein reproduzierbarer ML-Workflow möglich.
Außerdem relevant für das Lernziel der Datensatz-Isolation.

---

## B-08 — Git-ähnlicher Verlauf (Spec-Versionen) nicht sichtbar

### Problembeschreibung

Laut Anforderungen sollte es einen navigierbaren Verlauf aller Pipeline-Versionen geben —
ähnlich einer Git-History — auf dem der Nutzer zurückgehen kann. Diese Übersicht fehlt
im Frontend komplett.

### Aktueller Stand (Code)

**Backend:** Die Spec-Versionierung ist in der SQLite-Datenbank vorhanden
(`spec_versions`-Tabelle via `spec_repository`). Es gibt einen Rollback-Endpoint
(`/rollback`) und die Logik in `message_service.py`. Die Infrastruktur existiert.

**Frontend:** Das StatusPanel zeigt die *aktuelle* Spec-Version (`specSummary.spec_version_id`),
aber keinen Verlauf früherer Versionen. Es gibt keinen API-Call der alle Spec-Versionen
einer Session lädt, und kein UI-Element dafür.

### Ursache

Das Backend hat die Versionierungsinfrastruktur implementiert, aber das Frontend nutzt
sie nicht (kein Versions-Historie-Endpoint-Aufruf, kein UI-Rendering).

### Mögliche Fixes

**Fix A (Anzeige der Spec-Versionen im StatusPanel):**
Einen API-Endpoint `/sessions/{session_id}/specs` aufrufen, der alle bisherigen
Spec-Versionen zurückgibt. Diese als klickbare Liste im StatusPanel anzeigen, mit
einem "zurückrollen"-Button pro Version.

**Fix B (Rollback über Chat):**
Vorerst den Rollback nur über Spracheingabe ermöglichen (z. B. "Gehe zurück zu Spec v1").
Das ist bereits im LLM-Prompt und `message_service.py` implementiert, wird aber
wahrscheinlich nicht visuell kommuniziert.

### Dringlichkeit: 🟡 Mittel

Functionality teilweise vorhanden (per Chat-Befehl), aber nicht sichtbar/entdeckbar.

---

## B-09 — LLM schlägt von sich aus nichts vor

### Problembeschreibung

Wenn der Nutzer vage Fragen stellt wie "Was würdest du mir vorschlagen?" oder "Mit was
fängt man an?", antwortet das LLM zwar inhaltlich korrekt (schlägt Steps vor), aber
die Vorschläge landen als gewöhnliche Text-Antwort ohne Handlungsoption. Es gibt
keinen automatischen "Vorschlag anzeigen + bestätigen"-Flow für Empfehlungen.

Außerdem fragt das LLM nicht aktiv nach, wenn Informationen fehlen.

**Zitat aus dem Test:**
> "Schlägt keine Möglichkeiten vor"
> "Auswahlsfenster waren immer nur 'Bestätigen und Auswählen'"

### Aktueller Stand (Code)

In `message_service.py` wird bei `action == "propose"` ein `ProposalCard` erzeugt. Das
LLM soll `action: "propose"` verwenden wenn die Eingabe vage ist. Aber bei einer
konkreten Frage wie "Was empfiehlst du?" wählt das LLM stattdessen `action: "execute"`
oder gibt nur ein `explanation`-Feld zurück ohne Steps, was zu einer leeren Proposal
führt.

Das Proposal-UI zeigt laut Tester nur "Bestätigen und Auswählen" ohne beschreibende
Texte je Step — der `parameters_summary`-Text fehlt in der Anzeige oder wird nicht
vom LLM befüllt.

### Ursache

- LLM-Prompt definiert `action: "propose"` für "vage Eingaben", aber nicht für
  den Fall "Nutzer bittet explizit um Empfehlungen".
- `parameters_summary` wird in den LLM-Antworten nicht konsequent befüllt.
- ProposalCard-Rendering zeigt möglicherweise nicht alle Step-Details an.

### Mögliche Fixes

**Fix A (Prompt-Erweiterung):**
Im System-Prompt explizit hinzufügen: "Wenn der Nutzer nach Empfehlungen oder einem
Einstieg fragt, verwende `action: 'propose'` und befülle `parameters_summary` für jeden
Step mit einer deutschen Beschreibung."

**Fix B (ProposalCard-UI):**
Sicherstellen dass `parameters_summary` je Step im ProposalCard-Rendering angezeigt
wird.

### Dringlichkeit: 🟡 Mittel

Beeinträchtigt die Führung von Anfängern, die nicht wissen womit sie anfangen sollen.

---

## B-10 — Frontend-Smoke-Tests kaputt (pre-existing)

### Problembeschreibung

In `frontend/src/App.test.tsx` schlagen 9 von 10 Tests fehl. Diese Fehler existieren
unabhängig von den B-01- bis B-09-Fixes — sie waren bereits vor den Bugfixes in diesem
Dokument vorhanden und wurden durch das Refactoring nicht verursacht.

Beispielfehler:

```
TestingLibraryElementError: Unable to find an element with the text:
/Ergebnis \(Mock\): Run abgeschlossen\./
```

Die Tests suchen nach Mock-Texten die im gerenderten DOM nicht auffindbar sind, weil
sich das Rendering zwischenzeitlich geändert hat (z. B. Markdown-Rendering splittet
Text auf mehrere DOM-Elemente auf, die `getByText` nicht als einzelne Match findet).

### Bestätigung (pre-existing)

Verifiziert per `git stash` — identische 9 Fehler auch auf dem ursprünglichen Commit
`7b177f6` ohne jegliche lokale Änderungen.

### Betroffene Testdatei

`frontend/src/App.test.tsx` — alle Integration-Smoke-Tests der Story 1.1

### Ursache

Wahrscheinliche Ursachen (noch nicht final analysiert):

1. **Markdown-Rendering**: `formatAssistantResponse()` erzeugt Markdown-Text, der im
   gerenderten HTML auf mehrere `<p>`-Elemente aufgeteilt wird. `screen.findByText(/Regex/)`
   findet den Text nicht weil er nicht in einem einzelnen Node steht.
2. **Mock-Transport-Isolation**: Tests verlassen sich auf einen Mock-Transport, der
   möglicherweise nicht korrekt isoliert wird (`vi.resetModules()` fehlt in einigen Tests).
3. **Async-Timing**: `findByText` mit Default-Timeout findet Elemente nicht die erst
   nach einem asynchronen State-Update erscheinen.

### Mögliche Fixes

**Fix A (Matcher anpassen):**
Statt `findByText(/Regex/)` eine Funktion als Matcher verwenden:

```typescript
await screen.findByText((content, el) =>
  el?.textContent?.includes('Ergebnis (Mock): Run abgeschlossen.') ?? false
)
```

**Fix B (Test-Isolation prüfen):**
`vi.resetModules()` und `vi.doUnmock()` in jeden Test der Mock-Transport-Isolation
benötigt konsistent einbauen.

### Dringlichkeit: 🟠 Hoch

Nicht funktionierende Tests verdecken Regressionen. Solange diese Tests rot sind,
kann kein verlässliches CI-Signal für das Frontend aufgebaut werden.

---

## Empfohlene Fix-Reihenfolge

| Priorität | Bug-ID | Begründung |
| --- | --- | --- |
| 1 | B-01 | Blockiert Grundfunktionalität total |
| 2 | B-10 | Pre-existing Testfehler — CI ohne Vertrauen |
| 3 | B-05 + B-03 | Fehlende Metadaten/Log (hängen zusammen, Backend-Change) |
| 4 | B-06 | Spec-Summary-Update (kleiner Backend-Change, großer UX-Gewinn) |
| 5 | B-07 | Split-Artefakte (wichtig für ML-Korrektheit) |
| 6 | B-02 | Willkommens-Nachricht (einfach, schnell) |
| 7 | B-04 | Loading-Feedback (kleines Frontend-Feature) |
| 8 | B-09 | Prompt-Tuning |
| 9 | B-08 | Spec-Verlauf UI (Backend-Infrastruktur bereits vorhanden) |

---

## Technische Schlüsseldateien (Referenz für Implementierung)

| Datei | Relevante Bugs |
| --- | --- |
| `backend/src/gysi_ml/executor/spec_validator.py` | B-01 |
| `backend/src/gysi_ml/llm/prompts.py` | B-01, B-05, B-09 |
| `backend/src/gysi_ml/services/message_service.py` | B-01, B-03, B-05, B-06 |
| `backend/src/gysi_ml/steps/preprocessing/split.py` | B-07 |
| `backend/src/gysi_ml/executor/executor.py` | B-03, B-07 |
| `frontend/src/state/chatReducer.ts` | B-02, B-06 |
| `frontend/src/App.tsx` | B-02, B-04, B-05 |
| `frontend/src/components/StatusPanel.tsx` | B-03, B-06, B-08 |
| `frontend/src/components/ProposalCard.tsx` | B-09 |
| `frontend/src/App.test.tsx` | B-10 |
