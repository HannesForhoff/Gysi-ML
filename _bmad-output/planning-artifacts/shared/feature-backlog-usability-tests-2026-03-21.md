# Feature-Backlog: Erkenntnisse aus Usability-Tests

**Datum:** 2026-03-21
**Autor:** Mary (Business Analyst)
**Quelle:** Erste manuelle Tests durch Hannes + Kollege
**Status:** Analysiert, bereit für Planning & Architektur

## Zusammenfassung

Aus den ersten Tests des gysi-ml Systems wurden 6 Ideen identifiziert. Nach Diskussion mit dem Stakeholder (Hannes) ergeben sich **4 Backend-relevante Features** für die nächste Planungsphase. Zwei Frontend-spezifische Items (#2 Chat-Scroll, #3 Markdown-Rendering) werden vom Frontend-Kollegen separat bearbeitet.

### Entscheidungen

| # | Idee | Entscheidung | Verantwortung |
| --- | --- | --- | --- |
| 1 | Onboarding / Welcome + Slash-Commands | **Umsetzen — dynamisch aus Backend** | Backend |
| 2 | Chat scrollbar | Verworfen hier (Frontend-Kollege) | Frontend |
| 3 | Markdown-Rendering | Verworfen hier (Frontend-Kollege) | Frontend |
| 4 | Datensatz-Überblick | **Umsetzen — gekoppelt mit #1** | Backend |
| 5 | Schrittweise Ausführung | **Umsetzen — Option A+C + Step-by-Step-Modus** | Backend + Frontend |
| 6 | Pipeline-Visualisierung (Git-Baum) | **Direkt planen und umsetzen (kein Post-MVP!)** | Backend + Frontend |

---

## Feature 1: Dynamisches Onboarding-System

### Problem

Der Chat startet leer. Weder der Evaluator noch ein neuer Nutzer weiß, was er tun kann, wie er interagieren soll oder welche Grenzen das System hat. Die `/capabilities`-Endpoint existiert, wird aber nie proaktiv angeboten.

### Anforderung

Das Backend liefert dynamisch:

1. **Welcome-Message** beim Session-Start (oder als abrufbarer Endpunkt)
2. **Slash-Commands** als erweiterter Hilfe-Mechanismus (`/help`, `/overview`, `/status`)

### Stakeholder-Entscheidung

> „Die Welcome Message sowie die Slash Commands sollen dynamisch aus dem Backend kommen." — Hannes

### Funktionale Anforderungen

#### FR-OB1: Welcome-Message bei Session-Erstellung

**Given** ein Nutzer erstellt eine neue Session (`POST /v1/sessions`)
**When** die Session erfolgreich erstellt wurde
**Then** enthält die Response ein Feld `welcome_message` mit einer strukturierten Begrüßung
**And** die Begrüßung enthält: Kurzanleitung, Beispiel-Prompts, Hinweis auf `/help` und Datensatz-Overview
**And** die Begrüßung wird im Backend generiert (nicht im Frontend hartcodiert)
**And** die Welcome-Message wird als erste `system`- oder `assistant`-Nachricht in der Message-History persistiert

#### FR-OB2: Slash-Command-Erkennung

**Given** ein Nutzer sendet eine Nachricht, die mit `/` beginnt
**When** die Nachricht an `POST /v1/sessions/{id}/messages` gesendet wird
**Then** erkennt das Backend den Slash-Command und verarbeitet ihn **ohne LLM-Aufruf**
**And** unbekannte Slash-Commands geben eine Fehlermeldung mit verfügbaren Commands zurück

#### FR-OB3: `/help`-Command

**Given** der Nutzer sendet `/help` oder `/help <thema>`
**When** das Backend den Command verarbeitet
**Then** gibt das System eine strukturierte Übersicht zurück, kategorisiert nach:

- **Daten erkunden**: Datensatz-Überblick, Spalteninfos, fehlende Werte, Statistiken
- **Preprocessing**: Bereinigung, Encoding, Feature Selection, Outlier Handling
- **Modellierung**: Training (Decision Tree, EBM), Metriken, Vergleich
- **Pipeline-Verwaltung**: Version wechseln, Rückgängig machen, Spec einsehen
- **Grenzen**: Nur Bike-Datensatz, kein eigener Code, LLM generiert nur Vorschläge

**And** bei `/help <thema>` wird nur die relevante Kategorie zurückgegeben

#### FR-OB4: `/overview`-Command (verknüpft mit Feature 2)

**Given** der Nutzer sendet `/overview`
**When** das Backend den Command verarbeitet
**Then** führt das Backend eine Datensatz-Profilierung aus und gibt den strukturierten Überblick zurück
(Details siehe Feature 2 — FR-DO1)

#### FR-OB5: `/status`-Command

**Given** der Nutzer sendet `/status`
**When** das Backend den Command verarbeitet
**Then** gibt das System zurück:

- Aktuelle Spec-Version (oder „Keine Pipeline konfiguriert")
- Anzahl durchgeführter Runs
- Letzter Run-Status + Metriken (falls vorhanden)
- Aktive Steps in der Pipeline

### Architektur-Implikationen

| Aspekt | Detail |
| --- | --- |
| **Neuer Endpunkt?** | Nein — Slash-Commands laufen über den bestehenden `POST /messages`-Endpunkt |
| **LLM-Bypass** | Slash-Commands werden **vor** dem LLM-Aufruf erkannt und direkt im Backend verarbeitet |
| **Neue Service-Klasse** | `CommandService` oder Erweiterung von `MessageService` mit Command-Router |
| **Welcome-Message** | Entweder in `POST /sessions`-Response oder als automatische erste Message nach Session-Erstellung |
| **Persistenz** | Slash-Command-Responses werden als `assistant`-Messages persistiert (Gesprächsverlauf vollständig) |
| **Konfigurierbarkeit** | Help-Texte als Konfigurationsdatei (YAML/JSON), nicht hartcodiert im Code |

### Inhalt der Welcome-Message (Entwurf)

```text
Willkommen bei Gysi! 👋

Ich bin dein ML-Assistent für den Bike-Sharing-Datensatz. Du sagst mir in 
natürlicher Sprache, was du tun möchtest — ich schlage konkrete Schritte vor 
und führe sie erst nach deiner Bestätigung aus.

So kannst du starten:
• „Zeig mir einen Überblick über die Daten"
• „Bereite die Daten für ein Regressionsmodell vor"
• „Trainiere einen Decision Tree"

Hilfe & Befehle:
• /help     — Alle Funktionen und Möglichkeiten im Überblick
• /overview — Datensatz-Überblick (Spalten, fehlende Werte, Statistiken)
• /status   — Aktueller Pipeline-Stand und letzte Ergebnisse

Hinweis: Ich kann ausschließlich den Bike-Sharing-Datensatz analysieren. 
Alle Berechnungen werden deterministisch im Backend ausgeführt — keine 
Schätzungen, keine Halluzinationen bei Ergebnissen.
```

### Priorität & Abhängigkeiten

- **Priorität:** P1 (Hoch) — direkt Demo-relevant für Evaluator
- **Abhängigkeit zu Feature 2:** `/overview`-Command ruft Datensatz-Profiling auf
- **Keine Abhängigkeit zu:** LLM-Orchestrierung (Commands brauchen kein LLM)
- **Aufwand:** Mittel (Neuer Command-Router + Help-Texte + Welcome-Integration)

---

## Feature 2: Datensatz-Überblick / Profiling

### Problem

Der Nutzer kann keinen strukturierten Überblick über den geladenen Datensatz abrufen. Stattdessen kommt eine generische LLM-Antwort, die keine echten Daten enthält. Ohne Dateneinblick kann der Nutzer keine informierte Entscheidung über Preprocessing-Schritte treffen.

### Anforderung

Das Backend bietet eine **Datensatz-Profilierungsfunktion**, die reale statistische Informationen über den Bike-Datensatz zurückliefert. Aufrufbar über `/overview`-Command und über natürliche Sprache.

### Funktionale Anforderungen

#### FR-DO1: Datensatz-Profilierung ausführen

**Given** der Nutzer fragt nach einem Datensatz-Überblick (per `/overview` oder natürliche Sprache)
**When** das Backend die Anfrage verarbeitet
**Then** führt das Backend folgende Analysen auf dem Rohdatensatz aus und gibt das Ergebnis strukturiert zurück:

| Analyse | Inhalt |
| --- | --- |
| **Grundinfos** | Zeilen-/Spaltenanzahl, Datensatzname, Dateigröße |
| **Spalten-Übersicht** | Name, Datentyp (dtype), Non-Null-Count pro Spalte |
| **Fehlende Werte** | Spalte, Anzahl fehlend, Prozent fehlend (sortiert nach Häufigkeit) |
| **Datentypen-Verteilung** | Anzahl numerisch / kategorisch / datetime |
| **Statistische Zusammenfassung** | Min, Max, Mean, Median, Std für numerische Spalten |
| **Erste Zeilen** | Head (5 Reihen) als tabellarische Struktur |
| **Unique-Wert-Verteilung** | Anzahl unique Values pro Spalte (Kardinalität) |

#### FR-DO2: LLM-Empfehlungen zum Datensatz

**Given** das Backend hat die Profilierung ausgeführt
**When** das Ergebnis an das LLM weitergegeben wird
**Then** generiert das LLM basierend auf den echten Daten kontextbezogene Empfehlungen:

- Auffälligkeiten (z.B. „temp und atemp sind hoch korreliert")
- Vorgeschlagene nächste Schritte (z.B. „Fehlende Werte in weathersit sollten imputiert werden")
- Hinweise auf Besonderheiten (z.B. „dteday enthält Datumsinformationen — Time-Features extrahierbar")

#### FR-DO3: Profilierung nach Preprocessing

**Given** der Nutzer hat bereits Preprocessing-Schritte ausgeführt
**When** der Nutzer erneut einen Überblick anfragt
**Then** zeigt das System den Zustand **nach** den bereits ausgeführten Transformationen

- Vorher/Nachher-Vergleich sinnvoll: „Vorher: 17.379 Zeilen → Nachher: 17.376 Zeilen (3 Duplikate entfernt)"

### Architektur-Implikationen

| Aspekt | Detail |
| --- | --- |
| **Neue Aktion im Action-Schema** | `action_type: "dataset_overview"` (ohne Steps / ohne Spec-Änderung) |
| **Neuer Service** | `DatasetService` oder `ProfilingService` — lädt CSV, führt `df.info()`, `df.describe()`, `df.isnull().sum()` etc. aus |
| **Kein Spec-Eingriff** | Profilierung ändert keine Pipeline-Spec, erzeugt keine neue Version |
| **LLM-Kontext** | Profiling-Ergebnis wird als kompakter Report ins LLM-Prompt injiziert für kontextualisierte Empfehlungen |
| **Slash-Command-Integration** | `/overview` triggert diesen Service direkt (ohne LLM); bei natürlicher Sprache erkennt das LLM die Intention und löst die Aktion aus |
| **Caching** | Profiling des Rohdatensatzes kann gecacht werden (ändert sich nicht); Post-Preprocessing-Profiling basiert auf Sitzungs-State |

### Priorität & Abhängigkeiten

- **Priorität:** P1 (Hoch) — Grundlage für informierte Nutzerentscheidungen
- **Abhängigkeit von:** Feature 1 (für `/overview`-Command-Routing)
- **Aufwand:** Mittel (Profiling-Logik ist technisch einfach; Integration in LLM-Kontext + Command-Routing wichtig)

---

## Feature 3: Schrittweise Ausführung (Selective + Step-by-Step)

### Problem

Bei einem Proposal gibt es nur einen Button: „Bestätigen & Ausführen". Dieser führt **alle** vorgeschlagenen Schritte auf einmal aus. Der Nutzer kann weder einzelne Steps abwählen noch Schritt für Schritt vorgehen. Das widerspricht dem didaktischen Kern des Projekts: Der Nutzer soll lernen, verstehen und bewusst entscheiden.

### Stakeholder-Entscheidung

> „Ja eine Kombination aus Option A und C ist gut. Aber ein Schritt für Schritt ist fast genauso wichtiger und extrem wichtig für den Beleg." — Hannes

### Anforderung

Zwei kombinierte Modi:

1. **Selektive Bestätigung (Option A+C):** Nutzer kann einzelne Steps aus einem Proposal an-/abwählen vor der Ausführung
2. **Step-by-Step-Modus:** Nutzer führt einen Step nach dem anderen aus — nach jedem Step sieht er das Ergebnis und entscheidet, ob und wie es weitergeht

### Funktionale Anforderungen

#### FR-SE1: Selektive Step-Bestätigung

**Given** das Backend hat einen Proposal mit mehreren Steps zurückgegeben
**When** der Nutzer `POST /v1/sessions/{id}/confirm` aufruft
**Then** akzeptiert der Endpunkt ein optionales Feld `confirmed_steps`

```json
{
  "proposal_id": "abc-123",
  "confirmed_steps": [0, 1, 3]  // Indices der gewählten Steps
}
```

**And** wenn `confirmed_steps` fehlt, werden alle Steps ausgeführt (Rückwärtskompatibilität)
**And** die Pipeline-Spec wird nur mit den bestätigten Steps erstellt und ausgeführt
**And** die nicht bestätigten Steps werden in der Spec als `enabled: false` markiert

#### FR-SE2: Step-by-Step-Ausführungsmodus

**Given** das Backend hat einen Proposal mit mehreren Steps zurückgegeben
**When** der Nutzer `POST /v1/sessions/{id}/confirm` mit `"mode": "step_by_step"` aufruft
**Then** führt das Backend **nur den ersten (aktiven) Step** aus
**And** die Response enthält:

- Ergebnis des ausgeführten Steps (Metriken, Zusammenfassung)
- Verbleibende Steps als neuer Vorschlag
- Aufforderung zur Bestätigung des nächsten Steps

```json
{
  "type": "step_result",
  "completed_step": {
    "type": "dedup",
    "summary": "3 Duplikate entfernt. 17.376 Zeilen verbleiben."
  },
  "remaining_steps": [
    {"type": "imputation", "params": {"method": "median"}},
    {"type": "encoding", "params": {"method": "onehot"}}
  ],
  "next_action": "Nächster Schritt: Imputation (Median). Bestätigen, überspringen oder anpassen?"
}
```

#### FR-SE3: Step-by-Step Fortführung

**Given** ein Step-by-Step-Vorgang läuft
**When** der Nutzer den nächsten Step bestätigt (per Chat oder Confirm)
**Then** führt das Backend den nächsten Step aus, auf den Daten des vorherigen Steps aufbauend
**And** nach dem letzten Step wird das Gesamtergebnis zusammengefasst

#### FR-SE4: Step-by-Step Abbruch/Modifikation

**Given** ein Step-by-Step-Vorgang läuft
**When** der Nutzer per Chat einen Step modifizieren möchte (z.B. „Nutze Mean statt Median")
**Then** aktualisiert das LLM den aktuellen Step und wartet erneut auf Bestätigung
**When** der Nutzer den Vorgang abbrechen möchte (z.B. „Stopp" oder „Das reicht erstmal")
**Then** beendet das System den Step-by-Step-Modus und zeigt eine Zusammenfassung der bisher ausgeführten Steps

### Architektur-Implikationen

| Aspekt | Detail |
| --- | --- |
| **Confirm-Contract-Änderung** | `POST /confirm`-Body wird erweitert um `confirmed_steps` (optional, Array von Indices) und `mode` (optional, `"all"` \| `"step_by_step"`) |
| **Neuer Session-State** | Bei Step-by-Step: Session braucht einen `step_by_step_state` mit aktuellem Fortschritt, Zwischen-Daten und verbleibenden Steps |
| **Zwischen-Persistenz** | Zwischen-Ergebnisse (DataFrame nach jedem Step) müssen temporär gehalten werden (in-memory oder serialisiert) |
| **Proposal-Service-Erweiterung** | `ProposalService.confirm_proposal()` muss Step-Selektion und Step-by-Step-Logik unterstützen |
| **Neue Response-Typen** | `type: "step_result"` als neuer Nachrichtentyp neben `proposal` und `result` |
| **Frontend-Implikation** | Frontend braucht Checkbox-UI für Steps + Step-by-Step-Fortschrittsanzeige (Info für Frontend-Kollegen nötig) |
| **Rückwärtskompatibilität** | Bestehender Confirm-Flow (ohne `confirmed_steps` / ohne `mode`) funktioniert weiterhin wie bisher |

### Didaktischer Wert (Beleg-Relevanz)

Der Step-by-Step-Modus ist zentral für die **wissenschaftliche Argumentation** der Belegarbeit:

- Der Nutzer sieht nach **jedem** Schritt, was passiert ist (z.B. „47 fehlende Werte imputiert")
- Er kann bewusste Entscheidungen treffen: „Versuche Mean statt Median" nach Sichtung der Ergebnisse
- Das System wird zum **interaktiven Lernwerkzeug** statt zur Black-Box  
- Der Evaluator kann das Bestätigungsprinzip **Step für Step** nachvollziehen — deutlich überzeugender als „ein Knopf, alles auf einmal"

### Priorität & Abhängigkeiten

- **Priorität:** P1 (Hoch) — explizit als „extrem wichtig für den Beleg" markiert
- **Aufwand:** Hoch (Backend-Contract-Änderung + Session-State + Zwischen-Persistenz + neuer Response-Typ)
- **Abhängigkeit:** Confirm-Endpoint muss erweitert werden; Frontend muss Checkboxen + Step-Fortschritt darstellen
- **Empfehlung:** Selektive Bestätigung (FR-SE1) zuerst, Step-by-Step (FR-SE2–SE4) als zweiter Schritt

---

## Feature 4: Pipeline-Versionsbaum (Git-Baum-Visualisierung)

### Problem

Der Nutzer hat keine visuelle Übersicht über den Verlauf seiner Pipeline-Veränderungen. Die Spec-Versionierung existiert im Backend (Tabelle `spec_versions`), aber es gibt keine Darstellung als Baumstruktur mit Eltern-Kind-Beziehungen. Laut Systemkonzept ist die Möglichkeit, „zu früheren Pipeline-Zuständen zurückzukehren", ein Kernfeature — die Visualisierung macht das navigierbar.

### Stakeholder-Entscheidung

> „Ne nicht direkt als Platzhalter. Lass das direkt Planen um das umzusetzen. Das ist eine sehr wichtige Funktion/Feature." — Hannes

### Anforderung

Ein **visueller Pipeline-Versionsbaum** im rechten Panel der UI, der:

- Alle Spec-Versionen als Knoten zeigt
- Eltern-Kind-Beziehungen darstellt (welche Version entstand aus welcher)
- Den aktuellen Stand hervorhebt
- Navigation zu älteren Versionen ermöglicht (Rollback)
- Letzte Änderungen pro Version anzeigt

### Funktionale Anforderungen

#### FR-VB1: Parent-Child-Tracking in Spec-Versionen

**Given** eine neue Spec-Version wird erstellt (durch LLM-Aktion oder Confirm)
**When** die Version in `spec_versions` persistiert wird
**Then** enthält der Eintrag ein `parent_spec_id`-Feld, das auf die Vorgängerversion verweist
**And** die erste Version einer Session hat `parent_spec_id: null`

**Schema-Änderung (spec_versions):**

```sql
ALTER TABLE spec_versions ADD COLUMN parent_spec_id TEXT REFERENCES spec_versions(spec_id);
ALTER TABLE spec_versions ADD COLUMN change_summary TEXT;  -- z.B. "Imputation: median → mean"
```

#### FR-VB2: API-Endpunkt für Versionsbaum

**Given** eine Session mit mehreren Spec-Versionen existiert
**When** `GET /v1/sessions/{id}/spec/tree` aufgerufen wird
**Then** gibt das Backend den vollständigen Versionsbaum zurück:

```json
{
  "session_id": "...",
  "active_spec_id": "spec-v3",
  "versions": [
    {
      "spec_id": "spec-v1",
      "version": "v1",
      "parent_spec_id": null,
      "change_summary": "Initiale Pipeline: Dedup + Imputation + Encoding + Split",
      "created_at": "2026-03-21T10:00:00Z",
      "has_runs": true,
      "last_run_status": "completed"
    },
    {
      "spec_id": "spec-v2",
      "version": "v2",
      "parent_spec_id": "spec-v1",
      "change_summary": "Imputation: median → mean",
      "created_at": "2026-03-21T10:15:00Z",
      "has_runs": true,
      "last_run_status": "completed"
    },
    {
      "spec_id": "spec-v3",
      "version": "v3",
      "parent_spec_id": "spec-v2",
      "change_summary": "+ Outlier Handling (IQR)",
      "created_at": "2026-03-21T10:30:00Z",
      "has_runs": false,
      "last_run_status": null
    }
  ]
}
```

#### FR-VB3: Change-Summary-Generierung

**Given** eine neue Spec-Version wird aus einer bestehenden erzeugt
**When** die Änderungen zwischen alter und neuer Spec verglichen werden
**Then** erzeugt das Backend ein menschenlesbares `change_summary`:

- Hinzugefügte Steps: „+ Outlier Handling (IQR)"
- Entfernte Steps: „− Correlation Filter"
- Geänderte Parameter: „Imputation: median → mean"
- Aktivierung/Deaktivierung: „Encoding deaktiviert"

#### FR-VB4: Rollback auf frühere Version

**Given** der Nutzer wählt eine ältere Version im Baum (oder per Chat „Gehe zu v1")
**When** ein Rollback ausgelöst wird
**Then** wird die ältere Spec als Basis für eine **neue** Version kopiert (kein Überschreiben)
**And** die neue Version hat als `parent_spec_id` die aktuelle (vor dem Rollback)
**And** `change_summary` enthält „Rollback auf v1"
**And** die alte Version und ihre Runs bleiben unverändert (Audit-Trail)

#### FR-VB5: Branching (linearer Baum mit Rollback-Abzweigungen)

**Given** der Nutzer macht ein Rollback auf v1 und erstellt von dort neue Versionen
**When** der Baum dargestellt wird
**Then** zeigt der Baum eine Abzweigung:

```
[v1] Initiale Pipeline
  ├── [v2] Imputation: mean
  │    └── [v3] + Outlier Handling
  └── [v4] Rollback auf v1 → Imputation: KNN   ← aktiv
       └── [v5] + Encoding (Grouped)
```

**Hinweis:** Dies ergibt sich natürlich aus dem Parent-Child-Tracking — kein explizites Branch-Konzept nötig, solange `parent_spec_id` korrekt gesetzt wird.

### Architektur-Implikationen

| Aspekt | Detail |
| --- | --- |
| **Schema-Migration** | `spec_versions` braucht `parent_spec_id` + `change_summary` (neue Spalten) |
| **Neuer Endpunkt** | `GET /v1/sessions/{id}/spec/tree` — aggregiert Versionen + Run-Status |
| **Spec-Diff-Logik** | Neuer Utility: `spec_diff(old_spec, new_spec) → change_summary` |
| **Rollback-Logik** | Erweiterung im `SpecRepository` — alte Version kopieren, neue anlegen |
| **LLM-Aktion** | Neue Action `"rollback"` mit `target_spec_id` |
| **Frontend-Implikation** | Baumdarstellung im rechten Panel (Bibliothek wie `react-d3-tree` oder custom SVG); Klick → Details; Doppelklick/Button → Rollback |
| **Kein Branch-Management** | Kein explizites Branch-Modell nötig — der Baum ergibt sich aus den parent-child-Beziehungen; „aktiver Kopf" ist die zuletzt verwendete Version |

### Beleg-Relevanz

- Macht das **Versionierungskonzept aus dem Systemkonzept** sichtbar und greifbar
- Der Evaluator sieht auf einen Blick: „Der Nutzer hat 5 Varianten ausprobiert, Variante 3 war am besten"
- Unterstützt die **Nachvollziehbarkeit** (ein explizites Ziel des Systemkonzepts)
- Ermöglicht das im Systemkonzept beschriebene **explorative Arbeiten** mit der Möglichkeit zur Rückkehr

### Priorität & Abhängigkeiten

- **Priorität:** P1 (Hoch) — explizit als „sehr wichtig" eingestuft, direkt planen
- **Aufwand:** Hoch (Schema-Migration + neuer Endpunkt + Spec-Diff + Rollback-Logik + Frontend-Baum)
- **Abhängigkeit:** Schema-Migration muss zuerst (parent_spec_id); Rollback hängt vom Baum-Tracking ab
- **Backend zuerst:** API-Endpunkt + Datenstruktur können unabhängig vom Frontend gebaut und getestet werden

---

## Gesamtübersicht: Neue Anforderungen

### Neue Functional Requirements (vorgeschlagen)

| ID | Anforderung | Feature |
| --- | --- | --- |
| FR-OB1 | Welcome-Message dynamisch bei Session-Start | Feature 1 |
| FR-OB2 | Slash-Command-Erkennung (`/`-Prefix) ohne LLM | Feature 1 |
| FR-OB3 | `/help`-Command mit kategorisierter Funktionsübersicht | Feature 1 |
| FR-OB4 | `/overview`-Command triggert Datensatz-Profilierung | Feature 1+2 |
| FR-OB5 | `/status`-Command zeigt Pipeline- und Run-Zustand | Feature 1 |
| FR-DO1 | Datensatz-Profilierung (Spalten, Missing, Statistik, Head) | Feature 2 |
| FR-DO2 | LLM-Empfehlungen basierend auf Profiling-Daten | Feature 2 |
| FR-DO3 | Profilierung nach Preprocessing (Vorher/Nachher) | Feature 2 |
| FR-SE1 | Selektive Step-Bestätigung (`confirmed_steps` in Confirm) | Feature 3 |
| FR-SE2 | Step-by-Step-Modus (`mode: "step_by_step"`) | Feature 3 |
| FR-SE3 | Step-by-Step Fortführung (nächster Step) | Feature 3 |
| FR-SE4 | Step-by-Step Abbruch und Modifikation | Feature 3 |
| FR-VB1 | Parent-Child-Tracking in Spec-Versionen | Feature 4 |
| FR-VB2 | API-Endpunkt für Versionsbaum | Feature 4 |
| FR-VB3 | Change-Summary-Generierung (Spec-Diff) | Feature 4 |
| FR-VB4 | Rollback auf frühere Version | Feature 4 |
| FR-VB5 | Branching durch Rollback-Abzweigungen | Feature 4 |

### Neue API-Endpunkte (vorgeschlagen)

| Methode | Pfad | Beschreibung | Feature |
| --- | --- | --- | --- |
| `GET` | `/v1/sessions/{id}/spec/tree` | Versionsbaum abrufen | Feature 4 |

### Geänderte API-Endpunkte

| Methode | Pfad | Änderung | Feature |
| --- | --- | --- | --- |
| `POST` | `/v1/sessions` | Response enthält `welcome_message` + initiale Assistant-Message | Feature 1 |
| `POST` | `/v1/sessions/{id}/messages` | Slash-Command-Routing vor LLM | Feature 1 |
| `POST` | `/v1/sessions/{id}/confirm` | `confirmed_steps` (optional) + `mode` (optional) im Body | Feature 3 |

### Schema-Änderungen (SQLite)

| Tabelle | Änderung | Feature |
| --- | --- | --- |
| `spec_versions` | `+ parent_spec_id TEXT` (FK → spec_versions) | Feature 4 |
| `spec_versions` | `+ change_summary TEXT` | Feature 4 |

### Neue LLM-Aktionen (Action-Schema-Erweiterung)

| Aktion | Beschreibung | Feature |
| --- | --- | --- |
| `dataset_overview` | Datensatz-Profilierung triggern | Feature 2 |
| `rollback` | Spec auf ältere Version zurücksetzen | Feature 4 |

---

## Empfohlene Implementierungsreihenfolge

```
Phase A: Grundlagen (unabhängig voneinander startbar)
├── Feature 1: Slash-Commands + Welcome     [Backend]
├── Feature 2: Datensatz-Profilierung       [Backend]
└── Feature 4: Schema-Migration + Tree-API  [Backend - Schema zuerst]

Phase B: Aufbauend
├── Feature 3: Selektive Bestätigung        [Backend + Frontend]
├── Feature 3b: Step-by-Step-Modus          [Backend + Frontend]
└── Feature 4b: Rollback-Logik              [Backend]

Phase C: Frontend-Integration
├── Feature 4c: Baum-Visualisierung         [Frontend]
├── Feature 3c: Checkbox-UI + Fortschritt   [Frontend]
└── Feature 1c: Welcome-Rendering           [Frontend]
```

---

## Offene Fragen für Architektur-Phase

1. **Step-by-Step Zwischen-State:** Wo wird der DataFrame zwischen Steps gehalten? In-Memory (SessionState-Objekt) oder serialisiert (Pickle/Parquet in temp-Verzeichnis)?
2. **Spec-Diff-Granularität:** Reicht Step-Level-Diff (hinzugefügt/entfernt/geändert) oder brauchen wir Parameter-Level-Diff?
3. **Rollback als LLM-Aktion oder als dedizierter Endpunkt?** Option A: Nutzer sagt „Gehe zurück zu v1" → LLM erzeugt `rollback`-Aktion. Option B: Dedizierter `POST /sessions/{id}/rollback` Endpunkt (Frontend kann direkt aufrufen).
4. **Welcome-Message Personalisierung:** Soll die Welcome-Message je nach vorhandenem Session-State variieren (z.B. „Willkommen zurück! Deine letzte Pipeline war v3 mit 3 Steps")?

---

## Hinweise für den Frontend-Kollegen

Folgende Items sind separat zu bearbeiten (Quelle: gleiche Usability-Tests):

- **Chat scrollbar machen** (CSS/Layout-Fix in ChatLayout.tsx / MessageList.tsx)
- **Markdown-Rendering** in Assistant-Messages einbauen (z.B. `react-markdown` + `remark-gfm`)
- **Sicherheitshinweis:** Kein `dangerouslySetInnerHTML` — `react-markdown` rendert als React-Komponenten (XSS-sicher gemäß NFR5)
