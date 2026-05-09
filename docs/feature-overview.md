# Feature-Übersicht: gysi-ml

Stand: Mai 2026

---

## Systemüberblick

Konversationeller ML-Assistent für den Bike-Datensatz. Der Nutzer beschreibt in natürlicher Sprache, was er tun möchte. Das LLM erzeugt daraus strukturierte Aktionen (JSON). Das Python-Backend führt alle Berechnungen deterministisch aus.

```
Nutzer → Chat-UI → FastAPI Backend → LLM (OpenAI) → Pipeline-Spec → Executor → Artefakte
```

---

## Backend – API-Endpunkte

Basis-URL: `http://localhost:8000/v1`

### Sessions

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `POST` | `/sessions` | Neue Session erstellen |
| `GET` | `/sessions` | Alle Sessions auflisten |
| `GET` | `/sessions/{id}` | Session mit Nachrichtenhistorie abrufen |

### Konversation & Ausführung

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `POST` | `/sessions/{id}/messages` | Nutzernachricht senden (löst LLM aus) |
| `POST` | `/sessions/{id}/confirm` | LLM-Vorschlag bestätigen und ausführen |
| `POST` | `/sessions/{id}/execute` | Pipeline direkt ausführen (ohne LLM) |

### Spec-Versionierung

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `GET` | `/sessions/{id}/spec` | Aktuelle Spec-Version abrufen |
| `GET` | `/sessions/{id}/spec/tree` | Versionsbaum (alle Versionen inkl. Runs) |
| `POST` | `/sessions/{id}/rollback` | Auf eine frühere Spec-Version zurücksetzen |

### Runs & Artefakte

| Methode | Pfad | Beschreibung |
| --- | --- | --- |
| `GET` | `/sessions/{id}/runs` | Alle Runs einer Session |
| `GET` | `/sessions/{id}/runs/{run_id}` | Run-Detail mit Metriken und Artefakten |
| `GET` | `/sessions/{id}/raw-data` | Rohdatensatz paginiert abrufen |
| `GET` | `/artifacts/{artifact_id}` | Artefakt-Datei herunterladen (PNG, CSV) |
| `GET` | `/capabilities` | Alle verfügbaren Pipeline-Steps auflisten |
| `GET` | `/health` | Backend-Status |

---

## Pipeline-Steps

### Preprocessing

| Step-Typ | Beschreibung | Wichtige Parameter |
| --- | --- | --- |
| `split` | Train/Test-Split (reproduzierbar) | `test_size` (Standard 0.2), `random_state` |
| `impute_missing` | Fehlende Werte imputieren | `strategy`: median / mean / most_frequent; `columns` |
| `outlier_handling` | Ausreißer-Behandlung per Capping | `method`: iqr / zscore; `zscore_threshold`; `columns` |
| `encode_categorical` | Kategorisches Encoding | `method`: label / onehot; `columns` |
| `time_feature_encoding` | Zeitfeatures aus Datumsspalte ableiten | `column` (Standard: dteday); `features`: weekday, month, day_of_month, year, quarter; `drop_original` |
| `dedup` | Exakt duplizierte Zeilen entfernen | keine Parameter |
| `correlation_filter` | Hochkorrelierte Features filtern (Pearson) | `threshold` (Standard 0.9); `analysis_only`; `features_to_drop` |
| `rare_category_bucketing` | Seltene Kategorien zu `__rare__` bündeln | `min_frequency` (Standard 0.01); `columns` |
| `cast_dtype` | Datentypen einzelner Spalten ändern | `columns`: Mapping Spalte → Zieltyp (int64, float64, category, bool, datetime64, ...) |
| `plot_distribution` | Verteilungsplot erzeugen | `feature`; `group_by` (optional) – transient, wird nicht in Spec gespeichert |

### Modeling

| Step-Typ | Beschreibung | Wichtige Parameter |
| --- | --- | --- |
| `train_decision_tree` | Decision-Tree-Regression | `max_depth` (Standard: unbegrenzt); `random_state` |
| `train_ebm` | Explainable Boosting Machine (Regression) | `random_state` |
| `catboost_feature_selection` | Feature-Selektion via CatBoost Importance | `top_n` (Standard 8); `analysis_only`; `features_to_drop` |

### Erzeugte Metriken (Modeling)

Alle Modellierungs-Steps liefern für Train **und** Test:

- **RMSE** – Root Mean Squared Error
- **MAE** – Mean Absolute Error
- **R²** – Bestimmtheitsmaß

---

## Erzeugte Artefakte

