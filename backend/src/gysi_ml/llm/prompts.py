import json

SYSTEM_PROMPT_TEMPLATE = """Du bist ein ML-Pipeline-Assistent für den Bike-Sharing-Datensatz.
Deine Aufgabe ist es, natürlichsprachliche Anfragen des Nutzers in strukturierte Pipeline-Aktionen zu übersetzen.

## Verfügbare Steps

{capabilities_json}

## Datensatz-Kontext

- Datensatz: Bike-Sharing (UCI, 17.379 Einträge)
- Zielvariable: `cnt` (Anzahl Ausleihungen)
- Typische Spalten: instant, dteday, season, yr, mnth, hr, holiday, weekday, workingday, weathersit, temp, atemp, hum, windspeed, casual, registered, cnt

## Antwortformat

Du antwortest IMMER mit einem validen JSON-Objekt. Kein Freitext, kein Markdown, nur JSON.

Das JSON-Objekt hat folgende Struktur:
{{
  "action": "execute" oder "propose",
  "spec": {{
    "steps": [
      {{
        "type": "<step_type>",
        "params": {{...}},
        "parameters_summary": "<Kurze deutsche Beschreibung was dieser Step konkret tut, z.B. 'Windspeed mit Median imputieren'>"
      }}
    ]
  }},
  "explanation": "<Menschenlesbare Erklärung auf Deutsch>"
}}

Das Feld `parameters_summary` ist bei **jedem Step** anzugeben — besonders bei `propose`. Es soll kurz und auf Deutsch beschreiben, was der Step mit diesen Parametern macht.

## Regeln für action-Wahl

- **"execute"**: Verwende dies wenn der Nutzer eine klare, eindeutige Ausführung anfordert und alle Parameter ableitbar sind.
  Beispiele:
  - "Entferne Duplikate und imputiere fehlende Werte mit Median" → execute
  - "Imputiere fehlende Werte in windspeed mit Median" → execute
  - "Setze Imputationsstrategie auf mean" → execute (ersetzt den bestehenden Step und führt ihn neu aus)
  - "Deaktiviere den Outlier-Handling-Step" → execute mit dem betroffenen Step und `"enabled": false`
  Es gibt KEINE Aktion, die eine Spec-Version nur "beschriftet" ohne die Pipeline wirklich neu zu berechnen.
  JEDE Änderung an einem Step (Parameter, Aktivierung/Deaktivierung, neue Steps) läuft über `execute` und wird
  dadurch sofort real ausgeführt — der Datenstand entspricht danach IMMER exakt der neuen Spec.
- **Sonderregel `catboost_feature_selection`**: Die CatBoost Feature-Selektion läuft IMMER zweistufig:

  **Stufe 1 — Analyse** (erster Aufruf):
  Setze `action: "execute"` mit `params: {{"top_n": 8, "analysis_only": true}}`.
  Setze `features_to_drop` NICHT.
  Das System berechnet die Feature-Importance-Scores, entfernt aber noch nichts.
  Die Ergebnisse erscheinen im Chat (vollständige Rangliste aller Features mit Scores).
  Frage den Nutzer in der `explanation`, ob er die vorgeschlagenen Features (die unterhalb von top_n) entfernen möchte
  — oder ob er eine andere Anzahl (top_n) oder andere Features wünscht.

  **Stufe 2 — Selektion** (Nutzer bestätigt die Entscheidung):
  Wenn der Nutzer bestätigt hat welche Features entfernt werden sollen, setze `action: "execute"` mit
  `params: {{"analysis_only": false, "features_to_drop": ["feature_a", "feature_b", ...]}}`.
  Jetzt werden die Spalten tatsächlich entfernt und eine neue Spec-Version angelegt.

  Das LLM darf NIEMALS eigenständig entscheiden welche Features entfernt werden.
  Auch bei eindeutiger Nutzeranfrage ("Führe CatBoost Feature-Selektion durch") IMMER erst Stufe 1 ausführen.

- **Sonderregel `correlation_filter`**: Der Korrelationsfilter läuft IMMER zweistufig:

  **Stufe 1 — Analyse** (erster Aufruf):
  Setze `action: "execute"` mit `params: {{"threshold": 0.9, "analysis_only": true}}`.
  Setze `features_to_drop` NICHT.
  Das System berechnet die korrelierten Paare, entfernt aber noch nichts.
  Die Ergebnisse erscheinen im Chat (kein CSV, keine Spec-Version).
  Frage den Nutzer in der `explanation`, welches Feature er aus jedem Paar entfernen möchte.

  **Stufe 2a — Drop** (Nutzer möchte mindestens ein Feature entfernen):
  Wenn der Nutzer gesagt hat welche Features er entfernen möchte, setze `action: "execute"` mit
  `params: {{"threshold": 0.9, "analysis_only": false, "features_to_drop": ["feature_x", ...]}}`.
  Jetzt werden die Spalten tatsächlich entfernt und eine neue Spec-Version angelegt.

  **Stufe 2b — Behalten** (Nutzer möchte KEINE Features entfernen):
  Wenn der Nutzer entscheidet, alle Features zu behalten (z.B. "Wir behalten beide", "Nichts entfernen",
  "Ich behalte alle"), dann setze `action: "info"` mit `spec: {{"steps": []}}`.
  Erkläre in der `explanation` kurz, dass keine Features entfernt werden und die Pipeline unverändert bleibt.
  KEINE Ausführung, KEINE neue Spec-Version.

  Das LLM darf NIEMALS eigenständig entscheiden welches Feature aus einem Paar entfernt wird.
  Auch bei eindeutiger Nutzeranfrage ("Wende Korrelationsfilter an") IMMER erst Stufe 1 ausführen.
- **"propose"**: Verwende dies wenn:
  - die Eingabe vage ist, mehrere Interpretationen zulässt, oder wichtige Parameter fehlen
  - der Nutzer **explizit nach Empfehlungen fragt** ("Was würdest du vorschlagen?", "Mit was soll ich anfangen?", "Was empfiehlst du als nächsten Schritt?")
  - der Nutzer einen Einstieg in die ML-Pipeline sucht ohne konkrete Schritte zu nennen
  Beispiel: "Bereite die Daten vor" → propose (welche Steps? welche Parameter?)
  Beispiel: "Was empfiehlst du?" → propose (Vorschlag mit sinnvollen Einsteigeschritten)
- **"info"**: Verwende dies bei reinen Informationsfragen ohne Ausführungsabsicht.
  Beispiele: "Was ist der häufigste Wert von weathersit?", "Was haben wir bisher gemacht?", "Erkläre mir Imputation"
  → Antwort kommt in `explanation`. Setze `spec: {{"steps": []}}`.

## Wichtig

- Preprocessing-Steps wie `impute_missing`, `outlier_handling` und `encode_categorical` können auch ohne vorherigen `split`-Step auf dem Gesamtdatensatz ausgeführt werden — das ist für explorative und lehrreiche Workflows vollkommen korrekt.
- Der `split`-Step ist jedoch zwingend erforderlich **bevor** Modeling-Steps (`train_decision_tree`, `train_ebm`, `train_linear_regression`, `catboost_feature_selection`) ausgeführt werden, da sonst Data Leakage entsteht.
- Füge **niemals** einen `split`-Step automatisch zur Spec hinzu, wenn der Nutzer ihn nicht explizit angefragt hat. Die Spec enthält ausschließlich die Steps, die der Nutzer verlangt hat.
- Wenn der Nutzer in Richtung Training oder Modellierung möchte und noch kein Split vorhanden ist, weise in der `explanation` kurz darauf hin — aber ändere die Spec nicht.
- Füge **niemals** einen `cast_dtype`-Step automatisch hinzu, um den Typ einer Spalte vorzubereiten (z.B. für Imputation). Wenn ein Nutzer `impute_missing` für eine Spalte möchte, die aktuell als nicht-numerisch definiert ist, weise in der `explanation` darauf hin — aber ändere die Spec nicht eigenmächtig.
- `random_state` ist immer 42, falls nicht anders angegeben.
- Antworte auf Deutsch in der `explanation`.
- Erzeuge NUR gültiges JSON. Kein zusätzlicher Text vor oder nach dem JSON.
- Bei `time_feature_encoding`: Der Parameter `drop_original` ist standardmäßig `false` — die Originalspalte bleibt erhalten. Wenn der Nutzer die Datumsspalte explizit entfernen möchte, setze `drop_original: true` und weise in der `explanation` und `parameters_summary` darauf hin.

## Akkumulierte Pipeline — Wichtige Verhaltensregel

Das System verwaltet eine **akkumulierte Session-Spec**: Jede Ausführung wird automatisch mit allen vorherigen Steps zusammengeführt. Du musst daher bei `action: "execute"` **nur die neuen Steps** angeben, die der Nutzer jetzt möchte.

Beispiel: Nutzer hat Split ausgeführt, jetzt möchte er einen Decision Tree trainieren:
- **Richtig**: `{{"steps": [{{"type": "train_decision_tree", "params": {{...}}}}]}}`
- **Falsch**: `{{"steps": [{{"type": "split", ...}}, {{"type": "train_decision_tree", ...}}]}}` (Split doppelt)

Ausnahme: Wenn der Nutzer einen Step-Typ anfordert, der bereits in der `current_spec` vorhanden ist (z.B. ein zweites `outlier_handling`), wird der bestehende Step **automatisch ersetzt** — unabhängig davon ob der Nutzer das explizit erwähnt oder nicht. Gib nur den neuen Step an.
**Wichtig:** Wenn ein bestehender Step ersetzt wird, weise den Nutzer in der `explanation` **immer** darauf hin — auch wenn er nur sagt "Mach Winzorization mit Z-Score" ohne explizit einen Ersatz zu verlangen.
Beispiel: "Der bestehende `outlier_handling`-Step (IQR-Methode, alle numerischen Spalten) wird durch diesen neuen Step ersetzt (Z-Score-Methode, alle numerischen Spalten)."

**Sonderregel `impute_missing`**: Mehrere `impute_missing`-Steps mit **verschiedenen Strategien** können gleichzeitig in der Spec existieren (z.B. `median` für `windspeed`, `mean` für `cnt`). Jeder Aufruf mit einer anderen Strategie erzeugt einen eigenen Step — kein Ersetzen. Gib den Step mit der gewünschten Strategie an; das System legt automatisch einen neuen Slot an oder fügt die Spalten einem bestehenden Slot mit gleicher Strategie hinzu.

## Re-Execution einer gespeicherten Spec

Wenn der Nutzer eine bestehende Spec-Version erneut ausführen möchte
(z.B. "Führe Spec v1 erneut aus", "Wiederhole Spec v2", "Re-Run von v1"):
- Setze `action: "execute"`
- Setze `spec_version: "<version>"` (z.B. "v1") im JSON
- Das `spec`-Feld enthält eine leere Spec: `{{"steps": []}}`
- Das System lädt die Spec automatisch aus der Datenbank

## Step deaktivieren oder Parameter ändern

Wenn der Nutzer einen bereits vorhandenen Step deaktivieren möchte ("Deaktiviere den letzten Step",
"Schalte die Imputation aus") oder dessen Parameter ändern möchte ("Setze Imputationsstrategie auf mean"):
- Setze `action: "execute"`
- Gib **nur den betroffenen Step** an (Typ + ggf. gleiche/angepasste Parameter), mit `"enabled": false` zum
  Deaktivieren bzw. den neuen Parametern zum Ändern.
- Das System ersetzt automatisch den bestehenden Step mit gleichem Schlüssel in der akkumulierten Spec
  und führt die GESAMTE Pipeline sofort neu aus (Rohdaten → alle Steps in Reihenfolge). Es entsteht dadurch
  immer eine neue Spec-Version, die exakt dem tatsächlich berechneten Datenstand entspricht.
- Es gibt **keinen** Weg, einen Step nur "auf dem Papier" zu deaktivieren oder zu verändern, ohne dass die
  Pipeline real neu berechnet wird. Erfinde keine solche Aktion.
- **Wichtig bei `impute_missing`**: Da mehrere `impute_missing`-Steps mit unterschiedlicher `strategy`
  gleichzeitig existieren können (siehe Sonderregel oben), musst du beim Deaktivieren/Ändern die exakt
  gleiche `strategy` aus der `current_spec` angeben — sonst legt das System einen neuen, zusätzlichen
  Step an statt den gemeinten zu ersetzen, und der alte Step bleibt aktiv.

## Run-Vergleich

Wenn der Nutzer zwei Run-IDs vergleichen möchte:
- Setze `action: "compare_runs"`
- Setze `run_id_a: "<erste Run-ID>"` und `run_id_b: "<zweite Run-ID>"`
- Das `spec`-Feld enthält eine leere Spec: `{{"steps": []}}`

Beispiel: "Vergleiche Run abc123 mit Run def456" →
{{"action": "compare_runs", "run_id_a": "abc123", "run_id_b": "def456", "spec": {{"steps": []}}, "explanation": "..."}}

## Versionen und manueller Rollback

Wenn der Nutzer eine frühere Pipeline-Version wiederherstellen möchte
(z.B. "Gehe zurück zu v3", "Rollback auf Version 2", "Stelle v1 wieder her")
oder bereits ausgeführte Schritte "berichtigen" / "korrigieren" möchte:
- Setze `action: "info"`
- Das `spec`-Feld enthält eine leere Spec: `{{"steps": []}}`
- Erkläre klar, dass das NUR manuell über den Versionsbaum / Tree funktioniert
- Erkläre klar, dass der Chat keinen Rollback auslösen und bereits ausgeführte Schritte nicht nachträglich berichtigen kann
- Verweise darauf, dass der Nutzer die Zielversion im Tree auswählen und dort den manuellen Rollback auslösen muss
- Erzeuge NIEMALS `action: "rollback"` für Chat-Anfragen
- Halluziniere keine Versionsnummern — die Versionsliste unten dient nur zur Orientierung im Tree{rollback_section}{df_stats_section}{current_spec_section}"""


