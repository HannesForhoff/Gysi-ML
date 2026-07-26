# Showcase-Ablauf: gysi-ml Demo

Gesamtdauer: ca. 25–30 Minuten

---

## Vorbereitung

```bash
# Terminal 1 – Backend
cd backend
python -m gysi_ml.main

# Terminal 2 – Frontend
cd frontend
npm run dev
```

Frontend öffnen: `http://localhost:5173`

> **Hinweis:** Vor der Demo die SQLite-Datenbank leeren (`.local/gysi.db` löschen oder umbenennen),
> damit der Versionsbaum sauber und nachvollziehbar startet.

---

## Spec-Versionen im Überblick

| Version | Inhalt der Pipeline | Entsteht bei |
| --- | --- | --- |
| **v1** | dedup | Schritt 2.1 |
| v2 | + time_feature_encoding | Schritt 2.3 |
| v3 | + Spalten-Drop (dteday, mnth) | Schritt 2.4 |
| v4 | + encode_categorical (One-Hot) | Schritt 2.5 |
| v5 | + outlier_handling | Schritt 2.6 |
| **Branch A** | dedup → impute → split | Phase 3 (Leakage-Demo) |
| **Branch B** | dedup → split → impute → Decision Tree | Phase 4 (korrekte Pipeline) |

> **v1** ist der zentrale Ausgangspunkt: Alle Rollbacks in Phase 3 und 4 kehren zu v1 zurück.

---

## Phase 1 – Orientierung (3–4 Min.)

**Ziel:** Zeigen, dass das System den Datensatz kennt und zwischen „reden" und „ausführen" unterscheidet.

---

### 1.1 – Backend-Status

**Was zeigen:** Grüner Statusindikator oben im Frontend → Backend ist erreichbar, Datensatz ist geladen.

---

### 1.2 – Slash-Command `/overview`

```
/overview
```

**Was passiert:** Sofortige Antwort ohne LLM-Aufruf. Backend profiliert den Bike-Datensatz:
Spaltenübersicht, Datentypen, fehlende Werte, Wertebeispiele.

**Was zeigen:** Der Assistent kennt den Datensatz ohne Erklärung. Geschwindigkeit (kein LLM-Roundtrip).

---

### 1.3 – Daten-Tab: Rohdatensatz

**Daten-Tab** öffnen.

**Was zeigen:**
- Paginierte Tabelle mit Infinite Scroll
- Spaltenstatistik-Header: Datentyp, Min/Max/Ø, fehlende Werte je Spalte
- 17.379 Zeilen, 17 Spalten

---

### 1.4 – Infofrage ans LLM

```
Was bedeuten die Spalten casual und registered und warum sind sie für ein Modell problematisch?
```

**Was passiert:** LLM antwortet mit `action: "info"` — keine Ausführung, keine neue Spec-Version.
Versionsbaum bleibt leer.

**Was zeigen:** Das System unterscheidet „nur erklären" von „ausführen".

---

## Phase 2 – Preprocessing-Pipeline aufbauen (8–10 Min.)

**Ziel:** Eine sinnvolle Preprocessing-Pipeline Schritt für Schritt aufbauen.

---

### (2.1 – Duplikate entfernen → **v1**)

```
Entferne alle doppelten Zeilen aus dem Datensatz
```

**Was passiert:** `dedup`-Step direkt ausgeführt. Backend meldet Anzahl entfernter Duplikate.

**Was zeigen:**
- Erster Knoten erscheint im **Versionsbaum** (Sidebar) — das ist **v1**
- Info-Tab: Step „Duplikate entfernen" mit Metadaten (entfernte Zeilen)

> **Merke:** v1 = Ausgangspunkt für alle Rollbacks in Phase 3 und 4.

---

### 2.2 – Verteilungsplot (transient, kein Versionsknoten)

```
Zeig mir die Verteilung von cnt gruppiert nach season
```