| Typ | Format | Beschreibung |
| --- | --- | --- |
| `split_train` | CSV | Trainingsdaten nach Split |
| `split_test` | CSV | Testdaten nach Split |
| `feature_importance` | PNG | Decision-Tree Feature Importance Plot |
| `ebm_global_explanation` | PNG | EBM Global Explanation Plot |
| `overfitting_plot` | PNG | Overfitting-Plot (Train vs. Test über Tiefe) |
| `learning_curve` | PNG | Learning Curve (Train vs. Test) |
| `correlation_filter_result` | CSV | Korrelationspaar-Analyse |
| `plot_distribution` | PNG | Verteilungsplot (Histogramm + Boxplot, optional gruppiert) |
| `column_stats` | JSON | Spaltenstatistiken (min, max, mean, dtype, fehlende Werte) |

---

## Sicherheits- und Qualitäts-Features

### Data-Leakage-Erkennung

Lernende Steps (`impute_missing`, `encode_categorical`, `outlier_handling`, `rare_category_bucketing`) werden automatisch erkannt. Liegen sie in der Spec **vor** dem `split`-Step, erscheint im Frontend eine Warnung, bevor der Nutzer bestätigt.

### Zweistufiger Bestätigungsfluss

1. Nutzer schreibt Anfrage → LLM generiert Vorschlag
2. Frontend zeigt `ProposalCard` mit allen Steps inkl. Parameter-Zusammenfassung
3. Nutzer klickt „Bestätigen & Ausführen" → Backend führt Pipeline aus

### Analyse-only-Modus

`correlation_filter` und `catboost_feature_selection` können zuerst im Analyse-Modus laufen: Es werden Ergebnisse angezeigt, aber keine Features entfernt. Im zweiten Schritt bestätigt der Nutzer konkret, welche Features fallen sollen.

### Spec-Versionierung & Rollback

Jede Änderung an der Pipeline-Spec erzeugt eine neue Version (mit Parent-Referenz). Der Nutzer kann im Frontend-Versionsbaum auf jede frühere Version zurückspringen.

### Slash-Commands

In das Chat-Eingabefeld direkt eingebbar:

| Command | Funktion |
| --- | --- |
| `/help` | Hilfetext anzeigen |
| `/overview` | Datensatz-Profiling der aktuellen Session |
| `/status` | Aktuelle Pipeline-Konfiguration und letzter Run |

---

## Frontend

### Tabs

| Tab | Inhalt |
| --- | --- |
| **Chat** | Konversationsansicht mit Nachrichten, Vorschlags-Cards und Ergebnis-Cards |
| **Daten** | Paginierte Datentabelle mit Spaltenstatistiken; Filter: alle / Train / Test |
| **Artefakte & Steps** | Aktive Pipeline-Steps, letzter Run-Status, herunterladbare Artefakte |

### Sidebar

- **Spec-Verlauf**: SVG-Versionsbaum mit Rollback-Funktion pro Knoten (farbcodiert nach Lane/Branch)

### Wichtige Komponenten

| Komponente | Funktion |
| --- | --- |
| `MessageList` | Zeigt Chat-Verlauf (User, Assistant, Proposals, Results, Errors) |
| `Composer` | Eingabefeld mit Senden-Button |
| `ProposalCard` | Vorschlags-Anzeige inkl. Data-Leakage-Warnung und Bestätigen-Button |
| `ResultCard` | Run-Ergebnis mit Status, Metriken und Artefakt-Links |
| `DataViewPanel` | Paginierte Tabelle + Spaltenstatistik-Header + Infinite Scroll |
| `ColumnSummaryHeader` | Statistiken je Spalte (Typ, fehlende Werte, Min/Max/Mean) |
| `InfoPanel` | Aktive Pipeline-Steps mit Ergebnis-Details je Step |
| `SpecHistoryPanel` | Container für den Versionsbaum |
| `VersionTreeGraph` | SVG-Versionsbaum mit Click-to-Rollback pro Knoten |
| `StatusPanel` | Backend-Verbindungsstatus |

### State & Polling

- **`chatReducer`**: Zentrales State-Management (Flux-Muster) für Chat, Session, Spec, Run, UI-Tabs
- **`useHealthPolling`**: Prüft regelmäßig den Backend-Status
- **`useRunPolling`**: Pollt laufende Runs bis zum Abschluss

---

## Persistenz

| Speicherort | Inhalt |
| --- | --- |
| `.local/gysi.db` (SQLite) | Sessions, Nachrichten, Specs, Runs, Proposals, Step-States, Artefakt-Metadaten |
| `artifacts/` (Dateisystem) | PNG-Plots, CSV-Exporte, JSON-Stats |

---

## Tech-Stack

| Bereich | Technologie |
| --- | --- |
| Backend | Python 3.11, FastAPI, scikit-learn, interpret (EBM), CatBoost, pandas, matplotlib |
| Frontend | React 18, TypeScript, Vite |
| LLM | OpenAI GPT (konfigurierbar via `.env`) |
| Persistenz | SQLite (via Python `sqlite3`) |
| Tests Backend | pytest, pytest-cov |
| Tests Frontend | Vitest |