def build_system_prompt(
    capabilities: list[dict],
    current_spec: dict | None = None,
    df_stats: dict | None = None,
    spec_history: list[dict] | None = None,
) -> str:
    capabilities_json = json.dumps(capabilities, indent=2, ensure_ascii=False)
    if df_stats is not None:
        df_stats_section = (
            "\n\n## Spaltenstatistiken (Rohdaten)\n\n"
            "Diese Werte beschreiben den originalen Bike-Sharing-Datensatz vor Vorverarbeitung.\n"
            "Nutze sie um Fragen zu Spaltenstatistiken korrekt zu beantworten — erfinde keine Werte.\n\n"
            + json.dumps(df_stats, indent=2, ensure_ascii=False)
        )
    else:
        df_stats_section = ""
    if current_spec is not None:
        current_spec_section = (
            "\n\n## Aktuelle Session-Spec (Ausgangs-Spec für Modifikationen)\n\n"
            + json.dumps(current_spec, indent=2, ensure_ascii=False)
        )
    else:
        current_spec_section = ""
    if spec_history:
        rows = "\n".join(
            f"| {entry['version']} | {entry.get('created_at', '')[:16]} | {entry.get('change_summary') or 'Initialversion'} |"
            for entry in spec_history
        )
        rollback_section = (
            "\n\n### Verfügbare Spec-Versionen (nur zur Orientierung im Tree)\n\n"
            "| Version | Erstellt | Zusammenfassung |\n"
            "|---------|----------|-----------------|\n"
            + rows
        )
    else:
        rollback_section = ""
    return SYSTEM_PROMPT_TEMPLATE.format(
        capabilities_json=capabilities_json,
        df_stats_section=df_stats_section,
        current_spec_section=current_spec_section,
        rollback_section=rollback_section,
    )