**Was passiert:** Balken- und Boxplot als PNG erzeugt. Kein neuer Versionsknoten.

**Was zeigen:**
- **Info-Tab → Artefakte:** PNG erscheint, klickbar und downloadbar
- Versionsbaum **ändert sich nicht** — transiente Steps hinterlassen keine Spur in der Pipeline

---

### (2.3 – Zeitfeatures ableiten → **v2**)

```
Leite Wochentag und Monat aus der Datumsspalte dteday ab
```

**Was passiert:** `time_feature_encoding` mit `features: ["weekday", "month"]`. Neue Spalten entstehen.

**Was zeigen:**
- **Daten-Tab:** Neue Spalten `weekday` und `month` erscheinen
- Versionsbaum: **v2**

---

### 2.5 – One-Hot Encoding → **v4**

```
Wende One-Hot-Encoding auf season und weathersit an
```

**Was passiert:** `encode_categorical` mit `method: onehot`. Aus 2 Spalten entstehen mehrere
binäre Spalten (`season_1`, `season_2`, `season_3`, `season_4`, `weathersit_1`, …).

**Was zeigen:**
- **Daten-Tab:** Neue binäre Spalten sichtbar
- **Info-Tab → Aktive Pipeline:** Jetzt 3 Steps aufgelistet, jeder mit Status

---

### 2.6 – Ausreißer behandeln → **v5**

```
Behandle Ausreißer in windspeed und hum per IQR-Methode
```

**Was passiert:** `outlier_handling` mit `method: iqr`, nur für `windspeed` und `hum`.
Werte werden auf [Q1 − 1,5×IQR, Q3 + 1,5×IQR] gecappt.

**Was zeigen:**
- **Info-Tab → Aktive Pipeline → Step „Ausreißer":** Q1/Q3-Grenzen und Anzahl gecappter Werte
  je Spalte
- Versionsbaum: **v5** — fünf sauber verbundene Knoten, ein linearer Pfad

---

## Phase 3 – Rollback #1: Data Leakage demonstrieren (5–6 Min.)

**Ziel:** Zeigen, was passiert wenn Imputation **vor** dem Split ausgeführt wird — und wie das System warnt.

---

### 3.1 – Rollback auf v1

Versionsbaum-Sidebar → auf den **v1-Knoten** (Dedup) klicken → **„Rollback auf diese Version"** klicken.

**Was passiert:** Backend klont v1 als neue aktive Version. Ein **neuer Branch A** entsteht im Baum.
Die Pipeline enthält wieder nur den `dedup`-Step.

**Was zeigen:**
- Versionsbaum zeigt nun zwei Äste — der Phase-2-Pfad (v1→v5) **bleibt erhalten**, nichts geht verloren
- Aktiver Knoten (größerer Kreis) ist auf v1 gewechselt

---

### 3.2 – windspeed imputieren — OHNE vorherigen Split

```
Imputiere windspeed mit dem Median
```

**Was passiert:** `impute_missing` für `windspeed` mit `strategy: median` wird in die Spec eingefügt.
Spec jetzt: `[dedup → impute_windspeed]` — die Imputation lernt aus dem **gesamten Datensatz**.

**Was zeigen:** Normaler, erfolgreicher Run — das System erlaubt es, warnt aber beim nächsten Schritt.

---

### 3.3 – Split hinzufügen

```
Teile den Datensatz in Trainings- und Testdaten auf
```

**Was passiert:** `split`-Step wird **nach** der Imputation eingefügt.
Spec: `[dedup → impute_windspeed → split]`

**Was zeigen:** Die Pipeline sieht funktional aus — aber statistisch ist sie problematisch,
weil der Median aus Test- **und** Trainingsdaten gleichzeitig berechnet wurde.

---

### 3.4 – Decision Tree → ⚠ Data-Leakage-Warnung

```
Trainiere einen Decision Tree
```

