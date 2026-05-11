"""Schreibt help_texts.yaml mit vollständiger Step-Einzel-Hilfe."""
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

  **Hilfe:** `/help` \u2192 \u00dcbersicht  |  `/overview` \u2192 Datensatz  |  `/status` \u2192 Session

help:
  full_text: |
    ## Gysi \u2013 Hilfe\u00fcbersicht

    Beschreibe auf Deutsch, was du tun m\u00f6chtest. Gysi \u00fcbersetzt deine Anfrage in Pipeline-Schritte.
    Du brauchst keine ML-Kenntnisse \u2014 einfach nat\u00fcrliche Sprache verwenden.

    **Einzel-Hilfe:** `/help <schritt>` \u2014 z.\u00a0B. `/help dedup`, `/help impute_missing`, `/help train_decision_tree`
    **Themen-Hilfe:** `/help preprocessing` | `/help modellierung` | `/help visualisierung` | `/help daten`

    ---

    ### \U0001f50d Datensatz erkunden

    - **`/overview`** \u2014 Statistische \u00dcbersicht: Spalten, Datentypen, fehlende Werte, Werteverteilung
    - **`/status`** \u2014 Aktueller Stand der Pipeline und Ergebnisse des letzten Runs

    ---

    ### \U0001f9f9 Preprocessing

    | Schritt | Kurzbeschreibung | Parameter | Werte / Standard |
    |---|---|---|---|
    | `dedup` | Duplikate entfernen | \u2014 | \u2014 |
    | `impute_missing` | Fehlende Werte auff\u00fcllen | `strategy` | `median`\u00b9 \| `mean` \| `most_frequent` |
    | | | `columns` | Spaltenliste *(leer = alle numerischen)* |
    | `outlier_handling` | Ausrei\u00dfer winsorisieren | `method` | `iqr`\u00b9 \| `zscore` |
    | | | `zscore_threshold` | Zahl *(Standard: `3.0`)* |
    | | | `columns` | Spaltenliste *(leer = alle numerischen)* |
    | `encode_categorical` | Kategorien \u2192 Zahlen | `method` | `label`\u00b9 \| `onehot` |
    | | | `columns` | Spaltenliste *(leer = automatisch)* |
    | `correlation_filter` | Korrelierte Spalten finden/entfernen | `threshold` | Zahl *(Standard: `0.9`)* |
    | | | `analysis_only` | `true`\u00b9 \| `false` |
    | | | `features_to_drop` | Spaltenliste |
    | `rare_category_bucketing` | Seltene Kategorien b\u00fcndeln | `min_frequency` | Zahl *(Standard: `0.01`)* |
    | | | `columns` | Spaltenliste *(leer = alle kategorischen)* |
    | `time_feature_encoding` | Zeitfeatures aus Datum extrahieren | `column` | Spaltenname *(Standard: `dteday`)* |
    | | | `features` | `weekday`\u00b9 \| `month`\u00b9 \| `day_of_month` \| `year` \| `quarter` |
    | | | `drop_original` | `false`\u00b9 \| `true` |
    | `cast_dtype` | Datentyp \u00e4ndern | `columns` | `{"spalte": "typ"}` \u2014 `int64` \| `float64` \| `str` \| `category` \| `bool` \| `datetime64` |
    | | | `datetime_format` | z.\u00a0B. `"%Y-%m-%d"` *(optional)* |
    | `split` | Train/Test-Split | `test_size` | Zahl *(Standard: `0.2`)* |
    | | | `random_state` | Ganzzahl *(Standard: `42`)* |

    *\u00b9 = Standard-Wert*

    ---

    ### \U0001f916 Modelltraining & Analyse

    | Schritt | Kurzbeschreibung | Parameter | Werte / Standard |
    |---|---|---|---|
    | `train_decision_tree` | Decision Tree trainieren | `max_depth` | Ganzzahl *(Standard: kein Limit)* |
    | | | `random_state` | Ganzzahl *(Standard: `42`)* |
    | `train_ebm` | Explainable Boosting Machine | `random_state` | Ganzzahl *(Standard: `42`)* |
    | `catboost_feature_selection` | Feature-Wichtigkeit analysieren | `top_n` | Ganzzahl *(Standard: `8`)* |
    | | | `analysis_only` | `true`\u00b9 \| `false` |
    | | | `features_to_drop` | Spaltenliste |

    *\u00b9 = Standard-Wert*

    ---

    ### \U0001f4ca Visualisierung

    | Schritt | Kurzbeschreibung | Parameter | Werte / Standard |
    |---|---|---|---|
    | `plot_distribution` | Verteilung einer Spalte plotten | `feature` | Spaltenname *(Pflicht!)* |
    | | | `group_by` | Spaltenname *(Standard: kein)* |

    ---

    **Grenzen:** Nur Bike-Sharing-Datensatz. Kein Code-Upload, keine externen Daten.

  categories:
    preprocessing: |
      **Preprocessing-Schritte** \u2014 Details: `/help <schritt>`

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
      **Modelltraining & Analyse** \u2014 Details: `/help <schritt>`

      Train-Test-Split muss vor dem ersten Training ausgef\u00fchrt worden sein!

      - **train_decision_tree** \u2014 max_depth=null (kein Limit), random_state=42
      - **train_ebm** \u2014 random_state=42
      - **catboost_feature_selection** \u2014 top_n=8, analysis_only=true, features_to_drop=[]

    visualisierung: |
      **Visualisierung** \u2014 Details: `/help plot_distribution`

      - **plot_distribution** \u2014 feature=<spaltenname> (Pflicht!), group_by=null

    daten: |
      **Datensatz erkunden:**

      - **/overview** \u2014 Statistiken, Spaltennamen, Datentypen, fehlende Werte
      - **/status** \u2014 Aktuelle Pipeline-Spec und Ergebnisse des letzten Runs

    grenzen: "Gysi arbeitet nur mit dem Bike-Sharing-Datensatz. Kein Code-Upload, keine externen Daten, kein Deployment."

  steps:
    dedup: |
      ### \U0001f9f9 `dedup` \u2014 Duplikate entfernen

      Entfernt Zeilen, die in **allen** Spalten identisch sind. Im Bike-Datensatz k\u00f6nnen solche Duplikate durch fehlerhafte Doppelerfassung entstehen und w\u00fcrden Statistiken und Modellevaluierung verzerren.

      **Parameter:** keine

      **Empfehlung:** Immer als **erster Schritt** ausf\u00fchren, bevor Imputation oder Encoding laufen \u2014 so wird sichergestellt, dass alle nachfolgenden Berechnungen auf sauberen Daten basieren.

      **Beispiel:**
      > \u201eEntferne doppelte Zeilen aus dem Datensatz\u201c

    impute_missing: |
      ### \U0001f9f9 `impute_missing` \u2014 Fehlende Werte auff\u00fcllen

      F\u00fcllt `NaN`-Werte in numerischen Spalten mit einer statistischen Kennzahl auf. Im Bike-Datensatz hat `windspeed` h\u00e4ufig fehlende Werte.

      **Parameter:**
      - `strategy` *(Standard: `median`)* \u2014 `median` | `mean` | `most_frequent`
        - `median`: robust gegen Ausrei\u00dfer, empfohlen f\u00fcr schiefe Verteilungen
        - `mean`: sensitiv gegen Ausrei\u00dfer, nur bei symmetrischer Verteilung sinnvoll
        - `most_frequent`: geeignet f\u00fcr kategorische Spalten
      - `columns` *(Standard: leer = alle numerischen Spalten)* \u2014 Spaltenliste, z.\u00a0B. `["windspeed", "hum"]`

      **\u26a0\ufe0f Achtung \u2014 Data Leakage:** Dieser Schritt **lernt** den Median/Mean aus den Trainingsdaten.
      Er muss **nach** dem Train-Test-Split ausgef\u00fchrt werden. Gysi warnt automatisch, wenn die Reihenfolge nicht stimmt.

      **Beispiel:**
      > \u201eImpute fehlende Werte in windspeed mit dem Median\u201c
      > \u201eF\u00fclle alle fehlenden Werte mit dem Mittelwert auf\u201c

    outlier_handling: |
      ### \U0001f9f9 `outlier_handling` \u2014 Ausrei\u00dfer behandeln

      Erkennt extreme Werte und begrenzt sie per **Winsorisierung** (Capping): Die Werte werden nicht entfernt, sondern auf einen Grenzwert gesetzt. Das h\u00e4lt die Datenmenge konstant.

      **Parameter:**
      - `method` *(Standard: `iqr`)* \u2014 `iqr` | `zscore`
        - `iqr` (Interquartilsabstand): robust, emp\u00e4hlt sich bei schiefen Daten \u2014 Capping auf [Q1\u22121.5\u00d7IQR, Q3+1.5\u00d7IQR]
        - `zscore` (Standardabweichung): geeignet bei normalverteilten Daten \u2014 Capping auf [\u00b5\u2212k\u00d7\u03c3, \u00b5+k\u00d7\u03c3]
      - `zscore_threshold` *(Standard: `3.0`)* \u2014 Schwellwert k bei Z-Score-Methode
      - `columns` *(Standard: leer = alle numerischen Spalten)* \u2014 Spaltenliste

      **\u26a0\ufe0f Achtung \u2014 Data Leakage:** Grenzen werden aus den Trainingsdaten gelernt \u2014 muss **nach** dem Split ausgef\u00fchrt werden.

      **Beispiel:**
      > \u201eBehandle Ausrei\u00dfer in temp und windspeed mit der IQR-Methode\u201c
      > \u201eWindsorisiere alle numerischen Spalten\u201c

    encode_categorical: |
      ### \U0001f9f9 `encode_categorical` \u2014 Kategorien in Zahlen umwandeln

      Wandelt Textspalten (dtype `object` oder `category`) in numerische Werte um, damit ML-Modelle damit arbeiten k\u00f6nnen.

      **Parameter:**
      - `method` *(Standard: `label`)* \u2014 `label` | `onehot`
        - `label`: Jede Kategorie erh\u00e4lt eine ganze Zahl (0, 1, 2, ...). Einfach und speichereffizient. Kann bei linearen Modellen ordinale Beziehungen implizieren, die nicht existieren \u2014 f\u00fcr Entscheidungsb\u00e4ume aber unproblematisch.
        - `onehot`: Erstellt f\u00fcr jede Kategorie eine eigene Bin\u00e4rspalte (0/1). Keine ordinale Annahme, aber mehr Spalten.
      - `columns` *(Standard: leer = automatische Erkennung per dtype)* \u2014 Spaltenliste

      **\u26a0\ufe0f Achtung \u2014 Data Leakage:** Das Mapping wird aus den Trainingsdaten gelernt \u2014 muss **nach** dem Split ausgef\u00fchrt werden.

      **Tipp:** Wenn `season` oder `weathersit` noch als `int64` vorliegen, vorher mit `cast_dtype` auf `category` setzen.

      **Beispiel:**
      > \u201eEncode alle kategorischen Spalten mit Label-Encoding\u201c
      > \u201eWandle season und weathersit per One-Hot-Encoding um\u201c

    correlation_filter: |
      ### \U0001f9f9 `correlation_filter` \u2014 Korrelierte Spalten finden und entfernen

      Berechnet paarweise **Pearson-Korrelationen** zwischen numerischen Spalten. Paare \u00fcber dem Schwellwert werden als redundant gemeldet. Hohe Korrelation zwischen Features kann die Modellinterpretierbarkeit verschlechtern.

      **Parameter:**
      - `threshold` *(Standard: `0.9`)* \u2014 Korrelationsschwelle (0.0\u20131.0). Paare dar\u00fcber gelten als redundant.
      - `analysis_only` *(Standard: `true`)* \u2014 Nur analysieren, kein Feature wird entfernt. Sinnvoll f\u00fcr den ersten Aufruf.
      - `features_to_drop` *(Standard: leer)* \u2014 Nach Pr\u00fcfung explizit festgelegte Features, die entfernt werden sollen.

      **Typischer Ablauf (zweistufig):**
      1. `analysis_only=true` \u2014 Gysi zeigt, welche Paare hoch korreliert sind
      2. Du entscheidest, welche Spalte aus jedem Paar f\u00e4llt
      3. Gysi f\u00fchrt den Schritt mit `features_to_drop` erneut aus

      **Beispiel:**
      > \u201eAnalysiere korrelierte Spalten mit Schwellwert 0.9\u201c
      > \u201eEntferne atemp, da es stark mit temp korreliert\u201c

    rare_category_bucketing: |
      ### \U0001f9f9 `rare_category_bucketing` \u2014 Seltene Kategorien b\u00fcndeln

      Fasst Kategorien, die seltener als `min_frequency` Prozent aller Datenpunkte vorkommen, zu einer Sammelgruppe `"_other_"` zusammen. Verhindert, dass Modelle auf Rarit\u00e4ten \u00fcberfitten, und reduziert nach One-Hot-Encoding die Anzahl der Spalten.

      **Parameter:**
      - `min_frequency` *(Standard: `0.01` = 1\u00a0%)* \u2014 Minimale relative H\u00e4ufigkeit. Kategorien darunter werden geb\u00fcndelt.
      - `columns` *(Standard: leer = alle kategorischen Spalten)* \u2014 Spaltenliste

      **Tipp:** Sinnvoll vor `encode_categorical` mit `onehot`, damit keine Spalten f\u00fcr winzige Gruppen entstehen.

      **Beispiel:**
      > \u201eFasse seltene Kategorien in weathersit zusammen\u201c
      > \u201eBuckete alle kategorischen Spalten mit min_frequency=0.05\u201c

    time_feature_encoding: |
      ### \U0001f9f9 `time_feature_encoding` \u2014 Zeitfeatures aus Datum extrahieren

      Extrahiert strukturierte numerische/kategorische Features aus einer Datumsspalte. Die neue Spalten erm\u00f6glichen es Modellen, saisonale Muster, Wochentags- und Monatseffekte zu lernen.

      **Parameter:**
      - `column` *(Standard: `dteday`)* \u2014 Name der Datumsspalte
      - `features` *(Standard: `["weekday", "month"]`)* \u2014 Welche Features extrahiert werden:
        - `weekday` \u2014 Wochentag (0=Montag, 6=Sonntag)
        - `month` \u2014 Monat (1\u201312)
        - `day_of_month` \u2014 Tag im Monat (1\u201331)
        - `year` \u2014 Jahr
        - `quarter` \u2014 Quartal (1\u20134)
      - `drop_original` *(Standard: `false`)* \u2014 Datumsspalte nach Extraktion entfernen?

      **Tipp:** `dteday` sollte vorher mit `cast_dtype` auf `datetime64` gesetzt werden, damit die Extraktion korrekt funktioniert.

      **Beispiel:**
      > \u201eExtrahiere Wochentag, Monat und Quartal aus der Datumsspalte dteday\u201c
      > \u201eErstelle Zeitfeatures aus dteday und entferne die Originalspalte danach\u201c

    cast_dtype: |
      ### \U0001f9f9 `cast_dtype` \u2014 Datentyp einer Spalte \u00e4ndern

      \u00c4ndert den Datentyp einzelner Spalten. N\u00fctzlich, um nominale Spalten wie `season` oder `weathersit` von `int64` auf `category` zu setzen (damit Encoding-Schritte greifen) oder `dteday` auf `datetime64` (f\u00fcr Time-Feature-Extraktion).

      **Parameter:**
      - `columns` \u2014 Mapping von Spaltenname zu Zieldatentyp, z.\u00a0B. `{"season": "category", "dteday": "datetime64"}`
        - Erlaubte Typen: `int64` | `float64` | `str` | `object` | `category` | `bool` | `datetime64`
      - `datetime_format` *(optional)* \u2014 strptime-Format f\u00fcr `datetime64`-Casts, z.\u00a0B. `"%Y-%m-%d"`

      **Tipp:** F\u00fchre diesen Schritt m\u00f6glichst **fr\u00fch** in der Pipeline aus \u2014 korrekte Datentypen helfen allen nachfolgenden Schritten.

      **Beispiel:**
      > \u201eKonvertiere season und weathersit zu category\u201c
      > \u201eCaste dteday auf datetime64 mit Format %Y-%m-%d\u201c

    split: |
      ### \U0001f9f9 `split` \u2014 Train/Test-Split

      Teilt den Datensatz in **Trainings-** und **Testdaten** auf. Die Trainingsdaten werden f\u00fcr das Modelltraining verwendet, die Testdaten zur unabh\u00e4ngigen Bewertung \u2014 so wird sichergestellt, dass das Modell auf neuen Daten funktioniert.

      **Parameter:**
      - `test_size` *(Standard: `0.2`)* \u2014 Anteil der Testdaten (0.0\u20131.0). `0.2` = 20\u00a0% Test, 80\u00a0% Training.
      - `random_state` *(Standard: `42`)* \u2014 Zufalls-Seed f\u00fcr Reproduzierbarkeit

      **\u26a0\ufe0f Wichtig:** Muss **vor** dem Modelltraining ausgef\u00fchrt werden.
      Lernende Preprocessing-Schritte (Imputation, Encoding, Outlier Handling) sollten **nach** dem Split laufen \u2014 sonst Data Leakage. Gysi warnt automatisch, wenn das nicht eingehalten wird.

      **Beispiel:**
      > \u201eTeile die Daten 80/20 auf\u201c
      > \u201eF\u00fchre einen Train-Test-Split mit 25\u00a0% Testdaten durch\u201c

    train_decision_tree: |
      ### \U0001f916 `train_decision_tree` \u2014 Decision Tree trainieren

      Trainiert einen **Entscheidungsbaum** (sklearn `DecisionTreeRegressor`) auf die Zielspalte `cnt` (Fahrradausleihen). Bewertet das Modell nach dem Training auf den Testdaten und gibt R\u00b2, MAE und RMSE aus.

      **Parameter:**
      - `max_depth` *(Standard: kein Limit)* \u2014 Maximale Baumtiefe. Ohne Limit \u00fcberfittet der Baum leicht \u2014 empfohlen: `4`\u2013`6`.
      - `random_state` *(Standard: `42`)* \u2014 Zufalls-Seed

      **Tipp:** Starte mit `max_depth=4` oder `max_depth=5` und erh\u00f6he schrittweise, wenn die Trainingsmetriken noch schlecht sind. Ein Decision Tree ist gut f\u00fcr eine erste Basislinie \u2014 f\u00fcr bessere Genauigkeit dann EBM ausprobieren.

      **Voraussetzung:** `split` muss vorher ausgef\u00fchrt worden sein.

      **Beispiel:**
      > \u201eTrainiere einen Decision Tree mit max_depth=4\u201c
      > \u201eTrainiere einen Entscheidungsbaum ohne Tiefenlimit\u201c

    train_ebm: |
      ### \U0001f916 `train_ebm` \u2014 Explainable Boosting Machine trainieren

      Trainiert eine **Explainable Boosting Machine** (InterpretML). EBM ist \u00e4hnlich wie Gradient Boosting, aber jedes Feature wird separat modelliert \u2014 das Modell bleibt vollst\u00e4ndig interpretierbar. Meist pr\u00e4ziser als ein Decision Tree, l\u00e4uft aber langsamer.

      **Parameter:**
      - `random_state` *(Standard: `42`)* \u2014 Zufalls-Seed

      **Vorteile:**
      - Hohe Genauigkeit bei gleichzeitiger globaler und lokaler Erkl\u00e4rbarkeit
      - Gysi erkl\u00e4rt die Feature-Beitr\u00e4ge nach dem Training automatisch
      - Kein max_depth-Tuning n\u00f6tig \u2014 EBM regularisiert sich intern

      **Voraussetzung:** `split` muss vorher ausgef\u00fchrt worden sein.

      **Beispiel:**
      > \u201eTrainiere ein EBM-Modell\u201c
      > \u201eTrainiere eine Explainable Boosting Machine zum Vergleich mit dem Decision Tree\u201c

    catboost_feature_selection: |
      ### \U0001f916 `catboost_feature_selection` \u2014 Feature-Wichtigkeit analysieren

      Nutzt **CatBoost**, um die Wichtigkeit jedes Features f\u00fcr die Zielspalte `cnt` zu berechnen und zu ranken. Gibt die `top_n` wichtigsten Features aus. Kann anschlie\u00dfend unwichtige Features aus dem Datensatz entfernen.

      **Parameter:**
      - `top_n` *(Standard: `8`)* \u2014 Anzahl der anzuzeigenden wichtigsten Features
      - `analysis_only` *(Standard: `true`)* \u2014 Nur analysieren, kein Feature wird entfernt
      - `features_to_drop` *(Standard: leer)* \u2014 Features, die nach Pr\u00fcfung entfernt werden sollen

      **Typischer Ablauf (zweistufig):**
      1. `analysis_only=true` \u2014 Gysi zeigt Ranking der wichtigsten Features
      2. Du entscheidest, welche unwichtigen Features weg sollen
      3. Gysi f\u00fchrt den Schritt mit `features_to_drop` erneut aus

      **Tipp:** N\u00fctzlich vor dem eigentlichen Training, um irrelevante oder redundante Spalten zu entfernen und das Modell zu vereinfachen.

      **Voraussetzung:** `split` muss vorher ausgef\u00fchrt worden sein.

      **Beispiel:**
      > \u201eWelche Spalten haben den gr\u00f6\u00dften Einfluss auf cnt?\u201c
      > \u201eAnalysiere die Feature-Wichtigkeit mit top_n=10\u201c

    plot_distribution: |
      ### \U0001f4ca `plot_distribution` \u2014 Verteilung einer Spalte visualisieren

      Erzeugt eine **Visualisierung** der Werteverteilung einer Spalte. Wird als Bild in den Artefakten gespeichert. Mit `group_by` kann die Verteilung nach einer kategorischen Spalte aufgeteilt werden \u2014 dann entstehen ein Mittelwert-Balkendiagramm und ein gruppierter Boxplot.

      **Parameter:**
      - `feature` *(Pflicht)* \u2014 Name der zu visualisierenden Spalte, z.\u00a0B. `cnt`, `temp`, `windspeed`
      - `group_by` *(Standard: kein)* \u2014 Optionale Gruppierspalte, z.\u00a0B. `season`, `weathersit`, `weekday`

      **Hinweis:** Dieser Schritt ist **transient** \u2014 er wird nicht dauerhaft in der Pipeline-Spec gespeichert und beeinflusst keine Modelle. Er kann jederzeit aufgerufen werden.

      **Tipp:** Nutze `plot_distribution` vor dem Preprocessing, um ein Gef\u00fchl f\u00fcr die Daten zu bekommen \u2014 z.\u00a0B. ob `windspeed` eine schiefe Verteilung hat oder ob `cnt` nach Saison stark variiert.

      **Beispiel:**
      > \u201eZeige die Verteilung von cnt\u201c
      > \u201eZeige die Verteilung von cnt gruppiert nach season\u201c
      > \u201eVisualisiere windspeed gruppiert nach weathersit\u201c
"""

target = pathlib.Path(__file__).parents[1] / "configs" / "help_texts.yaml"
target.write_text(CONTENT, encoding="utf-8")
print(f"Geschrieben: {target}")
