# Notizen – 19.04.2026

## Bugs / Fehler

### Spec-Versionierung

- **One-Hot-Encoding auf float/int-Spalten**: Neue Spec-Version wird erzeugt, obwohl nichts am Datensatz verändert wurde (Encoding wurde intern übersprungen)
  - → Keine neue Version erzeugen, wenn ein Step nichts verändert hat

### Korrelations-Filter

- Gibt eine CSV aus statt die korrelierten Feature-Paare im Chat anzuzeigen
- Keine Möglichkeit, interaktiv auszuwählen, welches Feature entfernt werden soll
- Korrelationsergebnisse erscheinen nur in der Seitenleiste, nicht im Chat
- **Wenn Correlation Filter angewendet wird, werden vorherige Preprocessing-Schritte gelöscht** (z.B. Impute Missing + Time Feature Encoding)

### Rollback

- Rollback zu v4 führt tatsächlich zu v1 → falsche Versionsreferenz

### CatBoost Feature Selection

- Fehlermeldung: `Step 'catboost_feature_selection' benötigt einen vorherigen 'split'-Step, aber kein Split-Step wurde vor diesem Step gefunden` — obwohl Split vorhanden war

### Modelltraining mit NaN in Zielspalte

- `cnt` enthält fehlende Werte → CatBoost und Decision Tree brechen mit kryptischer Fehlermeldung ab
  - CatBoost: `metric/loss-function RMSE does not allow nan values in target data`
  - Decision Tree: `Input y contains NaN`
  - → Fehler sollte besser erklärt werden: Hinweis geben, dass `cnt` Missing Values enthält und zuerst imputiert werden muss

### Artefakt-Ausgabe nach Modelltraining

- Wenn mehrere Modelle trainiert wurden (z.B. Decision Tree + EBM), werden im Ergebnis **alle** Artefakte aus allen Runs angezeigt (Train/Test-CSVs, Decision Tree Feature Importance, EBM Global Explanation)
  - → Nur Artefakte des aktuellen Runs ausgeben

### Feature Importance Plot

- Anfrage „gib mir die Feature Importance als Plot" hat stattdessen eine EBM trainiert
  - → LLM-Interpretation korrigieren

---

## Feature-Wünsche / Todos

### Preprocessing

| Priorität | Feature | Details |
| --- | --- | --- |
| Hoch | **Datentyp-Konvertierung** | Spalten wie `season`, `weathersit` von int/float auf kategorisch umwandeln, damit One-Hot-Encoding greift |
| Hoch | **Feature löschen** | Funktion zum manuellen Entfernen von Spalten (z.B. `month` nach Neuberechnung) |
| Mittel | **Imputation aus anderem Feature** | Missing Values in `mnth` aus `dteday` ableiten |
| Mittel | **Rollback auf Basis CSV** | Pipeline auf einen früheren Datenzustand zurücksetzen |
| Niedrig | **Sample-Selektion** | Zeilen filtern nach Bedingung (z.B. alle Zeilen wo es geregnet hat) |

### Feature Selection

- **Manuelle Feature-Auswahl** hinzufügen
- **Wrapper / Embedded Feature Selection** (z.B. via CatBoost)
- Korrelations-Filter: Ergebnisse im Chat anzeigen + interaktive Auswahl welches Feature fliegt

### Kontext für LLM

- Separate Ablage einer Markdown-Datei mit Domänenwissen (z.B. `season = 2 → Frühling`, Bedeutung der Wochentagnummern 0–6)
- `time_feature_encoding (dteday)`: Dokumentieren welche Zahl welchem Wochentag entspricht

### EDA / Visualisierung

- Plots vor dem Preprocessing einbauen (z.B. Boxplot je Feature) für besseres Datenverständnis
- Generell mehr Möglichkeiten zur explorativen Datenanalyse **vor** dem Modelltraining

---

## Beobachtungen / Fachliches

### One-Hot-Encoding

- Geeignete Kandidaten im Bike-Datensatz: `season`, `weathersit`, `holiday`
- Nicht geeignet (ordinale / viele Kategorien): `mnth`, `hr`
- `workingday` und `weekday` **existieren nicht** als Features im Datensatz
- Encoding schlägt fehl wenn Spalte als `float64`/`int64` vorliegt → erst in `category`-Typ umwandeln

### Train-Test-Split

- 80/20-Split mit `random_state=42` → 13.903 Train / 3.476 Test
- Preprocessing (Imputation, Skalierung) **nach** dem Split anwenden (Fit nur auf Trainingsdaten) — korrekt implementiert