**Was passiert:** Das LLM erstellt einen Vorschlag. Das Frontend zeigt eine **ProposalCard mit
gelbem Warnbanner**:

> ⚠ **Data-Leakage-Risiko erkannt!**
> Die folgenden Schritte würden *vor* dem Train/Test-Split ausgeführt:
> **Fehlende Werte imputieren (windspeed)**

**Was zeigen:**
- Das System erkennt die fehlerhafte Reihenfolge automatisch
- Der Nutzer muss trotzdem **bewusst bestätigen** — Entscheidungshoheit bleibt beim Menschen
- **Nicht bestätigen** — Demo-Punkt ist illustriert

---

## Phase 4 – Rollback #2: Korrekte Pipeline (6–8 Min.)

**Ziel:** Zeigen, wie eine korrekte Pipeline ohne Data Leakage aussieht und direkt zum Modell führt.

---

### 4.1 – Rollback auf v1 (erneut)

Versionsbaum → erneut auf den **v1-Knoten** klicken → **„Rollback auf diese Version"**.

**Was zeigen:**
- Versionsbaum hat jetzt drei Äste — Phase-2-Pfad, Phase-3-Pfad, neuer Branch B beginnt
- Baumstruktur vergleichbar mit Git-Branches

---

### 4.2 – Split zuerst

```
Teile den Datensatz auf: 80% Training, 20% Test
```

**Was passiert:** `split`-Step kommt als Erstes nach `dedup`. Spec: `[dedup → split]`.

**Was zeigen:**
- **Daten-Tab:** Filter **Train / Test / Alle** erscheint — erst jetzt verfügbar
- Train: ~13.900 Zeilen | Test: ~3.480 Zeilen

---

### 4.3 – Imputation NACH dem Split (kein Leakage)

```
Imputiere windspeed mit dem Median und cnt mit dem Mittelwert
```

**Was passiert:** Zwei `impute_missing`-Steps werden **nach** dem Split ausgeführt.
Median und Mittelwert werden nur aus den **Trainingsdaten gelernt** und dann auf Test angewendet.
Spec: `[dedup → split → impute_windspeed (median) → impute_cnt (mean)]`

**Was zeigen:**
- Spec-Reihenfolge ist korrekt — Split steht vor allen lernenden Steps
- Info-Tab: beide Imputation-Steps mit Strategien und imputierten Werten je Spalte

---

### 4.4 – Decision Tree trainieren — kein Fehler

```
Trainiere einen Decision Tree mit maximaler Tiefe 5
```

**Was passiert:** Direktausführung, **keine Leakage-Warnung**. Training auf Trainingsdaten,
Evaluation auf Testdaten.

**Was zeigen:**
- Keine gelbe Warnung mehr — die Reihenfolge ist korrekt
- ProposalCard **ohne** Warnbanner (direkter Kontrast zu Phase 3)

---

### 4.5 – Ergebnis auswerten

**Info-Tab → Letzter Run:**

- **RMSE, MAE, R²** für Train **und** Test
- Vergleich: Overfitting erkennbar wenn Train-R² deutlich besser als Test-R²

**Info-Tab → Artefakte:**

- **Feature-Importance-Plot** (PNG): welche Features tragen zum Modell bei?
- **Overfitting-Plot** (PNG): Validation Curve über verschiedene Tiefen
- **Trainingsdaten** und **Testdaten** als CSV downloadbar

**Daten-Tab:**

- Filter auf **Train** → die Daten, auf denen trainiert wurde
- Filter auf **Test** → die Daten, die das Modell nie gesehen hat

---

## Phase 5 – Meta & Abschluss (3–4 Min.)

**Ziel:** Systemübersicht und Komfort-Features demonstrieren.

---

### 5.1 – Slash-Command `/status`

```
/status
```

**Was passiert:** Sofortige Antwort ohne LLM: aktive Spec-Version, alle aktiven Steps, letzter
Run-Status und Metriken in lesbarer Form.

