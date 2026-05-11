"""Einmaliges Hilfsskript: Schreibt help_texts.yaml mit neuer, übersichtlicher Struktur."""
import pathlib

CONTENT = """\
welcome_message: |
  Willkommen bei Gysi \u2014 deinem ML-Assistenten f\u00fcr den Bike-Datensatz! \U0001f6b2

  **Was ich kann:**
  - Preprocessing-Schritte konfigurieren (Dedup, Imputation, Encoding, ...)
  - Modelle trainieren (Decision Tree, EBM, CatBoost)
  - Ergebnisse erkl\u00e4ren und Runs vergleichen

  **Beispiele:**
  - \u201eEntferne Duplikate und impute fehlende Werte mit Median\u201c
  - \u201eTrainiere einen Decision Tree mit max_depth=5\u201c
  - \u201eVergleiche Run A mit Run B\u201c

  **Hilfe:** `/help` \u2192 Alle Funktionen  |  `/overview` \u2192 Datensatz-\u00dcberblick  |  `/status` \u2192 Session-Status

help:
  full_text: |
    ## Gysi \u2013 Hilfe\u00fcbersicht

    Beschreibe auf Deutsch, was du tun m\u00f6chtest. Gysi \u00fcbersetzt deine Anfrage in Pipeline-Schritte und f\u00fchrt sie aus.
    Du brauchst keine ML-Kenntnisse \u2014 einfach nat\u00fcrliche Sprache verwenden.

    Themen-Hilfe: `/help preprocessing` | `/help modellierung` | `/help visualisierung` | `/help daten`

    ---

    ### \U0001f50d Datensatz erkunden

    - **`/overview`** \u2014 Statistische \u00dcbersicht: Spalten, Datentypen, fehlende Werte, Werteverteilung
    - **`/status`** \u2014 Aktueller Stand der Pipeline und Ergebnisse des letzten Runs

    ---

    ### \U0001f9f9 Preprocessing

    **`dedup`** \u2014 Duplikate entfernen
      *(keine Parameter)*

    **`impute_missing`** \u2014 Fehlende Werte auff\u00fcllen
      - `strategy` *(Standard: `median`)* \u2014 `median` | `mean` | `most_frequent`
      - `columns` \u2014 Spaltenliste *(leer = alle numerischen Spalten)*

    **`outlier_handling`** \u2014 Ausrei\u00dfer behandeln (Winsorisierung)
      - `method` *(Standard: `iqr`)* \u2014 `iqr` | `zscore`
      - `zscore_threshold` *(Standard: `3.0`)* \u2014 Schwellwert bei Z-Score-Methode
      - `columns` \u2014 Numerische Spalten *(leer = alle)*

    **`encode_categorical`** \u2014 Kategorien in Zahlen umwandeln
      - `method` *(Standard: `label`)* \u2014 `label` | `onehot`
      - `columns` \u2014 Zu encodierende Spalten *(leer = automatische Erkennung)*

    **`correlation_filter`** \u2014 Stark korrelierte Spalten ermitteln / entfernen
      - `threshold` *(Standard: `0.9`)* \u2014 Korrelationsschwelle
      - `analysis_only` *(Standard: `true`)* \u2014 Nur analysieren, noch nichts entfernen
      - `features_to_drop` \u2014 Explizite Liste der zu entfernenden Spalten

    **`rare_category_bucketing`** \u2014 Seltene Kategorien in \u201eSonstige\u201c b\u00fcndeln
      - `min_frequency` *(Standard: `0.01`)* \u2014 Minimale relative H\u00e4ufigkeit (1 %)
      - `columns` \u2014 Kategorische Spalten *(leer = automatisch)*

    **`time_feature_encoding`** \u2014 Datumsspalte in Zeitfeatures umwandeln
      - `column` *(Standard: `dteday`)* \u2014 Datumsspalte
      - `features` *(Standard: `weekday, month`)* \u2014 `weekday` | `month` | `day_of_month` | `year` | `quarter`
      - `drop_original` *(Standard: `false`)* \u2014 Originalspalte nach Extraktion entfernen?

    **`cast_dtype`** \u2014 Datentyp einer Spalte \u00e4ndern
      - `columns` \u2014 Mapping `{"spalte": "typ"}` \u2014 Typen: `int64` | `float64` | `str` | `category` | `bool` | `datetime64`
      - `datetime_format` \u2014 strptime-Format bei `datetime64` (z. B. `"%Y-%m-%d"`)

    **`split`** \u2014 Train/Test-Split *(Pflicht vor dem Modelltraining!)*
      - `test_size` *(Standard: `0.2`)* \u2014 Anteil Testdaten (0.0\u20131.0)
      - `random_state` *(Standard: `42`)* \u2014 Zufalls-Seed

    ---

    ### \U0001f916 Modelltraining & Analyse

    **`train_decision_tree`** \u2014 Decision Tree trainieren
      - `max_depth` *(Standard: ohne Limit)* \u2014 Maximale Baumtiefe, z. B. `4`
      - `random_state` *(Standard: `42`)*

    **`train_ebm`** \u2014 Explainable Boosting Machine trainieren
      - `random_state` *(Standard: `42`)*

    **`catboost_feature_selection`** \u2014 Feature-Wichtigkeit analysieren
      - `top_n` *(Standard: `8`)* \u2014 Anzahl der wichtigsten Features
      - `analysis_only` *(Standard: `true`)* \u2014 Nur zeigen, noch nichts entfernen
      - `features_to_drop` \u2014 Features nach Best\u00e4tigung entfernen

    ---

    ### \U0001f4ca Visualisierung

    **`plot_distribution`** \u2014 Verteilung einer Spalte visualisieren
      - `feature` *(Pflicht)* \u2014 Spaltenname, z. B. `cnt` oder `temp`
      - `group_by` \u2014 Optionale Gruppierspalte, z. B. `season` oder `weathersit`

    ---

    ### \U0001f4a1 Beispielanfragen

    > \u201eEntferne Duplikate aus dem Datensatz\u201c
    > \u201eImpute fehlende Werte in windspeed mit dem Median\u201c
    > \u201eTeile die Daten 80/20 auf\u201c
    > \u201eTrainiere einen Decision Tree mit max_depth=4\u201c
    > \u201eZeige die Verteilung von cnt gruppiert nach season\u201c
    > \u201eWelche Spalten haben den gr\u00f6\u00dften Einfluss auf cnt?\u201c

    ---

    **Grenzen:** Nur Bike-Sharing-Datensatz. Kein Code-Upload, keine externen Daten.

  categories:
    preprocessing: |
      **Preprocessing-Schritte** (Parameter: Name=Standard-Wert):

      - **dedup** \u2014 Duplikate entfernen *(keine Parameter)*
      - **impute_missing** \u2014 strategy=median|mean|most_frequent, columns=[]
      - **outlier_handling** \u2014 method=iqr|zscore, zscore_threshold=3.0, columns=[]
      - **encode_categorical** \u2014 method=label|onehot, columns=[]
      - **correlation_filter** \u2014 threshold=0.9, analysis_only=true, features_to_drop=[]
      - **rare_category_bucketing** \u2014 min_frequency=0.01, columns=[]
      - **time_feature_encoding** \u2014 column=dteday, features=[weekday,month], drop_original=false
      - **cast_dtype** \u2014 columns={"spalte":"typ"} (int64|float64|str|category|bool|datetime64)
      - **split** \u2014 test_size=0.2, random_state=42

    modellierung: |
      **Modelltraining & Analyse** (Train-Test-Split muss vorher erfolgt sein!):

      - **train_decision_tree** \u2014 max_depth=null (kein Limit), random_state=42
      - **train_ebm** \u2014 random_state=42
      - **catboost_feature_selection** \u2014 top_n=8, analysis_only=true, features_to_drop=[]

    visualisierung: |
      **Visualisierung:**

      - **plot_distribution** \u2014 feature=<spaltenname> (Pflicht!), group_by=null

    daten: |
      **Datensatz erkunden:**

      - **/overview** \u2014 Statistiken, Spaltennamen, Datentypen, fehlende Werte
      - **/status** \u2014 Aktuelle Pipeline-Spec und Ergebnisse des letzten Runs

    grenzen: "Gysi arbeitet nur mit dem Bike-Sharing-Datensatz. Kein Code-Upload, keine externen Daten, kein Deployment."
"""

target = pathlib.Path(__file__).parents[1] / "configs" / "help_texts.yaml"
target.write_text(CONTENT, encoding="utf-8")
print(f"Geschrieben: {target}")
