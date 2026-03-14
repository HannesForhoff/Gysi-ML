# Domain & Technical Research Report — gysi-ml

> **Datum:** 2026-03-14
> **Erstellt von:** Mary (Business Analyst)
> **Typ:** Kombinierte Domain- und Technical-Research
> **Ziel:** Fundierte Wissensbasis für die Implementierung des gysi-ml Backends

---

## Teil A: Domain Research

### 1. Bike Sharing Dataset — Herkunft und Charakteristiken

**Quelle:** UCI Machine Learning Repository (ID 275), auch auf Kaggle verfügbar.
**Autor:** Hadi Fanaee-T, Laboratory of Artificial Intelligence and Decision Support (LIAAD), University of Porto.
**Lizenz:** Creative Commons Attribution 4.0 International (CC BY 4.0).
**Zitation:** Fanaee-T, H. (2013). Bike Sharing [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5W894>

#### 1.1 Dataset-Grunddaten

| Eigenschaft | Wert |
| --- | --- |
| Herkunft | Capital Bikeshare System, Washington D.C., USA |
| Zeitraum | 2011–2012 |
| Granularität | Stündlich (`hour.csv`: 17.379 Records) und täglich (`day.csv`: 731 Records) |
| Aufgabentyp | Regression (Vorhersage der Ausleihanzahl) |
| Feature-Typen | Integer, Real, Categorical, Date |
| Originale Missing Values | Laut UCI: **Nein** — das Originaldataset hat keine Missing Values |

**Wichtiger Hinweis:** Das in `data/raw/bikes.csv` vorliegende Dataset ist eine **modifizierte Version** des Originals. Es enthält künstlich eingeführte Missing Values (mindestens in `mnth` und `weathersit`) und hat eine angepasste Spaltenstruktur (ohne `instant`, `weekday`, `workingday`, `casual`, `registered`). Dies ist bewusst für die Belegarbeit so gestaltet, um Missing Value Handling üben zu können.

#### 1.2 Vollständige Feature-Beschreibung (Original)

| Feature | Typ | Beschreibung | Besonderheiten |
| --- | --- | --- | --- |
| `instant` | ID | Record-Index | Nicht im modifizierten Dataset, kein Feature |
| `dteday` | Date | Datum (YYYY-MM-DD) | Zeitbezogen, muss encodiert werden |
| `season` | Categorical | 1: Winter, 2: Frühling, 3: Sommer, 4: Herbst | Ordinal interpretierbar, aber kategorial behandeln |
| `yr` | Categorical | 0: 2011, 1: 2012 | Trends über Jahre |
| `mnth` | Categorical | Monat (1–12) | Zyklisch, hat Missing Values im mod. Dataset |
| `hr` | Categorical | Stunde (0–23) | Nur in hour.csv, stark prädiktiv, zyklisch |
| `holiday` | Binary | Feiertag ja/nein | Quelle: DC HR Holiday Schedule |
| `weekday` | Categorical | Wochentag (0–6) | Nicht im modifizierten Dataset |
| `workingday` | Binary | Kein Wochenende/Feiertag = 1 | Nicht im modifizierten Dataset |
| `weathersit` | Categorical | 1: Klar, 2: Nebel, 3: Leichter Regen/Schnee, 4: Starker Regen | Hat Missing Values im mod. Dataset, Kategorie 4 selten |
| `temp` | Real | Normalisierte Temperatur: (t−t_min)/(t_max−t_min), t_min=−8, t_max=+39 | Stündliche Normalisierung |
| `atemp` | Real | Normalisierte Gefühlstemperatur: t_min=−16, t_max=+50 | Stark korreliert mit `temp` |
| `hum` | Real | Normalisierte Luftfeuchtigkeit (/100) | |
| `windspeed` | Real | Normalisierte Windgeschwindigkeit (/67) | |
| `casual` | Integer | Anzahl nicht registrierter Nutzer | Nicht im modifizierten Dataset |
| `registered` | Integer | Anzahl registrierter Nutzer | Nicht im modifizierten Dataset |
| `cnt` | Integer | **Zielvariable** — Gesamtausleihungen (casual + registered) | |

#### 1.3 Bekannte Dataset-Eigenschaften für Preprocessing

1. **Hohe Korrelation:** `temp` und `atemp` sind stark korreliert (~0.99) → Feature Selection relevant
2. **Zyklische Features:** `hr`, `mnth` haben zyklische Natur (23→0, 12→1) → Sin/Cos-Encoding sinnvoll
3. **Kategoriale Ordinalität:** `season` und `weathersit` sind ordinal, aber nicht äquidistant
4. **Zeitliche Trends:** `yr` zeigt Wachstumstrend (2012 > 2011), `hr` hat Pendelmuster (Peaks um 8 und 17 Uhr)
5. **Seltene Kategorien:** `weathersit=4` (schwerer Regen) ist extrem selten → Candidate für Rare Category Bucketing
6. **Nicht-Normalverteilung:** `cnt` ist rechtsschief (viele niedrige, wenige hohe Werte)
7. **Multikollinearität:** Mehrere Features korrelieren (temp/atemp, season/mnth)

#### 1.4 Typische ML-Ansätze auf dem Bike-Dataset

Aus der Literatur und Kaggle-Notebooks:

- **Regression** als Hauptaufgabe (Vorhersage von `cnt`)
- **Tree-basierte Modelle** (Random Forest, Gradient Boosting, XGBoost) sind typische Top-Performer
- **EBM** (Explainable Boosting Machine) liefert vergleichbare Genauigkeit bei voller Interpretierbarkeit
- **Feature Engineering:** Zeit-Features extrahieren, zyklisches Encoding, Interaktionen
- **Preprocessing:** Normalisierung, Encoding, Feature Selection reduzieren Rauschen
- **Overfitting-Risiko:** Durch zeitliche Autokorrelation (aufeinanderfolgende Stunden ähnlich)

---

### 2. Preprocessing — Best Practices für Tabellarische Daten

#### 2.1 Data Leakage — Die größte Gefahr

**Definition:** Informationen aus dem Testset fließen in das Trainieren/Preprocessing ein, was zu optimistischen Performance-Schätzungen führt.

**Typische Quellen bei Preprocessing:**

| Leakage-Quelle | Warum problematisch | Lösung |
| --- | --- | --- |
| Mean/Median-Imputation auf Gesamtdaten | Testdaten-Statistiken fließen in Imputation ein | Imputation nur auf Trainingsdaten fitten |
| Scaling/Normalisierung auf Gesamtdaten | Min/Max/Std des Testsets beeinflusst Transformation | Scaler auf Trainingsdaten fitten, auf Test transformieren |
| Feature Selection auf Gesamtdaten | Korrelationen mit Zielvariable im Testset beeinflusst Auswahl | Feature Selection nur auf Trainingsdaten |
| Outlier Detection auf Gesamtdaten | Testset-Verteilung beeinflusst Grenzwerte | Grenzwerte nur aus Trainingsdaten berechnen |

**Architektur-Konsequenz für Gysi:**
Das Splitting MUSS vor allen verteilungsabhängigen Steps erfolgen. Steps, die Statistiken berechnen (Mean, Std, Korrelation), müssen ein **fit/transform-Pattern** implementieren:
- `fit()` → nur auf Trainingsdaten: Statistiken berechnen und speichern
- `transform()` → auf beliebige Daten: gespeicherte Statistiken anwenden

#### 2.2 Reihenfolge der Preprocessing-Schritte

Empfohlene Best-Practice-Reihenfolge:

```text
1. Dateninspektion (EDA, Datentypen, Missing Value Statistik)
2. Duplikat-Erkennung und -Entfernung
3. Time Feature Encoding (Datum → numerische Features)
4. Data Splitting (Train/Test/Validation) ← KRITISCHER PUNKT
   --- Ab hier: fit auf Train, transform auf Train+Test ---
5. Missing Value Handling (Imputation)
6. Outlier Detection/Handling
7. Encoding (One-Hot, Gruppierung)
8. Feature Selection (Filter, Wrapper, Embedded)
9. Scaling (optional, nicht für Trees/EBM nötig)
```

**Anmerkung:** Steps 1–3 sind verteilungsunabhängig und können vor dem Split durchgeführt werden. Ab Step 5 müssen alle Steps dem fit/transform-Pattern folgen.

#### 2.3 Missing Value Strategien — Eignung für Bike-Dataset

| Strategie | Eignung für Bike-Dataset | Wann verwenden |
| --- | --- | --- |
| **Variable Dropping** | Nur wenn >50% Missing in einer Spalte | Rare edge case |
| **List-wise Deletion** | OK bei wenig Missing, verliert Zeilen | <5% Missing |
| **Mean Imputation** | Gut für `temp`, `hum`, `windspeed` | Numerische, normalverteilte Features |
| **Median Imputation** | Besser bei Schiefverteilung | `cnt`, `windspeed` |
| **Hot-Deck Imputation** | Gut für kategoriale Features | `weathersit`, `season` |
| **Linear Interpolation** | Ideal für zeitliche Daten | Sortiert nach `dteday`+`hr` |
| **LOCF** | OK für zeitliche Daten, bias-anfällig | Wenn Trends langsam ändern |
| **NOCB** | Analog LOCF, rückwärts | Ergänzung zu LOCF |
| **Mode Imputation** | Für kategoriale Features | `weathersit`, `mnth` |

**Für Trees/EBMs:** Diese Modelle können nativ mit Missing Values umgehen. Trotzdem ist Imputation für die Belegarbeit als Demonstration sinnvoll.

---

### 3. Konversationelle ML-Assistenten — Stand der Technik

#### 3.1 Abgrenzung zu AutoML

| Merkmal | AutoML (z.B. Auto-sklearn, FLAML) | Gysi (konversationell) |
| --- | --- | --- |
| Interaktion | Minimal, automatisiert | Natürliche Sprache, iterativ |
| Kontrolle | System entscheidet | Mensch entscheidet, LLM empfiehlt |
| Transparenz | Begrenzt (Blackbox-Suche) | Hoch (jeder Schritt erklärbar) |
| Flexibilität | Breit, aber vordefiniert | Fokussiert, aber frei steuerbar |
| Reproduzierbarkeit | Über Seeds | Über Spec-Versionierung |

#### 3.2 Gysis Nische

Gysi positioniert sich als **Human-in-the-Loop ML-Assistent** mit:

- **Erklärbarkeit** als Kernwert (EBMs, Feature Importance)
- **Kontrollierbarkeit** durch Spec-basierte Pipeline (kein Blackbox-Verhalten)
- **Explorativität** durch History/Undo (was wäre wenn?)
- **Pädagogischer Wert** im Kontext einer Belegarbeit

---

## Teil B: Technical Research

### 4. scikit-learn Pipeline-Patterns

#### 4.1 Relevante Konzepte

**`Pipeline`:** Verkettet Transformer und Estimators sequentiell. Jeder Schritt außer dem letzten muss ein Transformer sein (braucht `transform()`-Methode).

**`ColumnTransformer`:** Wendet verschiedene Transformationen auf verschiedene Spalten an. Ideal für heterogene Daten (numerisch + kategorial).

**`FeatureUnion`:** Kombiniert Outputs mehrerer Transformer nebeneinander.

**Fit/Transform-Pattern:**

```python
# Alle sklearn Transformer implementieren:
class MyTransformer(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        # Statistiken aus X (Trainingsdaten) lernen
        self.mean_ = X.mean()
        return self

    def transform(self, X):
        # Gelernte Statistiken auf X anwenden
        return X.fillna(self.mean_)
```

#### 4.2 Entscheidung: sklearn-Pipeline vs. Custom Pipeline

| Ansatz | Vorteile | Nachteile |
| --- | --- | --- |
| **sklearn Pipeline direkt** | Etabliert, fit/transform automatisch, GridSearch-kompatibel | Schwer zu serialisieren als JSON-Spec, Reports zwischen Steps schwierig |
| **Custom Pipeline mit sklearn-Komponenten** | Volle Kontrolle über Reporting, JSON-Spec-kompatibel, History-fähig | Mehr eigener Code, fit/transform manuell sicherstellen |
| **Hybrid** (empfohlen) | sklearn-Transformer *in* Custom-Pipeline-Steps | Best of both worlds |

**Empfehlung für Gysi:** Hybrid-Ansatz. Jeder Step im Gysi-Executor nutzt intern sklearn-Transformers, aber die Orchestrierung (Spec → Step-Reihenfolge → Reporting → Persistence) ist custom. So profitieren wir von sklearn's geprüfter Logik, behalten aber volle Kontrolle über die Pipeline-Steuerung.

#### 4.3 Fit/Transform für Gysis Step-Interface

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd

@dataclass
class StepResult:
    """Ergebnis eines Pipeline-Steps."""
    df: pd.DataFrame                # Transformierter DataFrame
    report: dict                    # Kennzahlen, Statistiken
    artifacts: list[str]            # Pfade zu generierten Plots/Dateien

class PipelineStep(ABC):
    """Basis-Interface für alle Pipeline-Steps."""

    @abstractmethod
    def fit(self, df: pd.DataFrame, config: dict) -> "PipelineStep":
        """Statistiken aus Trainingsdaten lernen."""
        ...

    @abstractmethod
    def transform(self, df: pd.DataFrame) -> StepResult:
        """Gelernte Statistiken auf Daten anwenden."""
        ...

    def fit_transform(self, df: pd.DataFrame, config: dict) -> StepResult:
        """Convenience: fit + transform in einem Aufruf."""
        return self.fit(df, config).transform(df)
```

**Warum fit/transform:** Verhindert Data Leakage. Der Executor ruft `fit_transform()` auf Trainingsdaten und `transform()` auf Test/Validation.

---

### 5. JSON-Schema-Design für Pipeline-Spec

#### 5.1 Entwurfsprinzipien

1. **Deklarativ:** Die Spec beschreibt *was*, nicht *wie*
2. **Validierbar:** JSON Schema prüft Struktur und Parameterbereiche
3. **Erweiterbar:** Neue Step-Typen ohne Schema-Bruch hinzufügbar
4. **Versionierbar:** Jede Spec hat eine ID und einen Timestamp

#### 5.2 Beispiel-Spec-Struktur

```json
{
  "$schema": "pipeline_spec_schema.json",
  "version": "1.0",
  "dataset": {
    "path": "data/raw/bikes.csv",
    "target": "cnt",
    "date_column": "dteday"
  },
  "splitting": {
    "method": "train_test",
    "test_ratio": 0.2,
    "stratify": null,
    "random_seed": 42
  },
  "steps": [
    {
      "id": "step_01",
      "type": "duplicate_removal",
      "enabled": true,
      "params": {
        "subset": null,
        "keep": "first"
      }
    },
    {
      "id": "step_02",
      "type": "time_feature_encoding",
      "enabled": true,
      "params": {
        "source_column": "dteday",
        "extract": ["day", "month", "year", "weekday"],
        "cyclic_encoding": true,
        "drop_original": true
      }
    },
    {
      "id": "step_03",
      "type": "missing_value_handling",
      "enabled": true,
      "params": {
        "strategy": "median",
        "columns": ["mnth", "weathersit", "temp", "hum"],
        "threshold_drop_column": 0.5
      }
    },
    {
      "id": "step_04",
      "type": "outlier_handling",
      "enabled": true,
      "params": {
        "method": "winsorization",
        "columns": ["cnt", "windspeed"],
        "lower_percentile": 0.01,
        "upper_percentile": 0.99
      }
    },
    {
      "id": "step_05",
      "type": "categorical_encoding",
      "enabled": true,
      "params": {
        "method": "onehot",
        "columns": ["season", "weathersit"],
        "drop_first": true,
        "rare_threshold": 0.01
      }
    },
    {
      "id": "step_06",
      "type": "feature_selection",
      "enabled": true,
      "params": {
        "method": "correlation_filter",
        "threshold": 0.95,
        "target_column": "cnt"
      }
    }
  ]
}
```

#### 5.3 JSON Schema Validierung

Die `jsonschema`-Bibliothek (Python) validiert Specs gegen ein Schema. Das Schema definiert:

- Erlaubte Step-Typen (enum)
- Required/Optional Felder pro Step-Typ
- Parameterbereiche (min/max für Ratios, erlaubte Strategien)
- Strukturelle Konsistenz (z.B. referenzierte Spalten müssen existieren → semantische Validierung im Backend)

---

### 6. CatBoost Feature Selection

#### 6.1 API-Übersicht

CatBoost bietet eine eingebaute `select_features()`-Methode:

```python
from catboost import CatBoostRegressor, Pool
from catboost import EShapCalcType, EFeaturesSelectionAlgorithm

model = CatBoostRegressor(iterations=1000, random_seed=42)
summary = model.select_features(
    train_pool,
    eval_set=test_pool,
    features_for_select='0-11',      # Alle Features
    num_features_to_select=6,         # Ziel-Anzahl
    steps=3,                          # Mehr Steps = genauer
    algorithm=EFeaturesSelectionAlgorithm.RecursiveByShapValues,
    shap_calc_type=EShapCalcType.Regular,
    train_final_model=True,
    logging_level='Silent'
)
# summary enthält: selected_features, eliminated_features (mit Names)
```

#### 6.2 Algorithmen

| Algorithmus | Geschwindigkeit | Genauigkeit | Beschreibung |
| --- | --- | --- | --- |
| `RecursiveByPredictionValuesChange` | Schnell | Niedrig | Nicht empfohlen für Ranking |
| `RecursiveByLossFunctionChange` | Mittel | Mittel | Optimale Balance |
| `RecursiveByShapValues` | Langsam | Hoch | Basiert auf SHAP-Werten |

#### 6.3 Integration in Gysi

- **Dependency:** `catboost` als einzige Ausnahme neben pandas/sklearn
- **Wrapping:** CatBoost Feature Selection als eigener Step-Typ (`catboost_feature_selection`)
- **Config:** `num_features_to_select`, `algorithm`, `steps` als Spec-Parameter
- **Fallback:** Wenn CatBoost nicht verfügbar, auf sklearn-Methoden zurückfallen
- **Gotcha:** CatBoost benötigt `Pool`-Objekt, nicht direkt DataFrame → Konversion im Step
- **Gotcha:** `select_features()` trainiert intern ein Modell → dauert länger als Filter-Methoden
- **Report:** Selected/Eliminated Features, Feature Importances, SHAP-summary

---

### 7. InterpretML — Explainable Boosting Machine (EBM)

#### 7.1 Was ist EBM?

EBM ist ein **Glassbox-Modell** von Microsoft Research. Es basiert auf **Generalized Additive Models (GAMs)** mit modernen ML-Techniken:

- **Bagging** für Stabilität
- **Gradient Boosting** für Genauigkeit
- **Automatische Interaktionsdetektion** für Feature-Paare

EBMs sind **so genau wie Random Forests und Gradient Boosted Trees**, aber vollständig interpretierbar.

#### 7.2 Python-API

```python
from interpret.glassbox import ExplainableBoostingRegressor
from interpret import show

# Training
ebm = ExplainableBoostingRegressor(random_state=42)
ebm.fit(X_train, y_train)

# Prediction
y_pred = ebm.predict(X_test)

# Globale Erklärung (Feature-Beiträge über gesamtes Dataset)
ebm_global = ebm.explain_global()
show(ebm_global)  # Interaktive Visualisierung

# Lokale Erklärung (einzelne Samples)
ebm_local = ebm.explain_local(X_test[:5], y_test[:5])
show(ebm_local)
```

#### 7.3 Output-Typen für Gysi

| Output | Beschreibung | Umsetzung in Gysi |
| --- | --- | --- |
| **Feature Importance** | Ranking aller Features nach Beitrag | JSON-Report + Matplotlib Bar-Plot |
| **Shape Functions** | Wie jedes Feature die Vorhersage beeinflusst (Kurve) | Matplotlib-Plot pro Feature |
| **Interaction Terms** | Detected Pairwise Interactions | JSON-Liste + Heatmap-Plot |
| **Local Explanation** | Beitrag jedes Features für einzelne Samples | JSON-Report + Waterfall-Plot |
| **Performance** | R², MSE, MAE auf Train/Test | JSON-Report |

#### 7.4 Relevante Erkenntnisse für Gysi

1. **EBM unterstützt pandas DataFrames nativ** — kein Konversionsbedarf
2. **EBM behandelt Missing Values intern** — Imputation optional, aber demonstrativ sinnvoll
3. **EBM unterstützt kategoriale Features als Strings** — kein One-Hot nötig (wird intern behandelt)
4. **Pairwise Interactions** by default — 3-way und höher optional
5. **`explain_global()`** liefert serialisierbare Daten — ideal für JSON-Reports
6. **Package:** `interpret` (pip install interpret), MIT-lizenziert, aktiv gepflegt (v0.7.7, März 2026)
7. **Performance:** Auf dem Bike-Dataset typischerweise R² ~0.93–0.95

---

### 8. Decision Trees (sklearn)

#### 8.1 Relevanz für Gysi

Decision Trees sind der zweite Modelltyp neben EBM. Sie sind:

- Vollständig interpretierbar (Baum visualisierbar)
- Robust gegen Feature-Skalierung (kein Scaling nötig)
- Anfällig für Overfitting (Hyperparameter-Tuning wichtig)

#### 8.2 Wichtige Hyperparameter

| Parameter | Beschreibung | Relevanz für Gysi |
| --- | --- | --- |
| `max_depth` | Maximale Baumtiefe | Komplexitätskontrolle |
| `min_samples_split` | Min. Samples für Split | Overfitting-Kontrolle |
| `min_samples_leaf` | Min. Samples pro Blatt | Glättung |
| `max_leaf_nodes` | Max. Anzahl Blätter | Direkte Größenkontrolle |
| `max_features` | Features pro Split | Regularisierung |

#### 8.3 Tree-Visualisierung

```python
from sklearn.tree import DecisionTreeRegressor, plot_tree, export_text
import matplotlib.pyplot as plt

tree = DecisionTreeRegressor(max_depth=4)
tree.fit(X_train, y_train)

# Visueller Plot
fig, ax = plt.subplots(figsize=(20, 10))
plot_tree(tree, feature_names=X_train.columns, filled=True, ax=ax)
# → Speichern als Artefakt

# Text-Repräsentation (für LLM-Kontext)
rules = export_text(tree, feature_names=list(X_train.columns))
```

**Für Gysi relevant:** Die Komplexitätsreduktion über System-Prompts (nur erster Layer o.ä.) ist im Systemkonzept erwähnt. `plot_tree` mit `max_depth`-Begrenzung und `export_text` für LLM-kompatible Darstellung.

---

### 9. Python Registry / Plugin Pattern

#### 9.1 Step Registry Design

Die Step Registry ist ein Whitelist-basiertes Mapping von Step-Typ-Strings auf Python-Klassen:

```python
from typing import Type

# Registry als Dictionary
_STEP_REGISTRY: dict[str, Type[PipelineStep]] = {}

def register_step(step_type: str):
    """Decorator zum Registrieren eines Steps."""
    def decorator(cls: Type[PipelineStep]):
        if step_type in _STEP_REGISTRY:
            raise ValueError(f"Step '{step_type}' already registered")
        _STEP_REGISTRY[step_type] = cls
        return cls
    return decorator

def get_step(step_type: str) -> PipelineStep:
    """Step-Instanz nach Typ-String abrufen."""
    if step_type not in _STEP_REGISTRY:
        raise KeyError(f"Unknown step type: '{step_type}'")
    return _STEP_REGISTRY[step_type]()

# Nutzung:
@register_step("missing_value_handling")
class MissingValueStep(PipelineStep):
    ...
```

#### 9.2 Design-Vorteile

- **Erweiterbar:** Neuer Step = neue Klasse + Decorator → automatisch verfügbar
- **Whitelist:** Nur registrierte Steps sind erlaubt (Sicherheit für LLM-Aktionen)
- **Testbar:** Registry-Inhalt ist inspizierbar
- **Entkoppelt:** Executor kennt keine Step-Details, nur das Interface

---

### 10. FastAPI + SQLite Patterns

#### 10.1 FastAPI für ML-Backends

```python
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: DB initialisieren, Dataset laden
    init_database()
    yield
    # Shutdown: Verbindungen schließen

app = FastAPI(title="Gysi ML Backend", lifespan=lifespan)
```

#### 10.2 SQLite für State Management

SQLite eignet sich für Gysi aus diesen Gründen:

- **Keine Server-Installation** nötig (stdlib `sqlite3`)
- **File-basiert** — passt zu lokalem Prototyp
- **Transaktional** — ACID für History/Undo
- **Performant** für moderate Datenmengen

**Tabellen-Entwurf (Skizze):**

```sql
CREATE TABLE spec_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_json TEXT NOT NULL,
    parent_id INTEGER REFERENCES spec_versions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    branch TEXT DEFAULT 'main'
);

CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_version_id INTEGER NOT NULL REFERENCES spec_versions(id),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT CHECK(status IN ('pending', 'running', 'completed', 'failed')),
    result_summary_json TEXT
);

CREATE TABLE artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    step_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    current_spec_version_id INTEGER REFERENCES spec_versions(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

### 11. Pydantic für Action Models

Pydantic v2 ist ideal für die Action-Validierung:

```python
from pydantic import BaseModel, Field
from typing import Literal

class ModifySpecAction(BaseModel):
    action_type: Literal["modify_spec"]
    step_id: str
    changes: dict

class ExecuteAction(BaseModel):
    action_type: Literal["execute"]
    steps: list[str] | None = None  # None = alle Steps

class UndoAction(BaseModel):
    action_type: Literal["undo"]
    steps_back: int = Field(ge=1, le=100)
```

---

## Teil C: Zusammenfassung und Auswirkungen aufs Brainstorming

### Bestätigungen

Die Domain/Technical Research bestätigt die Tragfähigkeit der im Brainstorming getroffenen Entscheidungen:

1. **JSON für Specs:** Gut validierbar mit `jsonschema`, strukturiert serialisierbar
2. **Deterministisch zuerst:** Ermöglicht sauberes Testing ohne LLM-Abhängigkeit
3. **CatBoost:** `select_features()` API ist sauber und liefert strukturierte Ergebnisse
4. **85% Coverage:** Realistisch durch modulares Step-Design mit klaren Interfaces
5. **Matplotlib:** Passend für Reports; EBM's `explain_global/local` liefert plottbare Daten

### Neue Erkenntnisse mit Impact auf Planung

| Erkenntnis | Impact | Empfehlung |
| --- | --- | --- |
| **Fit/Transform-Pattern ist kritisch** | Architekturentscheidung | Step-Interface MUSS fit/transform implementieren, nicht nur execute |
| **Data Leakage Reihenfolge** | Spec-Design | Splitting muss explizit als Trennpunkt in der Spec markiert sein |
| **EBM unterstützt kategoriale Features nativ** | Encoding-Step optional für EBM | Encoding trotzdem implementieren, aber für EBM überspringbar machen (`enabled` Flag) |
| **EBM behandelt Missing Values intern** | Imputation optional für EBM | Gleiches Prinzip: Steps müssen deaktivierbar sein |
| **Modifiziertes Dataset ohne weekday/workingday** | Feature Engineering eingeschränkt | Time Feature Encoding muss Wochentag aus `dteday` ableiten |
| **`temp`/`atemp` hochkorreliert** | Feature Selection Demo-Case | Perfektes Beispiel für Korrelationsfilter in der Belegarbeit |
| **`weathersit=4` extrem selten** | Rare Category Bucketing relevant | Gutes Demo-Beispiel für Bucketing |
| **Decorator-basierte Registry** | Sauberes Pattern | Step Registry mit `@register_step` Decorator implementieren |

### Offene Fragen (zur Klärung in der nächsten Planungsphase)

1. **Split-Position in der Spec:** Soll Splitting ein eigener Step sein oder ein separater Spec-Abschnitt? (Empfehlung: Separater Abschnitt, da er die Pipeline in "Pre-Split" und "Post-Split" teilt)
2. **Step-Aktivierung für verschiedene Modelle:** Sollen Steps per Modelltyp aktivierbar sein? (z.B. Encoding an für Trees, aus für EBM)
3. **Artefakt-Format:** Sollen Plots als PNG, SVG oder beides gespeichert werden?
4. **EDA-Notebook:** Soll die EDA als eigenständiger Step oder als separates Notebook laufen?