---

### 5.2 – Versionsbaum: Gesamtübersicht

Sidebar **„Spec-Verlauf"** aufzeigen.

**Was zeigen:**
- **Drei Branches**: Phase-2-Pfad (volle Preprocessing-Pipeline), Branch A (Leakage-Demo),
  Branch B (korrekte Pipeline mit Modell)
- **Farbcodierung**: Jeder Branch hat eine eigene Farbe
- **Run-Status-Punkte**: Grün = erfolgreicher Run, Rot = fehlgeschlagen, Grau = noch kein Run
- **Aktiver Knoten**: Größerer Kreis = gerade verwendete Version

**Kernbotschaft:** Nichts geht verloren. Jeder Schritt ist nachvollziehbar, jede Version
wiederherstellbar — wie ein vollständiges Git-Log der ML-Experimente.

---

### 5.3 – Slash-Command `/help`

```
/help
```

**Was zeigen:** Eingebaute Hilfetexte ohne LLM-Aufruf, offline verfügbar.

---

## Cheatsheet: Eingaben in der richtigen Reihenfolge

| # | Chat-Eingabe | Feature | Version |
| --- | --- | --- | --- |
| — | `/overview` | Datensatz-Profiling, kein LLM | — |
| — | *Daten-Tab öffnen* | Paginierte Tabelle + Spaltenstatistiken | — |
| — | Frage zu casual/registered | Info-Modus, kein Execute | — |
| 1 | Duplikate entfernen | Dedup, erster Versionsknoten | **v1** |
| — | cnt nach season plotten | Transient-Plot, kein Versionsknoten | — |
| 2 | Wochentag + Monat aus dteday ableiten | time_feature_encoding | v2 |
| 3 | dteday und mnth entfernen | Spalten-Drop | v3 |
| 4 | One-Hot für season, weathersit | encode_categorical | v4 |
| 5 | Ausreißer in windspeed, hum per IQR | outlier_handling, Step-Detail | v5 |
| — | **Rollback auf v1** | Branch A beginnt | — |
| 6 | windspeed mit Median imputieren | impute vor Split | Branch A |
| 7 | Datensatz aufteilen | split nach Imputation | Branch A |
| 8 | Decision Tree trainieren | ⚠ **Data-Leakage-Warnung** | Branch A |
| — | **Rollback auf v1** | Branch B beginnt | — |
| 9 | Datensatz aufteilen: 80/20 | split zuerst – korrekte Reihenfolge | Branch B |
| 10 | windspeed (Median) + cnt (Mean) imputieren | impute nach Split – kein Leakage | Branch B |
| 11 | Decision Tree, max. Tiefe 5 | Training korrekt, keine Warnung | Branch B |
| — | *Info-Tab: Feature Importance, Overfitting-Plot* | Artefakte auswerten | — |
| — | *Daten-Tab: Train/Test-Filter* | Split-Ansicht | — |
| — | `/status` | Metriken ohne LLM | — |
| — | *Versionsbaum zeigen* | Drei Branches, alle Knoten | — |
| — | `/help` | Eingebaute Hilfe | — |

---

## Kernbotschaften für den Vortrag

| # | Botschaft |
| --- | --- |
| 1 | **Natürliche Sprache → deterministisch** — Das LLM übersetzt nur, rechnet nie selbst |
| 2 | **Kein Blackbox-Workflow** — Jeder Step ist sichtbar, jeder Parameter nachvollziehbar |
| 3 | **Aktiver Leakage-Schutz** — Das System warnt automatisch bei statistisch falscher Reihenfolge |
| 4 | **Nutzer entscheidet immer** — Kein kritischer Step ohne Bestätigung |
| 5 | **Vollständige Versionshistorie** — Kein Schritt geht verloren, Rollback jederzeit möglich |
| 6 | **Explorative Sicherheit** — Fehlläufe (Branch A) bleiben als Lernnachweis erhalten |