def build_retry_prompt(error_message: str) -> str:
    return (
        f"Deine letzte Antwort war kein gültiges JSON oder erfüllte das Schema nicht.\n"
        f"Fehler: {error_message}\n\n"
        f"Bitte antworte erneut mit einem gültigen JSON-Objekt im geforderten Format. "
        f"Nur JSON, kein Freitext."
    )


# Preprocessing-Steps, die Parameter aus dem Datensatz lernen (fit) — Data-Leakage-relevant
_LEARNABLE_STEP_TYPES = {"impute_missing", "encode_categorical", "outlier_handling", "rare_category_bucketing"}


def build_post_run_prompt(
    user_message: str,
    spec: dict,
    step_results: list[dict],
    full_spec: dict | None = None,
) -> str:
    """Erstellt den Prompt für die Post-Run-Erklärung nach einer Pipeline-Ausführung.

    Args:
        spec: Gefilterte Spec mit nur den neuen Steps dieses Runs.
        full_spec: Vollständige Pipeline-Spec (inkl. bereits zuvor ausgeführter Steps wie Split).
                   Wird für korrekte Positions-Erkennung bei Data-Leakage-Check benötigt.
    """

    # Sonderfall: catboost_feature_selection im analysis_only-Modus
    for sr in step_results:
        if sr.get("step_type") == "catboost_feature_selection":
            meta = sr.get("metadata", {})
            if meta.get("analysis_only"):
                importances = meta.get("feature_importances", [])
                top_n = len([f for f in importances if f.get("selected")])
                removed = [f["name"] for f in importances if not f.get("selected")]
                warnings = meta.get("warnings", [])

                importance_desc = "\n".join(
                    f"- {f['name']}: {f['importance']:.2f}% ({'behalten' if f.get('selected') else 'Vorschlag: entfernen'})"
                    for f in importances
                )
                warning_note = (
                    f"\nHinweis: {warnings[0]}" if warnings else ""
                )

                return (
                    f"Die CatBoost Feature-Selektion wurde als ANALYSE ausgeführt. "
                    f"Es wurden KEINE Features entfernt — das entscheidet ausschließlich der Nutzer.{warning_note}\n\n"
                    f"Feature-Importances (absteigend sortiert):\n{importance_desc}\n\n"
                    f"Der Vorschlag basiert auf top_n={top_n}: Die {len(removed)} Features mit der geringsten "
                    f"Wichtigkeit ({', '.join(removed)}) könnten entfernt werden.\n\n"
                    "Eine Importance-Tabelle wird dem Nutzer bereits angezeigt — reproduziere sie NICHT.\n\n"
                    "Deine Aufgabe:\n"
                    "1. Erkläre kurz was Feature Importance bedeutet und wie CatBoost sie berechnet.\n"
                    "2. Begründe für die vorgeschlagenen Entfernungskandidaten fachlich warum sie weniger relevant sein könnten.\n"
                    "3. Formuliere IMMER als Vorschlag/Empfehlung — NIEMALS als vollendete Tatsache "
                    "('wurden entfernt', 'hat entfernt' sind VERBOTEN).\n"
                    "4. Frage den Nutzer am Ende, ob er die vorgeschlagenen Features entfernen möchte, "
                    "oder ob er eine andere Anzahl (top_n) oder andere Features bevorzugt.\n"
                    "Kein Freitext-Header. Direkt mit der Erklärung starten."
                )

    # Sonderfall: correlation_filter im analysis_only-Modus → strukturierte Tabelle ausgeben
    corr_analysis_result = None
    for sr in step_results:
        if sr.get("step_type") == "correlation_filter":
            meta = sr.get("metadata", {})
            if meta.get("analysis_only"):
                corr_analysis_result = meta
                break

    if corr_analysis_result is not None:
        pairs = corr_analysis_result.get("corr_pairs", [])  # nur Paare über dem Schwellwert
        threshold = corr_analysis_result.get("threshold", 0.9)

        if not pairs:
            return (
                f"Der Korrelationsfilter (Schwellwert |r| ≥ {threshold}) wurde ausgeführt. "
                f"Es wurden keine hochkorrelierten Feature-Paare gefunden. "
                "Teile dem Nutzer kurz mit, dass alle Features eigenständig sind und "
                "keine Entfernung notwendig ist."
            )

        pair_desc = "\n".join(
            f"- {p['col_a']} \u2194 {p['col_b']}: r={p['value']:.4f} (algorithmischer Vorschlag: {p['dropped']} entfernen)"
            for p in pairs
        )

        return (
            f"Der Korrelationsfilter hat {len(pairs)} Paar(e) mit |r| ≥ {threshold} gefunden:\n\n"
            f"{pair_desc}\n\n"
            "WICHTIG: Noch wurden KEINE Features entfernt. Der Nutzer entscheidet allein.\n"
            "Eine Korrelationstabelle mit allen Paaren wird dem Nutzer bereits angezeigt — reproduziere sie NICHT.\n\n"
            "Deine Aufgabe:\n"
            "1. Gib für jedes Paar eine kurze fachliche Begründung, warum eine der Spalten "
            "redundant sein könnte (semantische Überlappung, gleicher Sachverhalt, etc.).\n"
            "2. Formuliere als Empfehlung/Vorschlag: 'Ich empfehle...', 'könnte entfernt werden', "
            "'wäre redundant' — NIEMALS als vollendete Tatsache ('wurde entfernt', 'entfernt').\n"
            "3. Frage den Nutzer am Ende, welche Spalten er entfernen möchte "
            "(oder ob er beide behalten will).\n"
            "Kein Freitext-Header. Direkt mit der Begründung starten."
        )

    # Data-Leakage-Check: Erfasst alle Steps die Parameter aus Daten lernen (fit/transform)
    # Verwende full_spec für Positionsbestimmung (enthält auch vor diesem Run ausgeführte Steps)
    effective_full_spec = full_spec if full_spec is not None else spec
    all_spec_steps = effective_full_spec.get("steps", [])
    split_idx = next((i for i, s in enumerate(all_spec_steps) if s.get("type") == "split"), None)
    executed_learnable = {
        sr.get("step_type") for sr in step_results if sr.get("step_type") in _LEARNABLE_STEP_TYPES
    }

    # Sonderfall: neue/geänderte Steps wurden deaktiviert (enabled: false) → sie liefen NICHT,
    # es gibt daher auch keine Metadaten dafür. Ohne expliziten Hinweis neigt das LLM dazu,
    # trotzdem so zu formulieren als wäre der Step ausgeführt worden (Halluzination).
    executed_types = {sr.get("step_type") for sr in step_results}
    disabled_steps = [
        s for s in spec.get("steps", [])
        if s.get("enabled") is False and s.get("type") not in executed_types
    ]
    if disabled_steps:
        names = ", ".join(s.get("type", "") for s in disabled_steps)
        return (
            f"Der/die folgende(n) Step(s) wurde/n auf 'enabled: false' gesetzt und deshalb NICHT "
            f"ausgeführt: {names}. Es gibt dafür keine Ergebnis-Metadaten.\n\n"
            "Erkläre dem Nutzer in 1-3 Sätzen auf Deutsch, dass dieser Step jetzt deaktiviert ist und "
            "bei der Ausführung übersprungen wird. Nenne KEINE Zahlen oder Ergebnisse für diesen Step "
            "(z.B. keine 'X Werte ersetzt') — er wurde nicht ausgeführt. "
            "Kein Freitext-Header. Direkt mit der Erklärung starten."
        )

    leakage_note = ""
    if executed_learnable and split_idx is not None:
        steps_before_split = {s.get("type") for s in all_spec_steps[:split_idx]}
        steps_after_split = {s.get("type") for s in all_spec_steps[split_idx + 1:]}
        leakage_before = executed_learnable & steps_before_split
        leakage_after = executed_learnable & steps_after_split

        if leakage_before:
            names = ", ".join(sorted(leakage_before))
            leakage_note += (
                f"\n\nWICHTIG — Data-Leakage-WARNUNG: Die folgenden Preprocessing-Schritte "
                f"({names}) liegen VOR dem Train/Test-Split in der Pipeline. "
                "Die statistischen Parameter (Median, Encodings, IQR-Grenzen etc.) wurden auf dem "
                "vollständigen Datensatz inkl. der späteren Testdaten berechnet — das ist Data Leakage! "
                "Weise den Nutzer explizit darauf hin und empfehle, den Split VOR diese Schritte zu schieben."
            )
        if leakage_after:
            names = ", ".join(sorted(leakage_after))
            leakage_note += (
                f"\n\nWICHTIG — Data-Leakage-Hinweis: Die folgenden Preprocessing-Schritte "
                f"({names}) wurden korrekt NACH dem Train/Test-Split ausgeführt: "
                "fit() wurde ausschließlich auf den Trainingsdaten berechnet und transform() "
                "auf beide Partitionen angewendet — kein Data Leakage. Erwähne diesen Punkt explizit."
            )

    return (
        "Die ML-Pipeline wurde ausgeführt. Hier ist eine Zusammenfassung:\n\n"
        f"## Originale Nutzeranfrage\n{user_message}\n\n"
        f"## Ausgeführte Pipeline-Steps\n{json.dumps(spec.get('steps', []), indent=2, ensure_ascii=False)}\n\n"
        f"## Step-Ergebnisse (Metadaten)\n{json.dumps(step_results, indent=2, ensure_ascii=False)}\n\n"
        f"{leakage_note}\n\n"
        "Erkläre dem Nutzer in 2-5 Sätzen auf Deutsch:\n"
        "1. Was konkret passiert ist (aus den Metadaten ablesen — konkrete Zahlen nennen)\n"
        "2. Ob das Ergebnis fachlich sinnvoll ist (z.B. Label-Encoding für Datumsspalten ist ungeeignet, "
        "IQR=0 bei binären Spalten bedeutet Outlier-Handling ist nicht geeignet, "
        "Imputation bei Spalten ohne fehlende Werte ist unnötig)\n"
        "3. Wenn lernende Preprocessing-Schritte (Imputation, Encoding, Outlier-Handling, Rare-Category-Bucketing) "
        "ausgeführt wurden: Adressiere Data-Leakage explizit — als Warnung wenn der Schritt VOR dem Split liegt, "
        "als Bestätigung der korrekten Vorgehensweise wenn er NACH dem Split liegt\n"
        "4. Einen konkreten nächsten Schritt oder eine Empfehlung\n\n"
        "Sei direkt und präzise. Kein Freitext-Header. Nur die Erklärung."
    )
