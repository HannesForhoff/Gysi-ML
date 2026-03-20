# Abgleich: Konsultationsnotizen vs. Implementierung

Stand: 2026-03-20

Dieses Dokument vergleicht die Anforderungen aus der ersten Konsultation
und den Preprocessing-Anforderungen mit dem aktuellen Implementierungsstand.

## Preprocessing

| Anforderung | Status | Implementierung | Anmerkungen |
| --- | --- | --- | --- |
| Duplikate erkennen und entfernen | ✅ fertig | `dedup`-Step | — |
| Missing Values beheben | ✅ fertig | `impute_missing` (median, mean, most_frequent) | Konsultation nannte auch: Variable Dropping, List-wise Deletion, Hot-Deck, Interpolation, LOCF — nicht umgesetzt |
| Ausreißerentfernung / Grenzen | ✅ fertig | `outlier_handling` (IQR, Z-Score / Winsorization) | Boxplot-Visualisierung zur Outlier-Erkennung fehlt |
| One-Hot-Encoding vs. gruppierte Features | ✅ fertig | `encode_categorical` (label, onehot) | — |
| Time Feature Encoding | ✅ fertig | `time_feature_encoding` (Datum → Wochentag + Monat) | Konsultation: dd/mm/yyyy → day/month/year einzeln. Aktuell: Wochentag + Monat (kein Jahr) |
| Data Splitting / Train-Test Ratios | ✅ fertig | `split` (test_size, random_state) | Validation-Split nicht umgesetzt (nur Train/Test) |
| Rare-Category-Bucketing | ✅ fertig | `rare_category_bucketing` (min_frequency) | War in Konsultation als optional markiert |
| Filter-Methods (Korrelation) | ✅ fertig | `correlation_filter` (Pearson-Threshold) | — |
| CatBoost Feature Selection | ✅ fertig | `catboost_feature_selection` (top_n) | Einzige Ausnahme außerhalb pandas/sklearn |
| User kann Features manuell auswählen | ❌ fehlt | — | Kein Step für manuelle Feature-Selektion |
| Interne Selektion als nächste Iteration | ❌ fehlt | — | Automatisches Feature-Subset nach Modelltraining |
| Wrapper/Embedded Feature Selection | ❌ fehlt | — | Konsultation: Filters, Wrappers, Embedded Methods |
| Samples selektieren | ❌ fehlt | — | Z.B. „Selektiere alle Samples wo es geregnet hat" |
| Class Imbalance | ❌ fehlt | — | War in Konsultation als optional markiert |
| Künstlich Missing Values erzeugen | ❌ fehlt | — | Konsultation: „Falls zu wenig Values = selbst welche künstlich erzeugen" |

## Modeling

| Anforderung | Status | Implementierung | Anmerkungen |
| --- | --- | --- | --- |
| Decision Tree (sklearn) | ✅ fertig | `train_decision_tree` | — |
| EBM (InterpretML) | ✅ fertig | `train_ebm` | — |
| Default Hyperparameter | ✅ fertig | Beide Modelle mit sinnvollen Defaults | — |
| User-Centric Hyperparameter | ⚠️ teilweise | Decision Tree: nur `max_depth` exponiert | Konsultation nannte: Interactions, Smoothing, Max Rounds, Early Stopping, Max Leafs |
| Hyperparameter-Optimierung (HPO) | ❌ fehlt | — | Konsultation: „erstmal ausklammern, aber umsetzbar" |
| LLM liest Doku und empfiehlt HP | ❌ fehlt | — | Konsultation: „most promising HP aufgrund der Doku" |
| Limitationsdoku: LLM-Kontextwissen | ❌ offen | — | Konsultation: „LLM hat zu wenig Kontextwissen um auf bestimmte HP zu kommen" |

## Model Explanation / Ergebnisse

| Anforderung | Status | Implementierung | Anmerkungen |
| --- | --- | --- | --- |
| Predictive Performance (Metriken) | ✅ fertig | RMSE, MAE, R² | — |
| Train/Test-Zugriff (Overfitting) | ✅ fertig | Split-Metadata (train_rows, test_rows) | Keine separaten Train- vs. Test-Metriken |
| Feature Importance als Plot | ✅ fertig | Decision Tree → Balkendiagramm (PNG) | — |
| Feature Importance als Liste | ⚠️ teilweise | Im Metadata als `feature_names` | Keine sortierte Importance-Liste als Text |
| Globale Erklärung | ✅ fertig | EBM → globaler Erklärungsplot (PNG) | — |
| Lokale Erklärung (einzelne Samples) | ❌ fehlt | — | Konsultation: „Baum + EBM, einzelne Samples des Datasets" |
| Modellvergleich | ✅ fertig | Metriken zweier Runs nebeneinander | Bestes R² wird gekennzeichnet |
| Baum-Tree-Maps | ❌ fehlt | — | Konsultation: „Komplexitätsreduktion über System-Prompts, nur ersten Layer" |

## Systemkonzept / Interaktion

| Anforderung | Status | Implementierung | Anmerkungen |
| --- | --- | --- | --- |
| Datensatz begrenzen auf Bike Data | ✅ fertig | Fest konfiguriert in `config.py` | — |
| Chat-basierte Interaktion | ✅ fertig | Frontend Chat + Backend Messages-API | — |
| LLM erzeugt nur strukturierte JSON-Aktionen | ✅ fertig | Proposal → Confirm-Flow | — |
| History Feature (Undo / Schritte zurück) | ✅ fertig | Versionierte Pipeline-Spec, Re-Execution | — |
| Pipeline-Spec als Quelle der Wahrheit | ✅ fertig | Versioniert in SQLite | — |
| Hybride Persistenz (SQLite + Dateisystem) | ✅ fertig | DB für State, FS für Artefakte | — |
| Backend validiert alle LLM-Aktionen | ✅ fertig | JSON-Schema-Validierung + Retry | — |
| Capabilities-Endpunkt (Step-Registry) | ✅ fertig | `GET /v1/capabilities` | — |
| Speech-to-Text / Text-to-Speech | ❌ fehlt | — | Konsultation: „optional, nur prototypisch oder Randnotiz" |

## Frontend-spezifische Notizen

| Anforderung | Status | Anmerkungen |
| --- | --- | --- |
| Chat innerhalb des Chatfensters scrollbar | ❌ offen | Aktuell scrollt die ganze Seite |
| Daten-Preview neben dem Chat | ❌ offen | Machbar als Erweiterung (~2 Stories), siehe technische Einschätzung |
| Interface anpassen (Überschrift etc.) | ❌ offen | UI-Polish |

## Zusammenfassung

| Bereich | Abdeckung | Bemerkung |
| --- | --- | --- |
| Preprocessing | 10/15 | Kernfunktionen komplett, manuelle Selektion + Sampling fehlen |
| Modeling | 3/6 | Modelle da, HP-Steuerung + HPO begrenzt |
| Explanation | 5/7 | Gute Basis, Local Explanation + Tree-Maps fehlen |
| System/Interaktion | 7/8 | Nur Speech-to-Text fehlt (bewusst ausgeklammert) |
| Frontend-Notizen | 0/3 | UI-Polish und Erweiterungen offen |
| **Gesamt** | **25/39** | ~64 % der besprochenen Anforderungen umgesetzt |
