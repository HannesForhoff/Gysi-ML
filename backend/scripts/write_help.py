"""Einmaliges Skript: Schreibt help_texts.yaml mit korrektem Inhalt."""
import pathlib

CONTENT = """\
welcome_message: |
  Willkommen bei Gysi \u2014 deinem ML-Assistenten f\u00fcr den Bike-Datensatz!

  **Was ich kann:**
  - Preprocessing-Schritte konfigurieren (Dedup, Imputation, Encoding, ...)
  - Modelle trainieren (Decision Tree, EBM, CatBoost)
  - Ergebnisse erkl\u00e4ren und Runs vergleichen

  **Beispiele:**
  - \u201eEntferne Duplikate und impute fehlende Werte mit Median\u201c
  - \u201eTrainiere einen Decision Tree mit max_depth=5\u201c

  **Hilfe:** /help, /overview, /status

help:
  full_text: |
    ## Gysi \u2013 Hilfe\u00fcbersicht
    Beschreibe auf Deutsch, was du tun m\u00f6chtest. Gysi \u00fcbersetzt deine Anfrage in Aktionsschritte und f\u00fchrt sie aus.
    Du brauchst keine ML-Kenntnisse \u2014 einfach nat\u00fcrliche Sprache verwenden.

    ### Datensatz erkunden
    - **`/overview`** \u2014 Statistische \u00dcbersicht: Spaltennamen, Datentypen, fehlende Werte und Werteverteilung
    - **`/status`** \u2014 Aktueller Stand deiner Pipeline und Ergebnisse des letzten Runs

    ### Preprocessing-Schritte
    Diese Schritte bereinigen und transformieren die Rohdaten, bevor ein Modell trainiert werden kann:
    - **Duplikate entfernen** \u2014 Entfernt identische Zeilen aus dem Datensatz
    - **Imputation** \u2014 F\u00fcllt fehlende Werte auf (z.\u00a0B. mit Median, Mittelwert oder einem festen Wert)
    - **Encoding** \u2014 Wandelt Text-Kategorien in Zahlen um, damit Modelle damit arbeiten k\u00f6nnen
    - **Outlier Handling** \u2014 Erkennt und behandelt Ausrei\u00dfer (z.\u00a0B. per IQR-Methode)
    - **Correlation Filter** \u2014 Entfernt Spalten, die stark miteinander korrelieren (Redundanzreduktion)
    - **Rare Category Bucketing** \u2014 Fasst selten vorkommende Kategorien zu einer Sammelgruppe zusammen
    - **Time Features** \u2014 Extrahiert neue Spalten aus Zeitstempeln (z.\u00a0B. Stunde, Wochentag, Monat)

    ### Modelltraining
    Vor dem Training muss immer ein **Train-Test-Split** durchgef\u00fchrt werden \u2014
    er teilt die Daten in Trainings- und Testdaten auf, damit das Modell fair bewertet werden kann.
    - **Decision Tree** \u2014 Einfaches, gut erkl\u00e4rbares Baummodell; typische Parameter: max_depth, target
    - **EBM (Explainable Boosting Machine)** \u2014 Genaues Modell mit eingebauter Erkl\u00e4rbarkeit
    - **CatBoost Feature Selection** \u2014 Ermittelt die wichtigsten Einflussvariablen (Feature Importance)

    ### Beispielanfragen
    > \u201eEntferne Duplikate und imputiere fehlende Werte in windspeed mit dem Median\u201c
    > \u201eF\u00fchre einen Train-Test-Split durch\u201c
    > \u201eTrainiere einen Decision Tree mit max_depth=4 auf die Zielspalte cnt\u201c

    ---
    **Grenzen:** Gysi arbeitet ausschlie\u00dflich mit dem Bike-Sharing-Datensatz. Kein Code-Upload, keine externen Daten, kein Deployment.

  categories:
    daten: "Datensatz erkunden: /overview, Profiling"
    preprocessing: "Dedup, Imputation, Encoding, Outlier Handling, Correlation Filter, Rare Category, Time Features"
    modellierung: "Decision Tree, EBM, CatBoost Feature Selection"
    grenzen: "Nur Bike-Datensatz, kein Code-Upload, kein Deployment"
"""

p = pathlib.Path(__file__).parent.parent / "configs" / "help_texts.yaml"
p.write_text(CONTENT, encoding="utf-8")
print(f"OK: {p}")
